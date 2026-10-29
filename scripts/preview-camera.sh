#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
backend=opencv
sample_mode=0
previous_arg=''
for arg in "$@"; do
  if [[ "$previous_arg" == '--camera-backend' ]]; then backend="$arg"; fi
  if [[ "$arg" == --camera-backend=* ]]; then backend="${arg#*=}"; fi
  if [[ "$arg" == '--sample' ]]; then sample_mode=1; fi
  if [[ "$arg" == '--help' || "$arg" == '-h' ]]; then
    echo '재빵소 USB 웹캠: bash scripts/preview-camera.sh [--camera-index 0] [--fps 60] [--denoise]'
    echo '기본: 1920×1080, 목표 60 FPS, JPEG 품질 90. 실제 속도는 장치 지원에 따릅니다.'
    echo '관리자: 8081 / 읽기 전용 터널 원본: 127.0.0.1:8082'
    echo 'CSI 카메라: --camera-backend picamera2 / 합성 테스트만: --sample'
    exit 0
  fi
  previous_arg="$arg"
done
if [[ -n "${BREAD_PYTHON:-}" ]]; then
  pi_python="$BREAD_PYTHON"
else
  system_python=/usr/bin/python3
  if [[ ! -x "$system_python" ]]; then system_python="$(command -v python3)"; fi
  imports='import cv2, numpy, venv, ensurepip'
  packages=(python3-venv python3-opencv python3-numpy)
  if [[ "$sample_mode" == 0 && "$backend" != opencv ]]; then
    imports+='; from picamera2 import Picamera2'
    packages+=(python3-picamera2)
  fi
  if ! "$system_python" -c "$imports" 2>/dev/null; then
    if ! command -v apt-get >/dev/null; then
      echo 'Raspberry Pi OS에서 실행하거나, OpenCV/numpy가 설치된 Python을 BREAD_PYTHON으로 지정하세요.' >&2
      exit 1
    fi
    privilege=()
    if [[ "$EUID" != 0 ]]; then privilege=(sudo); fi
    "${privilege[@]}" apt-get update
    "${privilege[@]}" apt-get install -y "${packages[@]}"
  fi
  if [[ ! -x .venv-pi/bin/python ]]; then
    "$system_python" -m venv --system-site-packages .venv-pi
  fi
  pi_python="$repo_dir/.venv-pi/bin/python"
fi
"$pi_python" -c 'import sys; assert sys.version_info >= (3,10), "Python >=3.10 required"; import cv2, numpy'
exec "$pi_python" edge-pi/camera_preview.py --camera-backend "$backend" "$@"
