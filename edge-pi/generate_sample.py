"""Generate repeatable synthetic camera fixtures, without external assets."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = {
    "threshold": 35,
    "slots": {
        f"slot_{i + 1}": {"name": f"{i + 1}번 칸", "x": 50 + (i % 3) * 170,
                          "y": 50 + (i // 3) * 200, "w": 150, "h": 180}
        for i in range(6)
    },
}


def generate(directory: Path = ROOT):
    directory.mkdir(parents=True, exist_ok=True)
    empty = Image.new("RGB", (600, 480), "#283d39")
    draw = ImageDraw.Draw(empty)
    draw.rounded_rectangle((20, 20, 580, 460), 18, fill="#182c28", outline="#71877b", width=3)
    for slot in DEFAULT_CONFIG["slots"].values():
        x, y, w, h = (slot[k] for k in ("x", "y", "w", "h"))
        draw.rectangle((x, y, x + w, y + h), fill="#555959")
        draw.rectangle((x + 3, y + h - 30, x + w - 3, y + h - 6), fill="#9a9c9b")
        for offset in range(25, h - 20, 18):
            draw.arc((x + 35, y + offset, x + 115, y + offset + 20), 0, 180, fill="#afb1af", width=2)
    stocked = empty.copy()
    draw = ImageDraw.Draw(stocked)
    colors = {0: "#eda52e", 2: "#e07031", 3: "#d19728", 5: "#91aa27"}
    for i, color in colors.items():
        slot = DEFAULT_CONFIG["slots"][f"slot_{i + 1}"]
        x, y = slot["x"], slot["y"]
        draw.rounded_rectangle((x + 9, y + 12, x + 141, y + 154), 10, fill=color, outline="#fae4af", width=2)
        draw.ellipse((x + 18, y + 30, x + 134, y + 120), fill="#aa6324")
        draw.ellipse((x + 20, y + 25, x + 130, y + 112), fill="#f4c569")
        for k in range(3):
            draw.arc((x + 33 + k * 26, y + 32, x + 51 + k * 26, y + 98), 110, 245, fill="#b07735", width=4)
        draw.rounded_rectangle((x + 20, y + 122, x + 130, y + 145), 4, fill="#fff0d1")
        draw.text((x + 56, y + 129), "BREAD", fill="#354b3e")
    empty.save(directory / "empty_vending.jpg", quality=94)
    stocked.save(directory / "sample_vending.jpg", quality=94)
    return cv2.cvtColor(np.array(stocked), cv2.COLOR_RGB2BGR), cv2.cvtColor(np.array(empty), cv2.COLOR_RGB2BGR)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-web", action="store_true")
    args = parser.parse_args()
    generate()
    if args.export_web:
        from analyzer import analyze_frame
        frame = cv2.imread(str(ROOT / "sample_vending.jpg"))
        empty = cv2.imread(str(ROOT / "empty_vending.jpg"))
        snapshot = {"config": DEFAULT_CONFIG,
                    "status": {"updated_at": "2026-10-16 13:00:00", "slots": analyze_frame(frame, empty, DEFAULT_CONFIG)}}
        web = ROOT.parent / "web-dashboard"
        (web / "src/mockSnapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (web / "src/assets").mkdir(parents=True, exist_ok=True)
        (web / "src/assets/sample_vending.jpg").write_bytes((ROOT / "sample_vending.jpg").read_bytes())
    print(f"Generated synthetic camera images in {ROOT}")


if __name__ == "__main__":
    main()
