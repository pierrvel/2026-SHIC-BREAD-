"""Run the camera, analyzer and LAN dashboard together. No Node/Firebase required.

The local API preserves the config/status schema. It is an optional on-device
development path; main.py remains the Firebase production worker.
"""
import argparse
import copy
import hashlib
import hmac
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import math
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import threading
import time
from urllib.parse import urlsplit

import cv2

from analyzer import validate_config
from generate_sample import DEFAULT_CONFIG, generate
from main import Camera, atomic_json, process_once

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger('bread.local')


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def atomic_bytes(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


class LocalState:
    def __init__(self, data_dir, sample=False, sample_image=None, empty_image=None,
                 backend='auto', camera_index=0, interval=30):
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.data_dir / 'state.json'
        self.sample = sample
        self.backend, self.camera_index, self.interval = backend, camera_index, interval
        self.sample_image = Path(sample_image) if sample_image else self.data_dir / 'fixtures/sample_vending.jpg'
        self.empty_image = Path(empty_image) if empty_image else (
            self.data_dir / 'fixtures/empty_vending.jpg' if sample else self.data_dir / 'empty-machine.png')
        if sample and not sample_image and not empty_image:
            if not self.sample_image.exists() and not self.empty_image.exists():
                generate(self.data_dir / 'fixtures')
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        if self.path.exists():
            self.config = json.loads(self.path.read_text(encoding='utf-8'))['config']
        validate_config(self.config)
        self.empty = cv2.imread(str(self.empty_image)) if self.empty_image.exists() else None
        if self.empty_image.exists() and self.empty is None:
            raise ValueError('빈 칸 기준 사진을 읽지 못했습니다. 파일 경로를 확인하세요.')
        self.status = None  # Do not present a previous boot's status as current.
        self.frame = self.jpeg = None
        self.frame_version = 0
        self.ready = False
        self.error = None
        self.revision = 0
        self.previous_frame = self.previous_config = None
        self.lock = threading.RLock()
        self.capture_lock = threading.Lock()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.thread = None
        self.camera = None

    def snapshot(self):
        with self.lock:
            if self.error:
                message = self.error
            elif not self.ready:
                message = '카메라의 첫 촬영을 기다리고 있습니다.'
            elif self.empty is None:
                message = '관리자에서 실제 칸 위치를 조정하고 빈 칸 기준 사진을 촬영해 주세요. 보정 전에는 재고를 표시하지 않습니다.'
            elif self.status is None:
                message = '새 설정으로 재고를 판별하고 있습니다.'
            else:
                message = None
            return {'config': copy.deepcopy(self.config), 'status': copy.deepcopy(self.status),
                    'meta': {'sample': self.sample, 'camera_ready': self.ready,
                             'calibrated': self.empty is not None, 'frame_version': self.frame_version,
                             'message': message, 'error': self.error}}

    def persist(self):
        atomic_json(self.path, {'config': self.config, 'status': self.status})

    def update_config(self, config, expected):
        with self.lock:
            validate_config(config, self.frame.shape if self.frame is not None else None)
            if self.config != expected:
                raise APIError(409, '다른 관리자가 설정을 변경했습니다. 최신 설정을 불러온 뒤 다시 저장해 주세요.')
            old_config, old_status = self.config, self.status
            self.config, self.status = copy.deepcopy(config), None
            try:
                self.persist()
            except Exception:
                self.config, self.status = old_config, old_status
                raise
            self.revision += 1
            self.previous_frame = self.previous_config = None
        self.wake.set()

    def calibrate(self, confirmed):
        if confirmed is not True:
            raise APIError(400, '모든 칸이 비어 있는지 확인해 주세요.')
        try:
            frame = self.read_frame()  # Capture NOW, rather than using a stale cached photo.
        except Exception:
            raise APIError(503, '카메라에서 새 기준 사진을 촬영하지 못했습니다.')
        with self.lock:
            ok, encoded = cv2.imencode('.png', frame)
            if not ok:
                raise APIError(500, '기준 사진을 저장하지 못했습니다.')
            self.empty_image.parent.mkdir(parents=True, exist_ok=True)
            if self.empty_image.exists():
                shutil.copy2(self.empty_image, self.empty_image.with_suffix('.previous' + self.empty_image.suffix))
            atomic_bytes(self.empty_image, encoded.tobytes())
            self.empty = frame.copy()
            self.frame = frame.copy()
            jpeg_ok, jpeg = cv2.imencode('.jpg', frame)
            if jpeg_ok:
                self.jpeg = jpeg.tobytes()
            self.frame_version += 1
            self.ready, self.error = True, None
            self.revision += 1
            self.status = self.previous_frame = self.previous_config = None
        self.wake.set()

    def read_frame(self):
        with self.capture_lock:
            if self.sample:
                frame = cv2.imread(str(self.sample_image))
                if frame is None:
                    raise ValueError('샘플 사진을 읽지 못했습니다.')
                return frame
            if self.camera is None:
                self.camera = Camera(self.backend, self.camera_index)
            try:
                return self.camera.read()
            except Exception:
                self.camera.close()
                self.camera = None
                raise

    def refresh(self):
        frame = self.read_frame()
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise ValueError('촬영 사진을 인코딩하지 못했습니다.')
        with self.lock:
            self.frame, self.jpeg = frame.copy(), encoded.tobytes()
            self.frame_version += 1
            self.ready, self.error = True, None
            if self.empty is None:
                return
            config, empty, revision = copy.deepcopy(self.config), self.empty.copy(), self.revision
            previous_frame, previous_config = self.previous_frame, self.previous_config
        status = process_once(frame, empty, config, previous_frame, previous_config, 2.0)
        with self.lock:
            if self.revision != revision:
                self.wake.set()
                return
            if status is not None:
                old_status = self.status
                self.status = status
                try:
                    self.persist()
                except Exception:
                    self.status = old_status
                    raise
                self.previous_frame, self.previous_config = frame.copy(), config

    def run(self):
        try:
            while not self.stopping.is_set():
                self.wake.clear()
                version = self.frame_version
                try:
                    self.refresh()
                except Exception as error:
                    with self.lock:
                        self.error = ('칸 좌표와 빈 칸 기준 사진의 해상도를 확인해 주세요.'
                                      if isinstance(error, ValueError) else
                                      '카메라 촬영에 실패했습니다. 연결과 Picamera2 설치를 확인해 주세요.')
                        self.ready = self.frame_version > version
                    LOG.warning('Capture/analysis failed (%s)', type(error).__name__)
                self.wake.wait(self.interval)
        finally:
            if self.camera is not None:
                self.camera.close()

    def start(self):
        self.thread = threading.Thread(target=self.run, name='bread-camera', daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=5)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state, web_dir, password_file=None):
        self.state = state
        self.web_dir = Path(web_dir).resolve()
        if not (self.web_dir / 'index.html').is_file():
            raise ValueError('동봉된 웹 파일이 없습니다. 최신 저장소의 edge-pi/web 폴더를 받아 주세요.')
        self.password_file = Path(password_file) if password_file else state.data_dir / 'admin-password'
        self.password_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(self.password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(secrets.token_urlsafe(18) + '\n')
        self.password = self.password_file.read_text().strip()
        if len(self.password) < 12:
            raise ValueError('관리자 비밀번호는 12자 이상이어야 합니다.')
        self.sessions, self.attempts = {}, {}
        self.auth_lock = threading.Lock()
        super().__init__(address, Handler)

    def authenticated(self, headers):
        try:
            cookie = SimpleCookie(headers.get('Cookie', ''))
            token = cookie['bread_session'].value
        except (KeyError, ValueError, CookieError):
            return False
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.auth_lock:
            expires = self.sessions.get(key, 0)
            if expires > time.monotonic():
                return True
            self.sessions.pop(key, None)
        return False

    def sign_in(self, password, client):
        now = time.monotonic()
        with self.auth_lock:
            attempts = [when for when in self.attempts.get(client, []) if now - when < 60]
            if len(attempts) >= 5:
                raise APIError(429, '로그인 시도가 너무 많습니다. 1분 후 다시 시도해 주세요.')
            if not isinstance(password, str) or not hmac.compare_digest(password.encode(), self.password.encode()):
                self.attempts[client] = attempts + [now]
                raise APIError(401, '관리자 비밀번호가 올바르지 않습니다.')
            self.attempts.pop(client, None)
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            if len(self.sessions) >= 256:
                self.sessions.pop(next(iter(self.sessions)))
            token = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = now + 8 * 3600
            return token


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, _format, *args):
        pass  # Do not log credentials, cookies or submitted bodies.

    def send_data(self, status, data, content_type='application/json; charset=utf-8', cookie=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        self.close_connection = True
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, data, cookie=None):
        self.send_data(status, json.dumps(data, ensure_ascii=False, allow_nan=False).encode(), cookie=cookie)

    def require_admin(self):
        if not self.server.authenticated(self.headers):
            raise APIError(401, '관리자 로그인이 필요합니다.')

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path == '/api/state':
                self.send_json(200, self.server.state.snapshot())
            elif path == '/api/session':
                self.send_json(200, {'ready': True, 'admin': self.server.authenticated(self.headers),
                                     'email': '파이 관리자' if self.server.authenticated(self.headers) else None})
            elif path == '/api/frame.jpg':
                self.require_admin()
                with self.server.state.lock:
                    frame = self.server.state.jpeg if self.server.state.ready else None
                if not frame:
                    raise APIError(503, '촬영된 사진이 없습니다.')
                self.send_data(200, frame, 'image/jpeg')
            elif path in ('/', '/index.html'):
                html = (self.server.web_dir / 'index.html').read_text(encoding='utf-8')
                runtime = json.dumps({'mode': 'local', 'sample': self.server.state.sample})
                html = html.replace('<head>', '<head><script>window.__BREAD_RUNTIME__=' + runtime + ';</script>', 1)
                self.send_data(200, html.encode(), 'text/html; charset=utf-8')
            elif path == '/favicon.ico':
                self.send_data(204, b'', 'image/x-icon')
            else:
                raise APIError(404, '경로를 찾을 수 없습니다.')
        except APIError as error:
            self.send_json(error.status, {'error': error.message})

    def do_POST(self):
        try:
            origin = self.headers.get('Origin')
            if self.headers.get('Sec-Fetch-Site') == 'cross-site' or (
                    origin and urlsplit(origin).netloc != self.headers.get('Host')):
                raise APIError(403, '같은 사이트에서만 설정을 변경할 수 있습니다.')
            if self.headers.get_content_type() != 'application/json':
                raise APIError(415, 'JSON 요청이 필요합니다.')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                raise APIError(413, '요청 크기가 올바르지 않습니다.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise APIError(400, 'JSON 객체가 필요합니다.')
            path = urlsplit(self.path).path
            if path == '/api/login':
                token = self.server.sign_in(body.get('password'), self.client_address[0])
                self.send_json(200, {'ok': True}, cookie=f'bread_session={token}; HttpOnly; SameSite=Strict; Path=/api; Max-Age=28800')
            elif path == '/api/logout':
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                if 'bread_session' in cookie:
                    key = hashlib.sha256(cookie['bread_session'].value.encode()).hexdigest()
                    with self.server.auth_lock:
                        self.server.sessions.pop(key, None)
                self.send_json(200, {'ok': True}, cookie='bread_session=; HttpOnly; SameSite=Strict; Path=/api; Max-Age=0')
            elif path == '/api/config':
                self.require_admin()
                self.server.state.update_config(body.get('config'), body.get('expectedConfig'))
                self.send_json(200, {'ok': True})
            elif path == '/api/calibrate':
                self.require_admin()
                self.server.state.calibrate(body.get('confirmEmpty'))
                self.send_json(200, {'ok': True})
            elif path == '/api/capture':
                self.require_admin()
                self.server.state.wake.set()
                self.send_json(200, {'ok': True})
            else:
                raise APIError(404, '경로를 찾을 수 없습니다.')
        except APIError as error:
            self.send_json(error.status, {'error': error.message})
        except (ValueError, TypeError) as error:
            self.send_json(400, {'error': str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else '요청 형식이 올바르지 않습니다.'})
        except Exception:
            self.send_json(500, {'error': '저장하지 못했습니다. 파이의 저장 공간과 파일 권한을 확인해 주세요.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--interval', type=float, default=30)
    parser.add_argument('--sample', action='store_true', help='Explicit synthetic image mode; never silently used on camera failure')
    parser.add_argument('--sample-image', type=Path)
    parser.add_argument('--empty-image', type=Path)
    parser.add_argument('--camera-backend', choices=['auto', 'picamera2', 'opencv'], default='auto')
    parser.add_argument('--camera-index', type=int, default=0)
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.local/share/school-bread')
    parser.add_argument('--web-dir', type=Path, default=ROOT / 'web')
    parser.add_argument('--admin-password-file', type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error('--interval must be positive')
    if not args.sample and args.sample_image:
        parser.error('--sample-image requires --sample')
    state = LocalState(args.data_dir, args.sample, args.sample_image, args.empty_image,
                       args.camera_backend, args.camera_index, args.interval)
    server = LocalServer((args.host, args.port), state, args.web_dir, args.admin_password_file)
    LOG.info('Mode: %s; LAN dashboard port: %s', 'SYNTHETIC SAMPLE' if args.sample else 'REAL CAMERA', server.server_port)
    LOG.info('Administrator password file (not logged): %s', server.password_file)
    LOG.info('Open this Pi\'s IP address with port %s in a browser on the same network.', server.server_port)
    state.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info('Stopping')
    finally:
        state.stop()
        server.server_close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    main()
