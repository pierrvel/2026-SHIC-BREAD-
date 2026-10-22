"""30-second camera → ROI analyzer → Firebase Realtime Database edge worker."""

import argparse
import json
import logging
import math
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from urllib.request import urlopen

import cv2
import numpy as np

from analyzer import analyze_frame, frame_difference, validate_config
from generate_sample import DEFAULT_CONFIG, generate

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("bread.edge")


def env_flag(name, default):
    value = os.getenv(name, str(default)).lower()
    if value not in ("true", "false", "1", "0"):
        raise ValueError(f"{name} must be true/false or 1/0")
    return value in ("true", "1")


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


class HTTPFrameCamera:
    """Reuse the live camera producer instead of opening the USB device twice."""
    def __init__(self, url, allow_sample=False):
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('CAMERA_URL must be an HTTP(S) snapshot URL without credentials')
        self.url = url
        self.allow_sample = allow_sample

    def read(self):
        with urlopen(self.url, timeout=5) as response:
            if response.headers.get('X-Bread-Sample') == 'true' and not self.allow_sample:
                raise RuntimeError('Synthetic camera frames cannot be used as real inventory input')
            if response.headers.get_content_type() != 'image/jpeg':
                raise RuntimeError('Camera snapshot endpoint did not return JPEG')
            data = response.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise RuntimeError('Camera snapshot exceeds 16 MiB')
        frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError('Camera snapshot could not be decoded')
        return frame

    def close(self):
        pass


class Camera:
    def __init__(self, backend="auto", index=0):
        if backend not in ("auto", "picamera2", "opencv"):
            raise ValueError("CAMERA_BACKEND must be auto, picamera2 or opencv")
        self.index = index
        self.picamera = None
        self.capture = None
        if backend in ("auto", "picamera2"):
            try:
                from picamera2 import Picamera2
            except ImportError:
                if backend == "picamera2":
                    raise RuntimeError("Install Raspberry Pi OS python3-picamera2; see README")
            else:
                self.picamera = Picamera2()
                # Picamera2's RGB888 buffer is B,G,R in numpy, as expected by OpenCV.
                configuration = self.picamera.create_still_configuration(main={"size": (1280, 960), "format": "RGB888"})
                self.picamera.configure(configuration)
                self.picamera.start()
                time.sleep(2)
        if self.picamera is None:
            self.capture = cv2.VideoCapture(index)
            if not self.capture.isOpened():
                self.close()
                raise RuntimeError("Camera unavailable. Check libcamera/Picamera2 or use MOCK_MODE=true")

    def read(self):
        if self.picamera is not None:
            return self.picamera.capture_array("main")
        # Reopen the USB stream on every sample to avoid a 30s-old buffered frame.
        self.capture.release()
        if not self.capture.open(self.index):
            raise RuntimeError("Could not reopen camera")
        for _ in range(4):
            ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError("Camera frame read failed")
        return frame

    def close(self):
        if self.picamera is not None:
            self.picamera.stop()
            self.picamera.close()
        if self.capture is not None:
            self.capture.release()

class FirebaseStore:
    def __init__(self):
        import firebase_admin
        from firebase_admin import credentials, db
        url = os.getenv("FIREBASE_DATABASE_URL")
        if not url:
            raise ValueError("FIREBASE_DATABASE_URL is required in live mode")
        # GOOGLE_APPLICATION_CREDENTIALS or the machine's existing ADC binding.
        self.app = firebase_admin.initialize_app(credentials.ApplicationDefault(), {"databaseURL": url, "httpTimeout": 15})
        self.config_ref = db.reference("config", app=self.app)
        self.status_ref = db.reference("status", app=self.app)

    def config(self):
        return self.config_ref.get()

    def publish(self, status):
        self.status_ref.set(status)


def process_once(frame, empty, config, previous_frame, previous_config, diff_threshold):
    validate_config(config, frame.shape)
    if config == previous_config and frame_difference(previous_frame, frame) < diff_threshold:
        return None
    return {"updated_at": datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S"),
            "slots": analyze_frame(frame, empty, config)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="One iteration; fail with a nonzero exit code on error")
    parser.add_argument("--interval", type=float, default=float(os.getenv("CAPTURE_INTERVAL", "30")))
    parser.add_argument("--camera-url", default=os.getenv('CAMERA_URL'), help='Read JPEG snapshots from the running live camera producer')
    parser.add_argument("--sample", type=Path, default=Path(os.getenv("SAMPLE_IMAGE_PATH", ROOT / "sample_vending.jpg")))
    parser.add_argument("--empty", type=Path, default=Path(os.getenv("EMPTY_IMAGE_PATH", ROOT / "empty_vending.jpg")))
    parser.add_argument("--mock-config", type=Path, help="Read exported config JSON at every mock iteration")
    parser.add_argument("--output", type=Path, default=ROOT / "mock-state.json")
    parser.add_argument("--calibrate-empty", action="store_true", help="Capture a fully empty machine to --empty, then exit")
    args = parser.parse_args()
    mock = env_flag("MOCK_MODE", True)
    if mock and args.camera_url:
        parser.error('--camera-url requires MOCK_MODE=false')
    diff_threshold = float(os.getenv("DIFF_THRESHOLD", "2.0"))
    if not math.isfinite(args.interval) or args.interval <= 0 or not math.isfinite(diff_threshold) or not 0 <= diff_threshold <= 255:
        parser.error("interval must be positive; DIFF_THRESHOLD must be between 0 and 255")
    camera = None
    try:
        if not mock:
            camera = HTTPFrameCamera(args.camera_url) if args.camera_url else Camera(os.getenv("CAMERA_BACKEND", "auto"), int(os.getenv("CAMERA_INDEX", "0")))
        if args.calibrate_empty:
            if mock:
                parser.error("Calibration requires MOCK_MODE=false and a fully empty machine")
            if args.empty.exists():
                raise ValueError("Empty reference already exists; choose a new --empty path to preserve it")
            args.empty.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(args.empty), camera.read()):
                raise RuntimeError("Could not save empty reference")
            LOG.info("Saved empty reference: %s", args.empty)
            return
        if mock and (not args.sample.exists() or not args.empty.exists()):
            if args.sample == ROOT / "sample_vending.jpg" and args.empty == ROOT / "empty_vending.jpg":
                if args.sample.exists() or args.empty.exists():
                    raise ValueError("Only one fixture exists; explicitly regenerate or provide a matching pair")
                generate()
            else:
                raise ValueError("Requested sample/reference image does not exist")
        empty = cv2.imread(str(args.empty))
        if empty is None:
            raise ValueError("Empty reference cannot be read. Calibrate with --calibrate-empty first")
        store = None if mock else FirebaseStore()
        LOG.info("Mode: %s; interval: %ss", "MOCK (local JSON only)" if mock else "FIREBASE", args.interval)
        previous_frame = previous_config = None
        while True:
            started = time.monotonic()
            try:
                config = (json.loads(args.mock_config.read_text(encoding="utf-8")) if args.mock_config else DEFAULT_CONFIG) if mock else store.config()
                frame = cv2.imread(str(args.sample)) if mock else camera.read()
                if frame is None:
                    raise ValueError("Sample image cannot be read")
                status = process_once(frame, empty, config, previous_frame, previous_config, diff_threshold)
                if status is not None:
                    if mock:
                        atomic_json(args.output, {"config": config, "status": status})
                    else:
                        store.publish(status)
                    # Only advance after a successful write: failed uploads are retried.
                    previous_frame = frame.copy()
                    previous_config = json.loads(json.dumps(config))
                    LOG.info("Published %s slots (%s stocked)", len(status["slots"]), sum(s["in_stock"] for s in status["slots"].values()))
                else:
                    LOG.info("No image/config change; skipped analysis and status upload")
            except Exception as error:
                # Log type only: SDK exceptions may contain URLs or credential-bearing input.
                LOG.error("Iteration failed (%s); check camera, ROI/config and database access", type(error).__name__)
                if args.once:
                    raise
            if args.once:
                break
            time.sleep(max(0, args.interval - (time.monotonic() - started)))
    finally:
        if camera is not None:
            camera.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        main()
    except KeyboardInterrupt:
        LOG.info("Stopped")
