import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera_preview import CameraSource, FrameStream, PreviewServer, PublicStreamServer, SampleSource, parse_args
from main import HTTPFrameCamera


class CameraCompatibilityTests(unittest.TestCase):
    def fake_camera(self, controls, pixel_format='RGB888'):
        camera = MagicMock()
        camera.camera_controls = controls
        camera.create_video_configuration.side_effect = lambda **kwargs: {
            **kwargs, 'controls': {'FrameDurationLimits': (33333, 33333),
                                  'NoiseReductionMode': 1, **kwargs['controls']}}
        camera.camera_configuration.return_value = {'main': {'format': pixel_format}}
        return camera

    def test_unadvertised_controls_removed_for_usb_mjpeg_and_colors_correct(self):
        camera = self.fake_camera({}, 'MJPEG')
        # Picamera2 decodes MJPEG with Pillow, returning RGB (red here).
        camera.capture_array.return_value = np.full((8, 8, 3), (255, 0, 0), dtype=np.uint8)
        with patch.dict(sys.modules, {'picamera2': SimpleNamespace(Picamera2=lambda index: camera)}):
            source = CameraSource('picamera2', 640, 480, 15, 0)
        self.assertEqual(camera.configure.call_args.args[0]['controls'], {})
        self.assertEqual(source.read()[0, 0].tolist(), [0, 0, 255])
        source.close()
        source.close()
        camera.stop.assert_called_once()
        camera.close.assert_called_once()

    def test_csi_supported_fps_control_and_bgr_frame_preserved(self):
        camera = self.fake_camera({'FrameDurationLimits': (100, 1_000_000, 33333), 'NoiseReductionMode': (0, 2, 1)})
        frame = np.full((8, 8, 3), (2, 3, 4), dtype=np.uint8)
        camera.capture_array.return_value = frame
        constructor = MagicMock(return_value=camera)
        with patch.dict(sys.modules, {'picamera2': SimpleNamespace(Picamera2=constructor)}):
            source = CameraSource('picamera2', 640, 480, 10, 1)
        constructor.assert_called_once_with(1)
        controls = camera.configure.call_args.args[0]['controls']
        self.assertEqual(controls['FrameDurationLimits'], (100000, 100000))
        self.assertEqual(controls['NoiseReductionMode'], 1)
        self.assertIs(source.read(), frame)
        source.close()

    def test_initialization_failure_releases_device_and_preserves_original_error(self):
        camera = self.fake_camera({})
        camera.start.side_effect = RuntimeError('original camera error')
        camera.close.side_effect = RuntimeError('cleanup error')
        with patch.dict(sys.modules, {'picamera2': SimpleNamespace(Picamera2=lambda index: camera)}):
            with self.assertRaisesRegex(RuntimeError, 'original camera error'):
                CameraSource('picamera2', 640, 480, 15, 0)
        camera.stop.assert_not_called()
        camera.close.assert_called_once()

    def test_opencv_usb_does_not_use_picamera_or_libcamera_controls(self):
        constructor = MagicMock(side_effect=AssertionError('Picamera2 must not be used'))
        with patch.dict(sys.modules, {'picamera2': SimpleNamespace(Picamera2=constructor)}), \
                patch('camera_preview.cv2.VideoCapture') as capture:
            capture.return_value.read.return_value = (True, np.zeros((8, 8, 3), dtype=np.uint8))
            capture.return_value.get.return_value = 30.0
            source = CameraSource('opencv', 1280, 720, 60, 2)
            capture.assert_called_once_with(2)
            settings = capture.return_value.set.call_args_list
            self.assertEqual(settings[0].args, (cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG')))
            self.assertIn(unittest.mock.call(cv2.CAP_PROP_FPS, 60), settings)
            self.assertEqual(source.device_fps, 30.0)
            self.assertEqual(source.read().shape, (8, 8, 3))
            source.close()
            capture.return_value.release.assert_called_once()
            constructor.assert_not_called()

    def test_usb_retries_30_fps_without_lowering_fhd_resolution(self):
        with patch('camera_preview.cv2.VideoCapture') as capture:
            capture.return_value.get.side_effect = [15.0, 30.0]
            source = CameraSource('opencv', 1920, 1080, 60, 0)
            settings = capture.return_value.set.call_args_list
            self.assertIn(unittest.mock.call(cv2.CAP_PROP_FPS, 60), settings)
            self.assertIn(unittest.mock.call(cv2.CAP_PROP_FPS, 30), settings)
            self.assertEqual([c.args for c in settings if c.args[0] == cv2.CAP_PROP_FRAME_WIDTH], [(cv2.CAP_PROP_FRAME_WIDTH, 1920)])
            self.assertEqual(source.device_fps, 30.0)
            source.close()


class QualityTests(unittest.TestCase):
    def test_high_fps_full_hd_and_denoise_options(self):
        with patch.object(sys, 'argv', ['camera_preview.py']):
            args = parse_args()
            self.assertEqual((args.width, args.height, args.fps, args.quality), (1920, 1080, 60, 90))
        with patch.object(sys, 'argv', ['camera_preview.py', '--fps', '60', '--width', '1920', '--height', '1080', '--denoise']):
            args = parse_args()
            self.assertTrue(args.denoise)
            self.assertEqual((args.width, args.height, args.fps), (1920, 1080, 60))

    def test_denoise_reduces_flat_region_noise_and_preserves_edge_without_mutating_source(self):
        rng = np.random.default_rng(42)
        image = np.full((96, 128, 3), 40.0)
        image[:, 64:] = 210.0
        noisy = np.clip(image + rng.normal(0, 10, image.shape), 0, 255).astype(np.uint8)
        original = noisy.copy()
        source = SimpleNamespace(read=lambda: noisy, close=lambda: None)
        plain = FrameStream(source, quality=95)
        clean = FrameStream(source, quality=95, denoise=True)
        plain.capture()
        clean.capture()
        decode = lambda stream: cv2.imdecode(np.frombuffer(stream.frame, np.uint8), cv2.IMREAD_COLOR)
        before, after = decode(plain), decode(clean)
        self.assertLess(after[10:85, 10:50].std(), before[10:85, 10:50].std() * .65)
        self.assertGreater(after[:, 80:].mean() - after[:, :48].mean(), 150)
        np.testing.assert_array_equal(noisy, original)
        self.assertTrue(clean.health()['denoise'])
        self.assertEqual(clean.health()['quality'], 95)
        self.assertGreater(clean.health()['jpeg_kb'], 0)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.stream = FrameStream(SampleSource(320, 240), sample=True, fps=20, width=320, height=240,
                                  source_factory=lambda width, height, fps: SampleSource(width, height))
        self.stream.start()
        self.server = PreviewServer(('127.0.0.1', 0), self.stream)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.stream.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def health(self):
        with urlopen(self.base + '/api/health', timeout=3) as response:
            return json.load(response)

    def read_jpeg(self, response, shape=(240, 320, 3)):
        self.assertEqual(response.readline(), b'--FRAME\r\n')
        headers = {}
        while True:
            line = response.readline()
            if line == b'\r\n':
                break
            self.assertTrue(line, 'stream closed before JPEG headers completed')
            key, value = line.decode().split(':', 1)
            headers[key.lower()] = value.strip()
        self.assertEqual(headers['content-type'], 'image/jpeg')
        jpeg = response.read(int(headers['content-length']))
        self.assertEqual(response.read(2), b'\r\n')
        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(frame.shape, shape)
        return jpeg

    def post(self, body, *, token=True, origin=None):
        headers = {'Content-Type': 'application/json', 'Origin': origin or self.base}
        if token:
            headers['X-Preview-Token'] = self.server.control_token
        request = Request(self.base + '/api/settings', data=json.dumps(body).encode(), headers=headers)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def change_body(self, **overrides):
        h = self.health()
        settings = {'width': h['requested_width'], 'height': h['requested_height'],
                    'fps': h['target_fps'], 'quality': h['quality'], 'denoise': h['denoise']}
        return {'settings': {**settings, **overrides}, 'expected_version': h['settings_version']}

    def wait_change(self, change_id):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            state = self.health()
            if state['change_id'] == change_id and state['change_state'] not in ('pending', 'applying'):
                return state
            time.sleep(.02)
        self.fail('camera settings change did not finish')

    def test_settings_apply_changes_real_encoded_dimensions_and_fps(self):
        old_source = self.stream.source
        with patch.object(old_source, 'close', wraps=old_source.close) as close:
            status, result = self.post(self.change_body(width=640, height=480, fps=60))
            self.assertEqual(status, 202)
            state = self.wait_change(result['change_id'])
            close.assert_called_once()
        self.assertEqual(state['change_state'], 'applied')
        self.assertEqual((state['width'], state['height'], state['target_fps']), (640, 480, 60))
        self.assertEqual(state['settings_version'], 1)
        self.assertTrue(state['live'])
        with urlopen(self.base + '/stream.mjpg', timeout=3) as response:
            self.read_jpeg(response, shape=(480, 640, 3))

    def test_software_settings_do_not_reopen_camera(self):
        with patch.object(self.stream, 'source_factory') as factory:
            status, result = self.post(self.change_body(quality=80, denoise=True))
            self.assertEqual(status, 202)
            state = self.wait_change(result['change_id'])
            factory.assert_not_called()
        self.assertTrue(state['denoise'])
        self.assertEqual(state['quality'], 80)

    def test_jpeg_snapshot_reuses_producer_without_opening_camera(self):
        with self.assertRaisesRegex(RuntimeError, 'Synthetic camera frames'):
            HTTPFrameCamera(self.base + '/api/frame.jpg').read()
        camera = HTTPFrameCamera(self.base + '/api/frame.jpg', allow_sample=True)
        frame = camera.read()
        self.assertEqual(frame.shape, (240, 320, 3))
        with self.assertRaises(RuntimeError):
            HTTPFrameCamera(self.base + '/api/health').read()
        with self.assertRaises(ValueError):
            HTTPFrameCamera('file:///etc/passwd')

    def test_public_origin_exposes_only_readonly_video_and_minimal_health(self):
        public = PublicStreamServer(('127.0.0.1', 0), self.stream)
        thread = threading.Thread(target=public.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{public.server_port}'
        try:
            with urlopen(base + '/api/health', timeout=3) as response:
                state = json.load(response)
                self.assertTrue(state['live'])
                self.assertNotIn('settings_version', state)
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
            for path in ['/', '/api/settings', '/api/frame.jpg']:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + path, timeout=3)
                self.assertEqual(error.exception.code, 404)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base + '/api/settings', data=b'{}', headers={'X-Preview-Token': self.server.control_token}), timeout=3)
            self.assertEqual(error.exception.code, 403)
            with urlopen(base + '/stream.mjpg', timeout=3) as response:
                self.read_jpeg(response)
        finally:
            public.shutdown()
            public.server_close()
            thread.join(timeout=2)

    def test_settings_require_page_token_and_same_origin(self):
        body = self.change_body(fps=30)
        self.assertEqual(self.post(body, token=False)[0], 403)
        self.assertEqual(self.post(body, origin='https://unrelated.example')[0], 403)
        self.assertEqual(self.health()['settings_version'], 0)

    def test_invalid_settings_rejected_without_touching_camera(self):
        with patch.object(self.stream, 'source_factory') as factory:
            for changes in ({'fps': 121}, {'fps': True}, {'width': 641}, {'width': 9000},
                            {'quality': 96}, {'denoise': 'true'}, {'unknown': 1}):
                self.assertEqual(self.post(self.change_body(**changes))[0], 400)
            self.assertEqual(self.post({'settings': {}, 'expected_version': False})[0], 400)
            factory.assert_not_called()
        self.assertEqual(self.health()['settings_version'], 0)

    def test_failed_reopen_restores_previous_camera_settings_and_keeps_stream_live(self):
        calls = []
        def factory(width, height, fps):
            calls.append((width, height, fps))
            if width == 640:
                raise RuntimeError('unsupported device mode')
            return SampleSource(width, height)
        self.stream.source_factory = factory
        status, result = self.post(self.change_body(width=640, height=480, fps=30))
        self.assertEqual(status, 202)
        state = self.wait_change(result['change_id'])
        self.assertEqual(state['change_state'], 'failed')
        self.assertEqual(calls, [(640, 480, 30), (320, 240, 20)])
        self.assertEqual(state['settings_version'], 0)
        self.assertEqual((state['width'], state['height']), (320, 240))
        self.assertIn('unsupported device mode', state['change_message'])
        self.assertTrue(state['live'])
        self.assertIsNone(state['error'])
        with urlopen(self.base + '/stream.mjpg', timeout=3) as response:
            self.read_jpeg(response)

    def test_bad_first_frame_releases_candidate_before_restoring_camera(self):
        bad = SimpleNamespace(read=lambda: None, close=MagicMock())
        self.stream.source_factory = lambda w, h, f: bad if w == 640 else SampleSource(w, h)
        _, result = self.post(self.change_body(width=640, height=480))
        state = self.wait_change(result['change_id'])
        bad.close.assert_called_once()
        self.assertEqual(state['change_state'], 'failed')
        self.assertTrue(state['live'])

    def test_failed_rollback_is_reported_and_server_remains_responsive(self):
        self.stream.source_factory = MagicMock(side_effect=RuntimeError('device unavailable'))
        _, result = self.post(self.change_body(width=640, height=480))
        state = self.wait_change(result['change_id'])
        self.assertEqual(state['change_state'], 'failed')
        self.assertFalse(state['live'])
        self.assertIn('복구 실패', state['error'])
        self.assertEqual(self.post(self.change_body(fps=30))[0], 503)

    def test_busy_change_and_stale_version_rejected(self):
        entered, release = threading.Event(), threading.Event()
        def factory(width, height, fps):
            entered.set()
            release.wait(timeout=3)
            return SampleSource(width, height)
        self.stream.source_factory = factory
        body = self.change_body(width=640, height=480)
        try:
            _, result = self.post(body)
            self.assertTrue(entered.wait(timeout=2))
            self.assertEqual(self.post(body)[0], 409)
        finally:
            release.set()
        self.assertEqual(self.wait_change(result['change_id'])['change_state'], 'applied')
        self.assertEqual(self.post(body)[0], 409)

    def test_continuous_jpegs_and_multiple_clients_share_source(self):
        with urlopen(self.base + '/stream.mjpg', timeout=3) as first, urlopen(self.base + '/stream.mjpg', timeout=3) as second:
            self.assertIn('boundary=FRAME', first.headers['Content-Type'])
            jpeg1 = self.read_jpeg(first)
            jpeg2 = self.read_jpeg(first)
            self.assertNotEqual(jpeg1, jpeg2)
            self.read_jpeg(second)
        self.assertTrue(self.health()['live'])

    def test_health_reports_advancing_frames_actual_size_and_stopped_state(self):
        first = self.health()
        self.assertTrue(first['sample'])
        self.assertEqual((first['width'], first['height']), (320, 240))
        time.sleep(.15)
        latest = self.health()
        self.assertGreater(latest['frames'], first['frames'])
        self.assertGreater(latest['fps'], 0)
        self.stream.close()
        self.assertFalse(self.health()['live'])
        self.assertFalse(self.stream.thread.is_alive())

    def test_capture_failure_stops_stream_instead_of_silent_sample_fallback(self):
        with patch.object(self.stream.source, 'read', side_effect=RuntimeError('camera disconnected')):
            self.stream.thread.join(timeout=2)
        state = self.health()
        self.assertFalse(state['live'])
        self.assertEqual(state['error'], 'camera disconnected')
        self.assertIsNone(self.stream.next_frame(0))

    def test_missing_camera_never_constructs_sample(self):
        with patch('camera_preview.cv2.VideoCapture') as capture, patch('camera_preview.SampleSource') as sample:
            capture.return_value.isOpened.return_value = False
            with self.assertRaises(RuntimeError):
                CameraSource('opencv', 320, 240, 15, 0)
            capture.return_value.release.assert_called_once()
            sample.assert_not_called()

    def test_page_and_private_paths(self):
        with urlopen(self.base, timeout=3) as response:
            page = response.read().decode()
            self.assertIn('합성 테스트 영상', page)
            self.assertIn('/stream.mjpg', page)
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + '/camera_preview.py', timeout=3)
        self.assertEqual(caught.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
