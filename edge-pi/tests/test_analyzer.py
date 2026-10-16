import base64
import copy
import json
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyzer import analyze_frame, frame_difference, validate_config
from generate_sample import DEFAULT_CONFIG, generate
from main import atomic_json, process_once


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.config = {"threshold": 35, "slots": {"slot_1": {"name": "1번 칸", "x": 0, "y": 0, "w": 20, "h": 20}}}
        self.empty = np.full((20, 20, 3), 100, dtype=np.uint8)
        self.stock = np.full((20, 20, 3), (20, 100, 230), dtype=np.uint8)

    def test_empty_is_sold_out(self):
        item = analyze_frame(self.empty, self.empty, self.config)["slot_1"]
        self.assertFalse(item["in_stock"])
        self.assertEqual(item["hsv_score"], 0)

    def test_stock_and_webp_round_trip(self):
        item = analyze_frame(self.stock, self.empty, self.config)["slot_1"]
        self.assertTrue(item["in_stock"])
        self.assertGreater(item["hsv_score"], 35)
        self.assertTrue(item["thumbnail"].startswith("data:image/webp;base64,"))
        image = Image.open(BytesIO(base64.b64decode(item["thumbnail"].split(",")[1])))
        self.assertEqual(image.format, "WEBP")
        self.assertEqual(image.size, (20, 20))

    def test_reference_uses_same_roi_not_global_color(self):
        # A colorful but empty background is correctly subtracted.
        result = analyze_frame(self.stock, self.stock, self.config)["slot_1"]
        self.assertEqual(result["hsv_score"], 0)
        self.assertFalse(result["in_stock"])

    def test_threshold_equality_is_empty(self):
        red = np.full((20, 20, 3), (0, 0, 255), dtype=np.uint8)
        self.config["threshold"] = 255
        self.assertFalse(analyze_frame(red, self.empty, self.config)["slot_1"]["in_stock"])

    def test_invalid_rois_rejected(self):
        for key, value in [("x", -1), ("w", 0), ("x", 0.5), ("w", 21), ("x", True)]:
            with self.subTest(key=key, value=value):
                config = copy.deepcopy(self.config)
                config["slots"]["slot_1"][key] = value
                with self.assertRaises(ValueError):
                    analyze_frame(self.stock, self.empty, config)

    def test_invalid_thresholds_rejected(self):
        for value in [-1, 256, float("nan"), True, "35"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_config({**self.config, "threshold": value})

    def test_reference_resolution_must_match(self):
        with self.assertRaises(ValueError):
            analyze_frame(self.stock, self.empty[:10], self.config)

    def test_diff_and_unchanged_frame_skip(self):
        self.assertEqual(frame_difference(self.empty, self.empty), 0)
        self.assertGreater(frame_difference(self.empty, self.stock), 2)
        self.assertIsNone(process_once(self.stock, self.empty, self.config, self.stock, self.config, 2))

    def test_config_change_forces_analysis_without_motion(self):
        previous = copy.deepcopy(self.config)
        self.config["threshold"] = 255
        status = process_once(self.stock, self.empty, self.config, self.stock, previous, 2)
        self.assertFalse(status["slots"]["slot_1"]["in_stock"])
        self.assertRegex(status["updated_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_first_frame_publishes(self):
        self.assertIsNotNone(process_once(self.stock, self.empty, self.config, None, None, 2))

    def test_generated_machine_has_four_stocked_two_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            frame, empty = generate(Path(directory))
            status = analyze_frame(frame, empty, DEFAULT_CONFIG)
            self.assertEqual([key for key, slot in status.items() if slot["in_stock"]], ["slot_1", "slot_3", "slot_4", "slot_6"])
            self.assertLess(sum(len(slot["thumbnail"]) for slot in status.values()), 50000)

    def test_mock_cli_writes_schema_and_reloads_exported_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate(root)
            config = copy.deepcopy(DEFAULT_CONFIG)
            config["threshold"] = 255
            atomic_json(root / "config.json", config)
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "main.py"), "--once",
                                     "--sample", str(root / "sample_vending.jpg"), "--empty", str(root / "empty_vending.jpg"),
                                     "--mock-config", str(root / "config.json"), "--output", str(root / "status.json")],
                                    env={**__import__('os').environ, "MOCK_MODE": "true"}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((root / "status.json").read_text())
            self.assertEqual(set(data), {"config", "status"})
            self.assertEqual(set(data["status"]), {"updated_at", "slots"})
            self.assertFalse(any(slot["in_stock"] for slot in data["status"]["slots"].values()))


if __name__ == "__main__":
    unittest.main()
