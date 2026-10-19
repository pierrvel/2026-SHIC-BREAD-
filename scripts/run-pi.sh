#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

sample_mode=0
camera_backend=picamera2
previous_arg=''
for arg in "$@"; do
  if [[ "$arg" == '--sample' ]]; then sample_mode=1; fi
  if [[ "$previous_arg" == '--camera-backend' ]]; then camera_backend="$arg"; fi
  if [[ "$arg" == '--help' || "$arg" == '-h' ]]; then
    echo 'Usage: bash scripts/run-pi.sh [--sample] [--port 8000] [--interval 30] [--camera-backend opencv]'
    echo 'Default: real Pi camera. --sample explicitly selects synthetic images.'
    echo 'Web files are included; Node.js/npm and Firebase are not required for this LAN mode.'
    exit 0
  fi
  previous_arg="$arg"
done

if [[ ! -f edge-pi/web/index.html ]]; then
  echo 'Prebuilt web files are missing. Download/pull the complete latest repository.' >&2
  exit 1
fi

if [[ -n "${BREAD_PYTHON:-}" ]]; then
  pi_python="$BREAD_PYTHON"
else
  system_python=/usr/bin/python3
  if [[ ! -x "$system_python" ]]; then system_python="$(command -v python3)"; fi
  import_check='import cv2, numpy; from PIL import Image, features; assert features.check("webp")'
  packages=(python3-venv python3-opencv python3-numpy python3-pil)
  if [[ "$sample_mode" == 0 && "$camera_backend" != opencv ]]; then
    import_check+='; from picamera2 import Picamera2'
    packages+=(python3-picamera2)
  fi
  if ! "$system_python" -c "$import_check" 2>/dev/null || ! "$system_python" -c 'import venv, ensurepip' 2>/dev/null; then
    if ! command -v apt-get >/dev/null; then
      echo 'Automatic dependency installation supports Raspberry Pi OS (apt). Set BREAD_PYTHON to an already configured Python interpreter on other systems.' >&2
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

"$pi_python" -c 'import sys; assert sys.version_info >= (3,10), "Python >=3.10 required"; import cv2, numpy; from PIL import Image, features; assert features.check("webp"), "Pillow WebP support is required"'
if [[ "$sample_mode" == 0 && "$camera_backend" != opencv ]]; then
  "$pi_python" -c 'from picamera2 import Picamera2'
fi
echo '웹 서버와 분석기를 함께 시작합니다. 접속할 파이 IP는 다른 터미널에서 hostname -I 로 확인하세요.'
echo '기본 웹 포트: 8000 / 종료: Ctrl+C'
echo '기본 관리자 비밀번호 확인: cat ~/.local/share/school-bread/admin-password'
exec "$pi_python" edge-pi/server.py --camera-backend "$camera_backend" "$@"
