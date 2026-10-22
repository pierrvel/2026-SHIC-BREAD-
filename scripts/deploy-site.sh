#!/usr/bin/env bash
set -euo pipefail
site_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$site_dir"
if ! command -v npx >/dev/null; then
  echo '배포용 Mac/PC에 Node.js LTS가 필요합니다: https://nodejs.org/ (파이 카메라 실행에는 필요하지 않습니다.)' >&2
  exit 1
fi
if [[ ! -f web-dashboard/dist/index.html || ! -f web-dashboard/dist/public-build.json ]]; then
  echo '게시용 빌드가 없습니다. npm --prefix web-dashboard run build:public 을 먼저 실행하세요.' >&2
  exit 1
fi
node -e 'const c=require("./web-dashboard/dist/public-build.json");if(c.hosting!=="cloudflare-pages"||c.mode!=="camera"||c.mockMode!==false||c.inventoryEnabled!==false)process.exit(1)'
echo 'Cloudflare Pages의 bread-notificator 프로젝트에 정적 사이트를 배포합니다.'
exec npx --yes wrangler@latest pages deploy web-dashboard/dist --project-name bread-notificator --branch main
