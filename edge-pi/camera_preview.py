"""Camera-only LAN MJPEG preview. No inventory, recording, Firebase or npm.

One producer owns the camera; clients share its latest JPEG and skip old frames.
Picamera2 RGB888 arrays use BGR byte order, matching OpenCV's JPEG encoder.
"""
import argparse
from collections import deque
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hmac
import secrets
import signal
import sys
import threading
import time
from urllib.parse import urlsplit

import cv2
import numpy as np


PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>쉬는빵 · 카메라 연결 확인</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#111827;color:#f3f4f6;font:16px system-ui,sans-serif}
main{max-width:1600px;margin:auto;padding:24px}h1{font-size:24px;margin:0 0 12px}
p{line-height:1.7;color:#cbd5e1}.video{background:#020617;border-radius:12px;overflow:hidden;min-height:160px}
img{display:block;width:100%;height:auto}button{background:#f8fafc;color:#111827;border:0;padding:12px 18px;border-radius:8px;margin:12px 8px 0 0;cursor:pointer}
#status{padding:12px;background:#1e293b;border-radius:8px}#status[data-live="true"]{color:#86efac}
.mirror{transform:scaleX(-1)}small{color:#94a3b8}
.video:fullscreen{display:flex;align-items:center;justify-content:center;background:#000}
.video:fullscreen img{width:100%;height:100%;object-fit:contain}
form{margin-top:20px;padding:18px;background:#1e293b;border-radius:12px}
.controls{display:flex;flex-wrap:wrap;gap:16px;align-items:center}
label{display:flex;flex-direction:column;gap:6px}label.check{flex-direction:row;align-items:center}
input,select{font:inherit;padding:8px;border:1px solid #64748b;border-radius:6px;max-width:100%}
input[type=number]{width:100px}input[type=checkbox]{width:18px;height:18px}
button:disabled{opacity:.5;cursor:wait}#control-status{margin-bottom:0}#control-status[data-error=true]{color:#fca5a5}
@media(max-width:480px){main{padding:14px}form{padding:12px}}
</style><main><h1>카메라 연결 확인</h1>
<p id="source">카메라 상태 확인 중…</p><div class="video"><img id="video" src="/stream.mjpg" alt="카메라 실시간 영상"></div>
<p id="status" role="status">영상 수신 중…</p>
<button id="reconnect">다시 연결</button><button id="mirror">좌우 반전</button><button id="fullscreen">전체 화면</button>
<p id="settings"></p>
<form id="camera-controls"><div class="controls">
<label for="resolution">해상도<select id="resolution" aria-label="해상도"><option value="1920x1080">1920 × 1080 (Full HD 유지)</option></select></label>
<label for="fps">목표 FPS<input id="fps" type="number" min="30" max="60" step="1" required></label>
<label for="quality">JPEG 화질 <output id="quality-value"></output><input id="quality" aria-label="JPEG 화질" type="range" min="10" max="95" step="1"></label>
<label class="check"><input id="denoise" type="checkbox">노이즈 제거</label>
</div><button id="apply" type="submit" disabled>설정 적용</button><button id="reload-settings" type="button">현재 설정 불러오기</button>
<p id="control-status" role="status">현재 설정 확인 중…</p>
<p>FHD 해상도를 우선 유지하고 목표 FPS는 30–60 사이에서 조절합니다. 적용하면 영상이 잠시 멈출 수 있습니다. 실제 속도는 카메라·조명·처리 부하에 따라 달라집니다.</p></form>
<p>카메라 앞에서 손을 움직여 영상이 계속 바뀌는지 확인하세요.<br>이 화면은 영상 확인용이며 재고 판별과 녹화는 수행하지 않습니다.</p>
<small>같은 네트워크에서만 사용하세요. 종료: 파이 터미널에서 Ctrl+C.</small></main>
<script>
const video=document.getElementById('video'),status=document.getElementById('status');
const controlToken=__CONTROL_TOKEN__;
const form=document.getElementById('camera-controls'),apply=document.getElementById('apply'),message=document.getElementById('control-status');
const resolution=document.getElementById('resolution'),fps=document.getElementById('fps'),quality=document.getElementById('quality'),denoise=document.getElementById('denoise');
let currentHealth=null,formVersion=null,dirty=false,inFlight=false,pendingId=null,streamVersion=null;
function showMessage(text,error=false){message.textContent=text;message.dataset.error=String(error)}
function fillForm(h){
 const value=h.requested_width+'x'+h.requested_height;
 if(!Array.from(resolution.options).some(o=>o.value===value))resolution.add(new Option(h.requested_width+' × '+h.requested_height,value));
 resolution.value=value;fps.value=h.target_fps;quality.value=h.quality;denoise.checked=h.denoise;
 document.getElementById('quality-value').value=h.quality;formVersion=h.settings_version;dirty=false;
}
form.oninput=()=>{dirty=true;document.getElementById('quality-value').value=quality.value};
document.getElementById('reload-settings').onclick=()=>{if(currentHealth){fillForm(currentHealth);showMessage('현재 설정을 불러왔습니다.')}};
form.onsubmit=async e=>{
 e.preventDefault();if(!form.reportValidity()||inFlight||pendingId!==null)return;
 const [width,height]=resolution.value.split('x').map(Number);
 inFlight=true;apply.disabled=true;showMessage('설정 적용을 요청하는 중…');
 try{
  const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json','X-Preview-Token':controlToken},
   body:JSON.stringify({expected_version:formVersion,settings:{width,height,fps:Number(fps.value),quality:Number(quality.value),denoise:denoise.checked}})});
  const result=await response.json();if(!response.ok)throw Error(result.message||'설정을 적용하지 못했습니다.');
  pendingId=result.change_id;showMessage('설정 적용 중… 영상이 잠시 멈출 수 있습니다.');
 }catch(error){showMessage(error.message,true)}finally{inFlight=false}
};
let lastCount=-1,lastProgress=performance.now();
function reconnect(){video.src='/stream.mjpg?t='+Date.now();lastCount=-1;lastProgress=performance.now()}
document.getElementById('reconnect').onclick=reconnect;
document.getElementById('mirror').onclick=()=>video.classList.toggle('mirror');
document.getElementById('fullscreen').onclick=async()=>{
 try{await video.parentElement.requestFullscreen()}catch(e){status.textContent='이 브라우저에서는 전체 화면을 사용할 수 없습니다.'}
};
video.onerror=()=>{status.dataset.live='false';status.textContent='영상 연결이 끊겼습니다. 다시 연결을 눌러주세요.'};
async function poll(){
 try{
  const response=await fetch('/api/health',{cache:'no-store',signal:AbortSignal.timeout(2500)});
  if(!response.ok)throw Error('서버 오류');const h=await response.json();
  currentHealth=h;
  if(formVersion===null)fillForm(h);
  if(streamVersion!==null&&streamVersion!==h.stream_version)reconnect();streamVersion=h.stream_version;
  const busy=h.change_state==='pending'||h.change_state==='applying';
  if(pendingId!==null&&h.change_id>=pendingId&&!busy){
   pendingId=null;fillForm(h);showMessage(h.change_message,h.change_state==='failed');
  }else if(!inFlight&&pendingId===null){
   if(busy)showMessage('다른 화면에서 설정을 적용하고 있습니다.');
   else if(h.settings_version!==formVersion){
    if(dirty)showMessage('다른 화면에서 설정이 변경됐습니다. 현재 설정 불러오기를 눌러 확인하세요.',true);
    else{fillForm(h);showMessage(h.change_message||'변경된 설정을 반영했습니다.');}
   }else if(!dirty&&h.change_id===0)showMessage('설정을 선택한 뒤 설정 적용을 누르세요.');
  }
  apply.disabled=busy||inFlight||pendingId!==null;
  document.getElementById('source').textContent=(h.sample?'합성 테스트 영상 · 실제 카메라 아님':'실제 카메라 · '+h.backend)+' · '+h.width+' × '+h.height+' · 목표 '+h.target_fps+' FPS';
  document.getElementById('settings').textContent='JPEG 품질 '+h.quality+' · 노이즈 제거 '+(h.denoise?'켜짐':'꺼짐')+' · 프레임 '+h.jpeg_kb+' KB'+(h.device_fps?' · 장치 설정 '+h.device_fps+' FPS':'')+(h.width!==h.requested_width||h.height!==h.requested_height?' · 요청한 해상도와 다릅니다. 카메라 지원 모드를 확인하세요.':'');
  if(h.frames!==lastCount){lastCount=h.frames;lastProgress=performance.now()}
  const live=h.live&&video.naturalWidth>0&&performance.now()-lastProgress<3500;
  status.dataset.live=String(live);
  status.textContent=busy?'카메라 설정 적용 중…':h.error?'카메라 오류: '+h.error:live?'영상 수신 중 · 처리 출력 '+h.fps+' FPS · '+h.frames+' 프레임'+(h.fps<h.target_fps*.8?' · 목표 미달: 조명, 카메라 지원 속도와 처리 부하를 확인하세요.':''):'영상 수신 대기 또는 중단 · 계속 멈춰 있으면 다시 연결을 누르세요.';
 }catch(e){apply.disabled=true;status.dataset.live='false';status.textContent='서버 연결 끊김 · 파이 터미널과 네트워크를 확인하세요.'}
 setTimeout(poll,1000);
}poll();
</script></html>'''


class CameraSource:
    """Continuous capture; never reopen a device for every video frame."""

    def __init__(self, backend, width, height, fps, index):
        self.camera = None
        self.backend = backend
        self.started = False
        self.pixel_format = 'RGB888'
        self.device_fps = None
        try:
            if backend == 'picamera2':
                from picamera2 import Picamera2
                self.camera = Picamera2(index)
                available = self.camera.camera_controls
                controls = {}
                if 'FrameDurationLimits' in available:
                    duration = round(1_000_000 / fps)
                    controls['FrameDurationLimits'] = (duration, duration)
                else:
                    print('카메라가 FPS 제어를 지원하지 않습니다. 장치 기본 속도로 촬영하고 '
                          '송출 속도만 제한합니다. USB 웹캠은 --camera-backend opencv를 권장합니다.',
                          flush=True)
                configuration = self.camera.create_video_configuration(
                    main={'size': (width, height), 'format': 'RGB888'},
                    controls=controls, buffer_count=4)
                # Older Picamera2 versions may insert Raspberry Pi-only defaults
                # even for USB cameras. Never submit unadvertised controls.
                configuration['controls'] = {key: value for key, value in
                                             configuration.get('controls', {}).items() if key in available}
                self.camera.configure(configuration)
                self.pixel_format = self.camera.camera_configuration()['main']['format']
                self.camera.start()
                self.started = True
            else:
                self.camera = cv2.VideoCapture(index)
                if not self.camera.isOpened():
                    raise RuntimeError(f'USB 카메라 {index}를 열 수 없습니다')
                # Ask for compressed USB transport before negotiating size/rate.
                if not self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG')):
                    print('USB 카메라가 MJPEG 설정을 수락하지 않았습니다. 지원되는 기본 포맷을 사용합니다.', flush=True)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                self.camera.set(cv2.CAP_PROP_FPS, fps)
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                device_fps = self.camera.get(cv2.CAP_PROP_FPS)
                if fps >= 30 and np.isfinite(device_fps) and 0 < device_fps < 30:
                    # Some UVC drivers reject 60 FPS by selecting a slower mode.
                    # Retry 30 at the same resolution; never lower resolution automatically.
                    self.camera.set(cv2.CAP_PROP_FPS, 30)
                    device_fps = self.camera.get(cv2.CAP_PROP_FPS)
                if np.isfinite(device_fps) and device_fps > 0:
                    self.device_fps = round(device_fps, 1)
                    if device_fps < fps * .9:
                        print(f'USB 카메라가 요청 {fps} FPS 대신 {self.device_fps} FPS로 설정되었습니다. '
                              '해상도별 지원 FPS와 조명을 확인하세요.', flush=True)
        except Exception:
            # Cleanup errors must not replace the original initialization error.
            with suppress(Exception):
                self.close()
            raise

    def read(self):
        if self.backend == 'picamera2':
            frame = self.camera.capture_array('main')
            # USB libcamera pipelines can negotiate MJPEG instead of RGB888.
            # Picamera2 decodes MJPEG via Pillow to RGB; OpenCV expects BGR.
            if self.pixel_format == 'RGB888':
                return frame
            conversions = {'MJPEG': cv2.COLOR_RGB2BGR, 'BGR888': cv2.COLOR_RGB2BGR,
                           'XBGR8888': cv2.COLOR_RGBA2BGR, 'XRGB8888': cv2.COLOR_BGRA2BGR,
                           'YUYV': cv2.COLOR_YUV2BGR_YUYV, 'UYVY': cv2.COLOR_YUV2BGR_UYVY,
                           'YUV420': cv2.COLOR_YUV2BGR_I420}
            if self.pixel_format not in conversions:
                raise RuntimeError(f'지원하지 않는 카메라 포맷: {self.pixel_format}. '
                                   'USB 웹캠은 --camera-backend opencv로 실행하세요')
            return cv2.cvtColor(frame, conversions[self.pixel_format])
        ok, frame = self.camera.read()
        if not ok:
            raise RuntimeError('USB 카메라 프레임을 읽지 못했습니다')
        return frame

    def close(self):
        if self.camera is not None:
            camera, self.camera = self.camera, None
            if self.backend == 'picamera2':
                try:
                    if self.started:
                        camera.stop()
                finally:
                    self.started = False
                    camera.close()
            else:
                camera.release()


class SampleSource:
    def __init__(self, width, height):
        self.width, self.height, self.number = width, height, 0

    def read(self):
        self.number += 1
        frame = np.full((self.height, self.width, 3), (35, 25, 15), dtype=np.uint8)
        x = (self.number * 11) % max(1, self.width - 50)
        cv2.rectangle(frame, (x, self.height // 2), (x + 40, self.height // 2 + 40), (50, 230, 80), -1)
        cv2.putText(frame, f'SYNTHETIC TEST - NOT CAMERA / {self.number}', (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        return frame

    def close(self):
        pass


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {'width', 'height', 'fps', 'quality', 'denoise'}:
        raise ValueError('해상도, FPS, 화질, 노이즈 제거 설정을 모두 입력하세요.')
    if any(type(settings[key]) is not int for key in ('width', 'height', 'fps', 'quality')) or type(settings['denoise']) is not bool:
        raise ValueError('해상도·FPS·화질은 정수, 노이즈 제거는 참/거짓이어야 합니다.')
    if not (128 <= settings['width'] <= 1920 and 96 <= settings['height'] <= 1080
            and settings['width'] % 2 == 0 and settings['height'] % 2 == 0
            and 1 <= settings['fps'] <= 120 and 10 <= settings['quality'] <= 95):
        raise ValueError('짝수 해상도 128..1920 × 96..1080, FPS 1..120, 화질 10..95 범위로 입력하세요.')
    return dict(settings)


class SettingsError(ValueError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class FrameStream:
    def __init__(self, source, *, sample=False, backend='picamera2', fps=60, quality=90, denoise=False,
                 width=1920, height=1080, source_factory=None):
        self.source, self.sample, self.backend = source, sample, backend
        self.source_factory = source_factory
        self.target_fps, self.quality = fps, quality
        self.denoise = denoise
        self.requested_width, self.requested_height = width, height
        self.condition = threading.Condition()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.frame = None
        self.frames = 0
        self.width = self.height = 0
        self.times = deque(maxlen=max(60, fps * 2))
        self.error = None
        self.thread = None
        self.pending = None
        self.settings_version = 0
        self.stream_version = 0
        self.change_id = 0
        self.change_state = 'idle'
        self.change_message = ''
        self.clients = 0

    @staticmethod
    def encode(frame, quality, denoise):
        if frame is None or frame.size == 0:
            raise RuntimeError('카메라에서 빈 프레임을 받았습니다')
        if denoise:
            # Mild spatial smoothing avoids the ghosting of frame averaging.
            frame = cv2.bilateralFilter(frame, 5, 35, 35)
        ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError('JPEG 인코딩에 실패했습니다')
        return jpeg.tobytes(), frame.shape[1], frame.shape[0]

    def publish(self, encoded):
        self.frame, self.width, self.height = encoded
        self.frames += 1
        self.times.append(time.monotonic())
        self.condition.notify_all()

    def capture(self):
        encoded = self.encode(self.source.read(), self.quality, self.denoise)
        with self.condition:
            self.publish(encoded)

    def settings(self):
        return {'width': self.requested_width, 'height': self.requested_height,
                'fps': self.target_fps, 'quality': self.quality, 'denoise': self.denoise}

    def request_settings(self, body):
        if not isinstance(body, dict) or set(body) != {'settings', 'expected_version'}:
            raise SettingsError(400, '설정과 현재 버전이 필요합니다.')
        try:
            settings = validate_settings(body['settings'])
        except ValueError as error:
            raise SettingsError(400, str(error)) from error
        version = body['expected_version']
        if type(version) is not int or version < 0:
            raise SettingsError(400, '설정 버전이 올바르지 않습니다.')
        with self.condition:
            if self.stop_event.is_set():
                raise SettingsError(503, '카메라 촬영이 중단됐습니다. 파이에서 프로그램을 다시 시작하세요.')
            if self.change_state in ('pending', 'applying'):
                raise SettingsError(409, '이미 설정을 적용 중입니다. 잠시 후 다시 시도하세요.')
            if version != self.settings_version:
                raise SettingsError(409, '다른 화면에서 설정이 변경됐습니다. 현재 설정 불러오기를 눌러주세요.')
            if self.source_factory is None and any(settings[k] != self.settings()[k] for k in ('width', 'height', 'fps')):
                raise SettingsError(400, '이 실행 모드에서는 카메라 설정 변경이 지원되지 않습니다.')
            self.pending = settings
            self.change_id += 1
            self.change_state = 'pending'
            self.change_message = '설정 적용을 기다리고 있습니다.'
            self.wake_event.set()
            return {'change_id': self.change_id}

    def open_source(self, settings):
        source = self.source_factory(settings['width'], settings['height'], settings['fps'])
        try:
            encoded = self.encode(source.read(), settings['quality'], settings['denoise'])
            return source, encoded
        except Exception:
            with suppress(Exception):
                source.close()
            raise

    def apply_pending(self):
        with self.condition:
            if self.pending is None:
                return False
            settings, self.pending = self.pending, None
            previous = self.settings()
            self.change_state = 'applying'
            self.change_message = '카메라 설정 적용 중입니다.'
            hardware = any(settings[k] != previous[k] for k in ('width', 'height', 'fps'))
            if hardware:
                self.frame = None
                self.times.clear()
        try:
            if hardware:
                # Only the producer touches the device, so clients never race
                # capture against close/reopen. A second camera is not opened first.
                self.source.close()
                source, encoded = self.open_source(settings)
            else:
                source = self.source
                encoded = self.encode(source.read(), settings['quality'], settings['denoise'])
            if self.stop_event.is_set():
                if hardware:
                    source.close()
                return True
            with self.condition:
                self.source = source
                self.requested_width, self.requested_height = settings['width'], settings['height']
                self.target_fps, self.quality, self.denoise = settings['fps'], settings['quality'], settings['denoise']
                self.times = deque(maxlen=max(60, self.target_fps * 2))
                self.publish(encoded)
                self.error = None
                self.settings_version += 1
                self.stream_version += 1
                self.change_state = 'applied'
                self.change_message = f'설정을 적용했습니다. 실제 영상 {self.width} × {self.height}.'
                if (self.width, self.height) != (settings['width'], settings['height']):
                    self.change_message += ' 요청과 다른 해상도입니다. 카메라 지원 모드를 확인하세요.'
                device_fps = getattr(source, 'device_fps', None)
                if device_fps and device_fps < self.target_fps * .9:
                    self.change_message += f' 장치가 선택한 속도는 {device_fps} FPS입니다.'
        except Exception as error:
            recovery_error = None
            if self.stop_event.is_set():
                return True
            if hardware:
                try:
                    source, encoded = self.open_source(previous)
                    with self.condition:
                        self.source = source
                        self.publish(encoded)
                        self.stream_version += 1
                except Exception as failure:
                    recovery_error = failure
            with self.condition:
                self.change_state = 'failed'
                self.change_message = f'설정 적용 실패: {error}. '
                if recovery_error:
                    self.error = f'이전 설정 복구 실패: {recovery_error}'
                    self.change_message += self.error + '. 파이에서 프로그램을 다시 시작하세요.'
                    self.stop_event.set()
                else:
                    self.change_message += '이전 설정을 유지합니다.'
                self.condition.notify_all()
        return True

    def start(self):
        # Fail before advertising a working server if the camera cannot capture.
        self.capture()
        self.thread = threading.Thread(target=self.run, name='camera-preview', daemon=True)
        self.thread.start()

    def run(self):
        try:
            while not self.stop_event.is_set():
                started = time.monotonic()
                if not self.apply_pending():
                    self.capture()
                self.wake_event.wait(max(0, 1 / self.target_fps - (time.monotonic() - started)))
                self.wake_event.clear()
        except Exception as error:
            with self.condition:
                self.error = str(error)
                self.stop_event.set()
                self.condition.notify_all()
            print(f'카메라 촬영 중단: {error}', file=sys.stderr, flush=True)

    def health(self):
        with self.condition:
            age = time.monotonic() - self.times[-1] if self.times else None
            elapsed = self.times[-1] - self.times[0] if len(self.times) > 1 else 0
            return {'sample': self.sample, 'backend': self.backend, 'width': self.width,
                    'height': self.height, 'target_fps': self.target_fps, 'frames': self.frames,
                    'requested_width': self.requested_width, 'requested_height': self.requested_height,
                    'quality': self.quality, 'denoise': self.denoise,
                    'device_fps': getattr(self.source, 'device_fps', None),
                    'jpeg_kb': round(len(self.frame) / 1024, 1) if self.frame else 0,
                    'settings_version': self.settings_version, 'stream_version': self.stream_version,
                    'change_id': self.change_id, 'change_state': self.change_state, 'change_message': self.change_message,
                    'clients': self.clients,
                    'fps': round((len(self.times) - 1) / elapsed, 1) if elapsed else 0,
                    'frame_age_seconds': round(age, 3) if age is not None else None,
                    'live': age is not None and age < 3 and not self.stop_event.is_set() and self.change_state not in ('pending', 'applying'),
                    'error': self.error}

    def next_frame(self, previous):
        with self.condition:
            self.condition.wait_for(lambda: (self.frame is not None and self.frames > previous) or self.stop_event.is_set(), timeout=3)
            if self.stop_event.is_set() or self.frame is None or self.frames <= previous:
                return None
            return self.frames, self.frame

    def close(self):
        self.stop_event.set()
        self.wake_event.set()
        with self.condition:
            self.condition.notify_all()
        if self.thread:
            self.thread.join(timeout=4)
        self.source.close()


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, stream):
        self.stream = stream
        self.control_token = secrets.token_urlsafe(24)
        super().__init__(address, PreviewHandler)


class PreviewHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            data, mime = PAGE.replace('__CONTROL_TOKEN__', json.dumps(self.server.control_token)).encode(), 'text/html; charset=utf-8'
        elif path == '/api/health':
            data, mime = json.dumps(self.server.stream.health()).encode(), 'application/json'
        elif path == '/api/frame.jpg':
            with self.server.stream.condition:
                if not self.server.stream.health()['live']:
                    self.respond(503, json.dumps({'message': '카메라의 새 프레임을 기다리고 있습니다.'}).encode())
                    return
                data, mime = self.server.stream.frame, 'image/jpeg'
            self.respond(200, data, mime, {'X-Bread-Sample': 'true' if self.server.stream.sample else 'false'})
            return
        elif path == '/stream.mjpg':
            return self.stream_video()
        else:
            self.send_error(404)
            return
        self.respond(200, data, mime)

    def respond(self, status, data, mime='application/json', headers=None):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if urlsplit(self.path).path != '/api/settings':
            self.send_error(404)
            return
        try:
            origin = self.headers.get('Origin')
            host = self.headers.get('Host', '')
            if origin and origin not in {f'http://{host}', f'https://{host}'}:
                raise SettingsError(403, '다른 사이트에서 보낸 설정 변경은 허용하지 않습니다.')
            token = self.headers.get('X-Preview-Token', '')
            if not hmac.compare_digest(token.encode(), self.server.control_token.encode()):
                raise SettingsError(403, '설정 변경 화면을 새로고침한 뒤 다시 시도하세요.')
            if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                raise SettingsError(415, 'JSON 요청이 필요합니다.')
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError as error:
                raise SettingsError(400, '요청 길이가 올바르지 않습니다.') from error
            if not 0 < length <= 4096:
                raise SettingsError(413, '설정 요청은 4096바이트 이하여야 합니다.')
            self.connection.settimeout(5)
            try:
                body = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError, TimeoutError) as error:
                raise SettingsError(400, '설정 JSON을 읽을 수 없습니다.') from error
            result = self.server.stream.request_settings(body)
            self.respond(202, json.dumps(result).encode())
        except SettingsError as error:
            self.respond(error.status, json.dumps({'message': str(error)}).encode())

    def stream_video(self):
        self.connection.settimeout(5)
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        previous = 0
        with self.server.stream.condition:
            self.server.stream.clients += 1
        try:
            while True:
                next_frame = self.server.stream.next_frame(previous)
                if next_frame is None:
                    break
                previous, frame = next_frame
                self.wfile.write(b'--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                                 str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        finally:
            with self.server.stream.condition:
                self.server.stream.clients -= 1


class PublicStreamServer(ThreadingHTTPServer):
    """Loopback-only tunnel origin: no page tokens or camera mutation endpoints."""
    daemon_threads = True

    def __init__(self, address, stream):
        self.stream = stream
        super().__init__(address, PublicStreamHandler)


class PublicStreamHandler(PreviewHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/stream.mjpg':
            self.stream_video()
        elif path == '/api/health':
            state = self.server.stream.health()
            public = {key: state[key] for key in ('sample', 'width', 'height', 'target_fps', 'fps', 'frame_age_seconds', 'live', 'clients')}
            public['read_only'] = True
            self.respond(200, json.dumps(public).encode())
        else:
            self.respond(404, json.dumps({'message': '공개 영상 경로가 아닙니다.'}).encode())

    def do_POST(self):
        self.respond(403, json.dumps({'message': '공개 영상 연결에서는 카메라 설정을 변경할 수 없습니다.'}).encode())


def parse_args():
    parser = argparse.ArgumentParser(description='같은 LAN에서 카메라 연속 영상 확인 (DB/녹화 없음)')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--public-port', type=int, default=8082, help='읽기 전용 터널 원본 포트 (항상 127.0.0.1에 바인딩)')
    parser.add_argument('--camera-backend', choices=['picamera2', 'opencv'], default='picamera2')
    parser.add_argument('--camera-index', type=int, default=0)
    parser.add_argument('--fps', type=int, default=60, help='목표 처리 출력 FPS (1..120), 실제 속도는 장치/조명/부하에 따라 다름')
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--quality', type=int, default=90, help='JPEG 품질 10..95 (기본 90)')
    parser.add_argument('--denoise', action='store_true', help='약한 공간 노이즈 제거. 처리 부하가 늘고 미세 질감이 약해질 수 있음')
    parser.add_argument('--sample', action='store_true', help='합성 영상만 사용 (실제 촬영 아님)')
    args = parser.parse_args()
    if not (1 <= args.fps <= 120 and 128 <= args.width <= 1920 and 96 <= args.height <= 1080
            and args.width % 2 == 0 and args.height % 2 == 0 and 10 <= args.quality <= 95
            and 1 <= args.port <= 65535 and 1 <= args.public_port <= 65535
            and args.public_port != args.port and args.camera_index >= 0):
        parser.error('FPS 1..120, 짝수 해상도 128..1920 × 96..1080, 품질 10..95, 포트 1..65535 필요')
    return args


def main():
    args = parse_args()
    source = stream = server = public_server = public_thread = None
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    try:
        def create_source(width, height, fps):
            return SampleSource(width, height) if args.sample else CameraSource(
                args.camera_backend, width, height, fps, args.camera_index)
        source = create_source(args.width, args.height, args.fps)
        stream = FrameStream(source, sample=args.sample, backend=args.camera_backend,
                             fps=args.fps, quality=args.quality, denoise=args.denoise,
                             width=args.width, height=args.height, source_factory=create_source)
        stream.start()
        server = PreviewServer((args.host, args.port), stream)
        public_server = PublicStreamServer(('127.0.0.1', args.public_port), stream)
        public_thread = threading.Thread(target=public_server.serve_forever, name='public-camera-readonly', daemon=True)
        public_thread.start()
        print('합성 테스트 영상입니다. 실제 카메라가 아닙니다.' if args.sample else '실제 카메라 첫 프레임 촬영 성공.', flush=True)
        health = stream.health()
        print(f'실제 프레임 {health["width"]}×{health["height"]} / 목표 {args.fps} FPS / '
              f'JPEG 품질 {args.quality} / 노이즈 제거 {"켜짐" if args.denoise else "꺼짐"}', flush=True)
        if (health['width'], health['height']) != (args.width, args.height):
            print(f'요청한 {args.width}×{args.height}와 실제 해상도가 다릅니다. '
                  '카메라 지원 모드를 확인하세요. 소프트웨어 확대는 적용하지 않습니다.', flush=True)
        print(f'같은 네트워크의 브라우저에서 http://파이IP:{args.port} 접속 (IP 확인: hostname -I)', flush=True)
        print(f'공개 터널 원본: http://127.0.0.1:{args.public_port} (영상·상태 읽기 전용)', flush=True)
        print('카메라 확인 전용 · 녹화/재고 분석 없음 · 종료 Ctrl+C', flush=True)
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        print(f'실행 실패: {error}\n기존 카메라 프로그램을 종료하고 rpicam-hello --list-cameras로 확인하세요. '
              'Picamera2는 Raspberry Pi OS의 python3-picamera2 패키지가 필요합니다. '
              'USB 웹캠이라면 --camera-backend opencv로 다시 실행하세요. '
              '카메라 실패 시 합성 영상으로 전환하지 않습니다.', file=sys.stderr)
        return 1
    finally:
        if stream:
            stream.close()
        elif source:
            source.close()
        if server:
            server.server_close()
        if public_server:
            if public_thread and public_thread.is_alive():
                public_server.shutdown()
                public_thread.join(timeout=2)
            public_server.server_close()


if __name__ == '__main__':
    raise SystemExit(main())
