#!/usr/bin/env bash
set -euo pipefail
cd /workspace/2026-SHIC-BREAD-
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python >=3.10 required"'
node -e 'const [a,b]=process.versions.node.split(".").map(Number); if(a<20 || (a===20 && b<19)) throw Error("Node >=20.19 required")'
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
PIP_CACHE_DIR=/tmp/school-bread-pip-cache .venv/bin/python -m pip install --disable-pip-version-check -r edge-pi/requirements.txt
if [ ! -e edge-pi/sample_vending.jpg ] && [ ! -e edge-pi/empty_vending.jpg ]; then
  .venv/bin/python edge-pi/generate_sample.py
fi
if [ ! -f edge-pi/sample_vending.jpg ] || [ ! -f edge-pi/empty_vending.jpg ]; then
  echo 'A sample/reference image is missing. Preserve existing images and supply a matching pair.' >&2
  exit 1
fi
MOCK_MODE=true .venv/bin/python edge-pi/main.py --once
.venv/bin/python -m unittest discover -s edge-pi/tests -v
npm --prefix web-dashboard ci --cache /tmp/school-bread-npm-cache --no-audit --no-fund
npm --prefix web-dashboard run build
npm --prefix web-dashboard run build:preview
.venv/bin/python scripts/package-pi.py
