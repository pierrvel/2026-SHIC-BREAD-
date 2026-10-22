#!/usr/bin/env bash
set -euo pipefail
public_port="${BREAD_PUBLIC_PORT:-8082}"
if ! [[ "$public_port" =~ ^[0-9]+$ ]] || (( public_port < 1 || public_port > 65535 )); then
  echo 'BREAD_PUBLIC_PORT must be a valid TCP port.' >&2
  exit 1
fi
if ! command -v cloudflared >/dev/null; then
  echo 'cloudflared가 필요합니다. Raspberry Pi OS용 공식 설치 안내: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/' >&2
  exit 1
fi
curl -fSs --max-time 5 "http://127.0.0.1:$public_port/api/health" | python3 -c 'import json,sys; state=json.load(sys.stdin); sys.exit(0 if state.get("read_only") is True else "읽기 전용 포트가 아닙니다. 기본 포트 8082를 사용하세요.")'
echo '읽기 전용 카메라 서버를 공유합니다. 출력되는 https://...trycloudflare.com 주소에 /stream.mjpg 를 붙여 사용하세요.'
echo '임시 주소는 재실행하면 바뀔 수 있습니다. 종료: Ctrl+C'
exec cloudflared tunnel --protocol http2 --url "http://127.0.0.1:$public_port"
