import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import urlopen

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera_preview import CameraSource, FrameStream, PreviewServer, SampleSource, parse_args


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


class QualityTests(unittest.TestCase):
    def test_high_fps_full_hd_and_denoise_options(self):
        with patch.object(sys, 'argv', ['camera_preview.py']):
            args = parse_args()
            self.assertEqual((args.width, args.height, args.fps, args.quality), (1280, 720, 60, 90))
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
        self.stream = FrameStream(SampleSource(320, 240), sample=True, fps=20, width=320, height=240)
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

    def read_jpeg(self, response):
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
        self.assertEqual(frame.shape, (240, 320, 3))
        return jpeg

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
