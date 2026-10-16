"""Pure, testable ROI analysis. Images are OpenCV BGR arrays; no network calls."""

import base64
import math
import re
from io import BytesIO
from typing import Any

import cv2
import numpy as np
from PIL import Image


def number(value: Any, label: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return float(value)


def validate_config(config: dict, frame_shape=None) -> dict:
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    number(config.get("threshold"), "threshold", 0, 255)
    slots = config.get("slots")
    if not isinstance(slots, dict) or not 1 <= len(slots) <= 60:
        raise ValueError("config.slots must contain 1–60 slots")
    for slot_id, slot in slots.items():
        if not isinstance(slot_id, str) or not re.fullmatch(r"slot_[A-Za-z0-9_-]+", slot_id):
            raise ValueError("slot IDs must start with slot_")
        if not isinstance(slot, dict) or not isinstance(slot.get("name"), str) or not slot["name"].strip():
            raise ValueError(f"{slot_id}: a name is required")
        if len(slot["name"]) > 60:
            raise ValueError(f"{slot_id}: name is too long")
        for key in ("x", "y", "w", "h"):
            value = slot.get(key)
            number(value, f"{slot_id}.{key}", 1 if key in ("w", "h") else 0, 8192)
            if int(value) != value:
                raise ValueError(f"{slot_id}.{key} must be an integer")
        if frame_shape is not None:
            height, width = frame_shape[:2]
            if slot["x"] + slot["w"] > width or slot["y"] + slot["h"] > height:
                raise ValueError(f"{slot_id}: ROI is outside {width}x{height} image")
    return config


def crop_roi(frame: np.ndarray, slot: dict) -> np.ndarray:
    x, y, w, h = (int(slot[key]) for key in ("x", "y", "w", "h"))
    return frame[y:y + h, x:x + w]


def encode_thumbnail(roi: np.ndarray, max_size=(160, 192), quality=55) -> str:
    image = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=quality, method=4)
    return "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def analyze_frame(frame: np.ndarray, empty_frame: np.ndarray, config: dict) -> dict:
    """Compare each ROI's mean saturation to the same ROI in a calibrated empty frame.

    hsv_score = abs(mean(S_current) - mean(S_empty)), OpenCV S range 0..255.
    A score strictly greater than threshold means stock is present.
    This heuristic requires on-site calibration; it is not object recognition.
    """
    for image in (frame, empty_frame):
        if image is None or image.size == 0 or image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            raise ValueError("Expected nonempty uint8 BGR images")
    if frame.shape != empty_frame.shape:
        raise ValueError("Camera and empty reference must have identical dimensions")
    validate_config(config, frame.shape)
    result = {}
    for slot_id, slot in config["slots"].items():
        roi = crop_roi(frame, slot)
        empty_roi = crop_roi(empty_frame, slot)
        saturation = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 1]
        empty_saturation = cv2.cvtColor(empty_roi, cv2.COLOR_BGR2HSV)[:, :, 1]
        score = float(abs(float(saturation.mean()) - float(empty_saturation.mean())))
        result[slot_id] = {
            "in_stock": score > config["threshold"],
            "hsv_score": round(score, 2),
            "thumbnail": encode_thumbnail(roi),
        }
    return result


def frame_difference(previous: np.ndarray | None, current: np.ndarray) -> float:
    if previous is None or previous.shape != current.shape:
        return 255.0
    return float(cv2.absdiff(previous, current).mean())
