import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera_preview import CameraSource, FrameStream, PreviewServer, SampleSource


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.stream = FrameStream(SampleSource(320, 240), sample=True, fps=20)
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
