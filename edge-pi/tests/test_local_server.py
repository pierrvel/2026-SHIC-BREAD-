import copy
import http.cookiejar
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import LocalServer, LocalState


class LocalServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.web = self.root / 'web'
        self.web.mkdir()
        (self.web / 'index.html').write_text('<!doctype html><html><head></head><body>School bread</body></html>')
        password = self.root / 'test-password'
        password.write_text('local-test-password-only')
        self.state = LocalState(self.root / 'data', sample=True)
        self.state.refresh()
        self.server = LocalServer(('127.0.0.1', 0), self.state, self.web, password)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.browser = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.state.stop()
        self.temporary.cleanup()

    def request(self, path, body=None, origin=None):
        headers = {}
        if body is not None:
            headers = {'Content-Type': 'application/json', 'Origin': origin or self.base}
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with self.browser.open(request, timeout=5) as response:
                data = response.read()
                return response.status, data, response.headers
        except HTTPError as error:
            with error:
                return error.code, error.read(), error.headers

    def login(self):
        status, _, headers = self.request('/api/login', {'password': 'local-test-password-only'})
        self.assertEqual(status, 200)
        return headers

    def test_student_state_is_analyzed_not_browser_fixture(self):
        status, body, _ = self.request('/api/state')
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(sum(slot['in_stock'] for slot in data['status']['slots'].values()), 4)
        self.assertTrue(data['meta']['sample'])
        self.assertEqual(set(data['status']), {'slots', 'updated_at'})
        self.assertTrue(all(slot['thumbnail'].startswith('data:image/webp;base64,') for slot in data['status']['slots'].values()))

    def test_browser_receives_runtime_config_and_private_files_are_not_served(self):
        status, body, _ = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'window.__BREAD_RUNTIME__={"mode": "local", "sample": true}', body)
        self.assertEqual(self.request('/server.py')[0], 404)
        self.assertEqual(self.request('/../admin-password')[0], 404)
        self.assertEqual(self.request('/api/frame.jpg')[0], 401)

    def test_config_and_calibration_require_login(self):
        self.assertEqual(self.request('/api/config', {'config': self.state.config})[0], 401)
        self.assertEqual(self.request('/api/calibrate', {'confirmEmpty': True})[0], 401)
        self.assertEqual(self.request('/api/capture', {})[0], 401)

    def test_session_cookie_login_frame_and_logout(self):
        headers = self.login()
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertTrue(json.loads(self.request('/api/session')[1])['admin'])
        status, body, _ = self.request('/api/frame.jpg')
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b'\xff\xd8'))
        self.assertEqual(self.request('/api/logout', {})[0], 200)
        self.assertEqual(self.request('/api/frame.jpg')[0], 401)

    def test_saved_config_reanalyzes_and_survives_restart(self):
        self.login()
        old = copy.deepcopy(self.state.config)
        new = {**old, 'threshold': 255}
        self.assertEqual(self.request('/api/config', {'config': new, 'expectedConfig': old})[0], 200)
        self.assertIsNone(self.state.status)
        self.state.refresh()
        self.assertFalse(any(slot['in_stock'] for slot in self.state.status['slots'].values()))
        restored = LocalState(self.root / 'data', sample=True)
        self.assertEqual(restored.config['threshold'], 255)
        self.assertIsNone(restored.status)  # A previous boot's status is not current.

    def test_concurrent_configuration_conflict(self):
        self.login()
        old = copy.deepcopy(self.state.config)
        new = {**old, 'threshold': 45}
        self.assertEqual(self.request('/api/config', {'config': new, 'expectedConfig': old})[0], 200)
        self.assertEqual(self.request('/api/config', {'config': old, 'expectedConfig': old})[0], 409)
        self.assertEqual(self.state.config['threshold'], 45)

    def test_roi_bounds_and_cross_origin_writes_rejected(self):
        self.login()
        old = copy.deepcopy(self.state.config)
        bad = copy.deepcopy(old)
        bad['slots']['slot_1']['x'] = 590
        self.assertEqual(self.request('/api/config', {'config': bad, 'expectedConfig': old})[0], 400)
        self.assertEqual(self.request('/api/config', {'config': old, 'expectedConfig': old}, origin='https://other.example')[0], 403)
        self.assertEqual(self.state.config, old)

    def test_calibration_requires_confirmation_and_uses_a_fresh_capture(self):
        self.login()
        self.assertEqual(self.request('/api/calibrate', {})[0], 400)
        original = cv2.imread(str(self.state.sample_image))
        empty = cv2.imread(str(self.state.empty_image))
        cv2.imwrite(str(self.state.sample_image), empty)  # Current camera image changed since last refresh.
        self.assertEqual(self.request('/api/calibrate', {'confirmEmpty': True})[0], 200)
        self.state.refresh()
        self.assertFalse(any(slot['in_stock'] for slot in self.state.status['slots'].values()))
        self.assertTrue(self.state.empty_image.with_suffix('.previous.jpg').exists())
        cv2.imwrite(str(self.state.sample_image), original)
        self.state.refresh()
        self.assertEqual(sum(slot['in_stock'] for slot in self.state.status['slots'].values()), 4)

    def test_failed_login_is_rate_limited(self):
        for _ in range(5):
            self.assertEqual(self.request('/api/login', {'password': 'incorrect'})[0], 401)
        self.assertEqual(self.request('/api/login', {'password': 'incorrect'})[0], 429)

    def test_real_mode_has_no_sample_fallback(self):
        real = LocalState(self.root / 'real', sample=False)
        with patch('server.Camera', side_effect=RuntimeError('test: no physical camera')):
            with self.assertRaises(RuntimeError):
                real.refresh()
        self.assertFalse(real.snapshot()['meta']['sample'])
        self.assertIsNone(real.snapshot()['status'])
        self.assertFalse((self.root / 'real/fixtures').exists())


if __name__ == '__main__':
    unittest.main()
