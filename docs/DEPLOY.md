# 재빵소 · Cloudflare Pages와 실시간 카메라 연결

현재 사이트는 카메라 한 대의 실시간 화면을 보여줍니다. 슬롯 지도·자동 재고·로그인·Firebase 설정은 필요하지 않습니다.

```text
GitHub main → Cloudflare Pages → 학생 브라우저의 재빵소 화면
USB 웹캠 → Raspberry Pi → Cloudflare Tunnel → 같은 화면 안의 실시간 영상
```

Pages가 제공하는 사이트 주소와 파이의 영상 주소는 서로 다릅니다. 사이트는 정적 파일이고, 영상은 브라우저가 파이에서 직접 받습니다. 파이와 카메라 프로그램·터널이 켜져 있어야 영상이 나옵니다.

## 1. 사이트 게시

### GitHub 연결 — 기존 빌드 설정 유지 가능

Cloudflare에서 **Workers & Pages → Pages 만들기 → Git 저장소 연결**을 선택합니다. 기존 Pages 프로젝트가 연결되어 있다면 새로 만들지 말고 아래 설정을 확인합니다.

| 설정 | 값 |
| --- | --- |
| 저장소 | `pierrvel/2026-SHIC-BREAD-` |
| 프로덕션 브랜치 | `main` |
| 프레임워크 프리셋 | 없음 |
| 루트 디렉터리 | 비워 두기 — 저장소 루트 |
| 빌드 명령 | `npm --prefix web-dashboard ci && npm --prefix web-dashboard run build:public` |
| 출력 디렉터리 | `web-dashboard/dist` |
| 환경 변수 | `NODE_VERSION=22` |

프로젝트 이름은 원하는 사용 가능한 이름을 선택합니다. 기존 `bread-notificator` 프로젝트를 쓰더라도 화면 브랜딩은 재빵소입니다. 실제 `pages.dev` 주소는 배포 결과에서 확인합니다. GitHub 앱이 해당 저장소에 접근할 권한이 필요합니다.

영상 주소가 이미 있으면 프로덕션 환경 변수 **`VITE_CAMERA_STREAM_URL`**에 실제 HTTPS MJPEG 주소 전체를 입력합니다. 예: `https://실제-영상-호스트/stream.mjpg`. 아직 주소가 없다면 비워 두고 사이트부터 게시할 수 있습니다. Firebase 환경 변수는 입력하지 않습니다.

저장·배포 후 재빵소 간판과 **개업 준비중** 화면이 나오면 사이트는 열린 것입니다. 실제 영상이 수신되면 팻말이 **영업중**, 합성 카메라로 테스트하면 **테스트중**으로 바뀝니다. 최초 Pages 연결을 끝낸 뒤에는 GitHub `main`의 새 푸시마다 자동 배포됩니다.

### ZIP 직접 업로드

GitHub 연결 없이 게시하려면 저장소의 **`jaebbangso-site.zip`**을 내려받아 Cloudflare Pages의 **직접 업로드**에 올립니다. ZIP 루트에 게시용 `index.html`이 있습니다. 저장소 전체 ZIP이나 Git 번들을 Pages에 올리지는 않습니다.

직접 업로드는 완성된 빌드를 올리는 방식이므로 Pages에 환경 변수만 추가해도 ZIP 내용이 바뀌지 않습니다. 카메라 설정은 해당 브라우저에서 시험할 수 있습니다. 모든 방문자에게 공통 주소를 제공하려면 아래처럼 다시 빌드한 ZIP을 올리거나 Git 자동 빌드를 사용하세요.

```bash
npm --prefix web-dashboard ci
VITE_CAMERA_STREAM_URL=https://실제-영상-호스트/stream.mjpg npm --prefix web-dashboard run build:public
python3 scripts/package-site.py
```

`VITE_` 값은 브라우저에 공개됩니다. 카메라 주소에 비밀번호·API 토큰을 넣지 않습니다. CLI 직접 배포를 사용할 경우 자신의 PC에서 `npx --yes wrangler@latest login` 후 `bash scripts/deploy-site.sh`를 실행합니다. 스크립트와 `wrangler.jsonc`의 기본 프로젝트명은 `bread-notificator`이므로 실제 프로젝트명이 다르면 맞춰야 합니다.

## 2. 파이에서 실제 영상 실행

최신 `jaebbangso-pi.zip`을 새 폴더에 풀고 그 안의 `jaebbangso-pi` 폴더로 이동하거나, 저장소를 업데이트합니다. 저장소를 사용하는 경우:

```bash
cd ~/school-bread
git pull --ff-only
bash scripts/preview-camera.sh
```

기본은 **USB 웹캠 / FHD 1920×1080 / 목표 60 FPS / JPEG 품질 90**입니다. 카메라가 1080p 30 FPS까지만 지원하면 실제 촬영을 60 FPS로 만들 수 없습니다. 해상도를 자동으로 낮추지는 않으며 장치 설정 FPS와 처리 출력 FPS를 관리자 화면에서 확인합니다.

같은 네트워크에서 **`http://파이IP:8081`**을 열어 움직이는 영상을 확인합니다. 파이 자체에서는 `http://localhost:8081`입니다. 이 화면에서 FPS 30..60, JPEG 화질, 노이즈 제거를 바꿀 수 있습니다. 설정은 현재 실행에 적용되며 다음 시작값은 명령줄 옵션을 따릅니다.

```bash
# 다른 USB 장치 또는 노이즈 제거
bash scripts/preview-camera.sh --camera-index 1 --denoise
# CSI 카메라를 사용하는 경우에만
bash scripts/preview-camera.sh --camera-backend picamera2
```

실행기는 Raspberry Pi OS의 OpenCV/numpy를 사용하며 필요하면 OS 패키지 설치를 진행합니다. Node/npm, Firebase 키, 재고 분석기는 설치·실행하지 않습니다. 연결 실패를 합성 영상으로 대체하지 않습니다. 테스트할 때만 `--sample`을 명시합니다.

## 3. 공개 HTTPS 영상 주소

파이에 [공식 cloudflared](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/)를 설치합니다. 카메라 터미널을 유지하고 **다른 파이 터미널**에서 같은 폴더로 이동한 뒤:

```bash
bash scripts/share-camera.sh
```

1. 출력되는 실제 `https://…trycloudflare.com` 주소를 복사합니다.
2. 뒤에 **`/stream.mjpg`**를 붙입니다.
3. 전체 주소를 Mac·휴대폰 브라우저에서 열어 움직이는 영상인지 확인합니다.
4. 사이트 아래 **카메라 설정 → MJPEG 스트리밍 HTTPS 주소 → 저장하고 연결**로 시험합니다.
5. 모든 방문자에게 적용하려면 Pages 프로덕션의 `VITE_CAMERA_STREAM_URL`에 등록하고 **배포를 다시 빌드**합니다. 환경 변수 수정만으로 기존 빌드가 갱신되지는 않습니다.

카메라 설정에서 직접 저장한 주소는 **해당 브라우저에만** 적용되며 공통 주소보다 우선합니다. 예전 빵살핌/재빵소 HTML에서 저장한 주소도 유효하면 이어 씁니다. **저장한 주소 지우기**는 예전 저장값까지 지우고 현재 배포의 기본 주소로 돌아갑니다. 저장소를 사용할 수 없는 미리보기에서도 현재 창에서는 연결할 수 있습니다.

임시 터널을 종료하면 영상이 끊기고, 다시 실행하면 주소가 달라질 수 있습니다. 바뀐 주소를 공통으로 적용하려면 환경 변수 수정과 재배포가 필요합니다. 지속 운영 시 자신의 도메인을 Cloudflare에 연결하고 고정 터널을 설정합니다. 터널의 공개 호스트에 연결하는 서비스는 **HTTP / `localhost:8082`**입니다. Pages의 `pages.dev` 주소 자체를 카메라 터널 주소로 쓸 수는 없습니다.

**8082는 영상·상태 읽기 전용 원본이고, 8081은 카메라 설정 화면입니다. 공개 터널은 8082에만 연결합니다.**

## 4. 화면 동작 확인

- 실제 첫 프레임이 오기 전에는 ‘준비중’이며 마지막 화면을 새 영상처럼 표시하지 않습니다.
- **잠깐 멈추기**를 누르면 영상 연결이 종료됩니다. **다시 보기**로 연결합니다.
- 다른 탭으로 이동하면 자동으로 멈추고 돌아오면 다시 연결합니다. 직접 멈춘 영상은 탭을 돌아와도 멈춘 상태를 유지합니다.
- **크게 보기**로 원본 비율을 유지한 전체 화면을 볼 수 있습니다.
- 파이가 새 프레임 중단을 알리면 오류 블라인드가 내려옵니다. **다시 연결**을 사용합니다.
- 카메라 해상도/FPS 변경을 감지하면 새 스트림으로 다시 연결합니다. 최신 파이 실행기를 사용하세요.
- **카메라 설정** 안에서 실제 해상도와 파이 처리 FPS를 확인할 수 있습니다. 표시 FPS는 브라우저 렌더링 FPS를 보장하는 수치가 아닙니다.

영상이 안 나오면 전체 `/stream.mjpg` 주소를 먼저 직접 엽니다. 직접 열리지 않으면 파이·터널 상태를 확인하고, 직접 열리는데 사이트에서 안 나오면 환경 변수와 재배포, 브라우저에 별도로 저장한 주소를 확인합니다. 공개 HTTPS 사이트에는 학교 LAN의 HTTP 주소를 직접 넣지 않습니다.

FHD MJPEG는 시청자마다 파이의 업로드 대역폭을 사용합니다. 여러 기기로 실제 부하를 확인해야 하며, 터널 제공자의 사용량·정책 제한을 따릅니다.

## 5. 파일과 수정

현재 UI는 첨부 HTML에 맞춘 **HTML/CSS + JavaScript**이며 Vite로 빌드합니다.

- `web-dashboard/index.html`: 간판·차양·창문·문구·폰트.
- `web-dashboard/src/shopfront.js`: 실제 영상과 팻말 상태, 자동 멈춤, 전체 화면.
- `web-dashboard/src/cameraConnection.js`: 공통 주소·브라우저 설정·주소 검증.
- `docs/design/index.html`: 전달받은 디자인 원본.
- `edge-pi/camera_preview.py`: 하나의 카메라 촬영 작업을 여러 시청자가 공유하는 송출기.

로컬 수정은 Node.js 22가 설치된 Mac/PC에서 `npm --prefix web-dashboard ci`, `npm --prefix web-dashboard run dev:public`로 시작합니다. 단일 HTML은 `npm --prefix web-dashboard run build:preview`로 만듭니다. 이 미리보기는 웹폰트 대신 시스템 폰트를 사용하며 주소를 연결하기 전까지 실제 영상을 표시하지 않습니다.

이전 React/재고/DB 구현은 Git 이력과 보관 파일에 남아 있지만 현재 사이트와 카메라 전용 ZIP에서 사용하지 않습니다. 배포와 실제 학교 장비의 영상 연결 성공은 별도로 확인합니다.
