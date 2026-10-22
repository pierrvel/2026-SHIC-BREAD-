# 빵살핌 · Cloudflare Pages 게시 안내

현재 공개 사이트는 **실시간 영상으로 빵을 직접 확인하는 사이트**입니다. Firebase, 재고 DB, 로그인, 자동 품절 판별은 필요하지 않습니다. 제공받은 HTML 디자인을 React로 구현했으며 원본은 `docs/design/index.html`에 보관합니다.

```text
GitHub main ──자동 빌드──→ Cloudflare Pages ──사이트──→ 학생 브라우저
USB 웹캠 → 라즈베리 파이 → Cloudflare Tunnel ──영상──→ 학생 브라우저
```

사이트와 영상의 주소는 서로 다릅니다. Pages는 사이트 파일을 제공하고, 영상은 학생 브라우저가 터널을 통해 파이에서 직접 받습니다. 파이와 영상 프로그램이 켜져 있어야 영상이 나옵니다. 현재 구성은 영상을 녹화하지 않습니다.

## 1. GitHub 저장소를 Cloudflare Pages에 연결

1. [Cloudflare 대시보드](https://dash.cloudflare.com/)에 로그인합니다.
2. **Workers & Pages → 만들기 → Pages → Git 저장소 연결**을 선택합니다. 메뉴 이름이 달라도 **Pages의 Git 연동**을 선택하세요. Workers의 배포 명령을 요구하는 화면과는 다릅니다.
3. GitHub 계정을 연결하고 `pierrvel/2026-SHIC-BREAD-`에 접근을 허용합니다. 목록에 없으면 GitHub 앱의 저장소 접근 범위를 확인합니다.
4. 아래 값을 입력합니다.

| 설정 | 입력값 |
| --- | --- |
| 프로젝트 이름 | `bread-notificator` 또는 원하는 사용 가능한 이름 |
| 프로덕션 브랜치 | `main` |
| 프레임워크 프리셋 | 없음 |
| 루트 디렉터리 | 비워 두기 — 저장소 루트 |
| 빌드 명령 | `npm --prefix web-dashboard ci && npm --prefix web-dashboard run build:public` |
| 빌드 출력 디렉터리 | `web-dashboard/dist` |
| 환경 변수 | `NODE_VERSION` = `22` |

5. 영상 주소가 준비되었다면 환경 변수 `VITE_CAMERA_STREAM_URL`에 실제 **HTTPS MJPEG 주소 전체**를 입력합니다. 예: `https://실제-영상-호스트/stream.mjpg`. 예시 문자열 자체를 입력하지 마세요. 아직 주소가 없으면 비워 두고 먼저 배포할 수 있습니다.
6. **저장 및 배포**를 누릅니다. 빌드 로그에 `vite build --mode camera`와 성공 결과가 표시되는지 확인합니다.
7. Cloudflare가 발급한 실제 `https://…pages.dev` 주소를 엽니다. 주소와 프로젝트 생성 성공 여부는 배포 결과에서 확인합니다.

`VITE_` 환경 변수는 브라우저에 공개됩니다. 공개 영상 주소만 넣고 비밀번호·API 토큰·서비스 계정 키는 넣지 않습니다. Firebase 환경 변수는 입력하지 않습니다. 영상 전용 빌드는 기존 Firebase 변수가 남아 있어도 재고 기능을 활성화하지 않습니다.

> 저장소 루트의 `index.html`은 예전 기능을 살펴보는 오프라인 데모입니다. Pages에는 **`web-dashboard/dist`**를 게시하세요. 루트 파일이나 `school-bread-preview.zip`을 게시용으로 사용하지 않습니다.

## 2. 파이에서 실제 웹캠 영상 실행

최신 `school-bread-pi.zip`을 새 폴더에 풀거나 기존 저장소를 업데이트합니다. 저장소를 사용하는 경우:

```bash
cd ~/school-bread
git pull --ff-only
bash scripts/preview-camera.sh --camera-backend opencv
```

ZIP을 사용하는 경우 압축을 푼 `school-bread-pi` 폴더에서 마지막 명령을 실행하세요. 이 작업은 Python으로 구동하며 파이에 Node/npm을 설치할 필요가 없습니다.

같은 네트워크에서 `http://파이IP:8081`을 열어 실제 움직이는 영상인지 확인합니다. 기본 요청은 **1920×1080 / 목표 60 FPS / JPEG 품질 90**입니다. 해상도를 자동으로 낮추지 않으며 실제 FPS는 웹캠 지원 모드·조명·처리 속도에 따라 달라집니다. FHD 30 FPS 웹캠을 소프트웨어로 실제 60 FPS 촬영하게 만들 수는 없습니다.

8081의 관리자 화면에서 FPS 30..60, JPEG 화질, 노이즈 제거를 바꿀 수 있습니다. 설정은 현재 실행에 적용되며 다음 실행의 시작값은 명령줄 옵션을 따릅니다.

## 3. 공개 HTTPS 영상 주소 만들기

파이에 공식 `cloudflared`를 설치합니다: [Cloudflare 공식 다운로드 안내](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/).

카메라 실행 터미널을 유지하고 **파이의 다른 터미널**에서:

```bash
cd ~/school-bread
bash scripts/share-camera.sh
```

ZIP을 사용했다면 두 번째 터미널도 압축을 푼 폴더로 이동합니다. 스크립트는 카메라 서버의 읽기 전용 표시를 확인한 후 터널을 시작합니다.

1. 터미널에 나오는 실제 `https://…trycloudflare.com` 주소를 복사합니다.
2. 끝에 `/stream.mjpg`를 붙입니다.
3. 이 전체 주소를 Mac이나 휴대폰 브라우저에서 직접 열어 움직이는 영상을 확인합니다.
4. Pages 프로젝트의 **설정 → 환경 변수**에서 프로덕션의 `VITE_CAMERA_STREAM_URL`을 이 전체 주소로 저장합니다.
5. **배포 → 배포 다시 시도/새 배포**로 사이트를 다시 빌드합니다. 환경 변수만 바꿔서는 이미 만들어진 사이트 파일이 바뀌지 않습니다.
6. 사이트를 새로 열고 **실시간 카메라**에서 확인합니다.

사이트의 **영상 연결 설정**은 테스트할 때 해당 브라우저에만 적용됩니다. 모든 학생에게 공통 주소를 제공하려면 Pages 환경 변수를 사용하세요. 이전에 브라우저에 직접 저장한 주소는 기본 주소보다 우선하므로, 그 브라우저에서 새 주소로 수정하거나 사이트 데이터를 지워 다시 확인합니다.

임시 터널은 종료하면 끊어지고 재실행하면 주소가 달라질 수 있습니다. 주소가 바뀌면 환경 변수 수정과 재배포가 필요합니다. 지속 운영에는 Cloudflare에 연결한 자신의 도메인과 **고정 터널**을 사용합니다. Pages에서 발급된 `pages.dev` 주소를 카메라 터널 주소로 사용할 수는 없습니다.

### 고정 터널을 사용할 때

Cloudflare One의 터널 관리에서 파이용 터널을 만들고, 안내되는 커넥터 설치 명령을 **파이에서** 실행합니다. 공개 호스트명(예: 자신의 도메인의 `camera` 서브도메인)에 연결할 서비스는 **HTTP / `localhost:8082`**입니다. 그 뒤 `https://실제-카메라-도메인/stream.mjpg`를 Pages 환경 변수에 등록하고 재배포합니다. 이 경우 임시 `share-camera.sh` 터널은 함께 실행할 필요가 없습니다. 계정에서 제공하는 설치 토큰은 저장소에 커밋하지 않습니다.

카메라 서버가 터널에 제공하는 기본 포트는 **`127.0.0.1:8082`**입니다. `/stream.mjpg`와 `/api/health`만 공개하며 설정 변경은 허용하지 않습니다. **관리자 포트 8081을 공개 터널에 연결하지 마세요.**

## 4. 실제 게시 확인

- 지도에서 칸을 고르면 선택한 위치가 표시됩니다. 현재 기본 배치는 2행 × 3열이며 실제 배치에 맞춰 `web-dashboard/src/siteLayout.js`를 수정할 수 있습니다. 자동 재고·품절 표시는 없습니다.
- **실시간 카메라에서 확인**을 누르면 선택한 위치를 유지하고 실제 영상을 표시합니다. 전체 화면과 다시 연결을 사용할 수 있습니다.
- 지도로 돌아가면 영상 연결을 종료합니다. 사진 한 장이 아니라 물체를 움직여 연속 영상인지 확인합니다.
- 카메라 주소를 아직 등록하지 않아도 사이트는 열리고 연결 준비 화면이 나옵니다.
- 영상이 안 나오면 먼저 `/stream.mjpg` 주소를 직접 엽니다. 직접 열리지 않으면 파이 프로그램·터널 상태를 확인하고, 직접 열리는데 사이트에서 안 나오면 `VITE_CAMERA_STREAM_URL`과 재배포 여부, 브라우저에 저장된 개별 주소를 확인합니다.

FHD MJPEG는 접속자마다 파이의 업로드 대역폭을 사용합니다. 이 구성은 Cloudflare의 영상 중계 서비스나 CDN 영상 캐시가 아니며, 동시 시청은 네트워크와 터널 제공자의 사용량·정책 제한을 따릅니다. 여러 기기로 실제 부하를 확인하고 동시 접속이 많아지면 영상 전송 방식을 별도로 검토합니다.

## 5. 이후 수정과 자동 배포

Git 연결을 끝내면 **GitHub `main`에 새 커밋을 푸시할 때 Cloudflare Pages가 자동으로 다시 빌드·배포**합니다. GitHub에 파일을 저장하는 것만으로 최초 Cloudflare 계정 연결이 대신 이루어지지는 않습니다. 이 저장소에는 별도 Cloudflare API 토큰이나 GitHub Actions 배포 비밀키가 필요하지 않습니다.

핵심 사이트 파일:

- `web-dashboard/src/public-main.jsx`: 공개 사이트 진입점. Firebase나 Mock 데이터를 불러오지 않습니다.
- `web-dashboard/src/Site.jsx`: 화면 전환과 공통 레이아웃.
- `web-dashboard/src/components/StudentView.jsx`, `CameraView.jsx`: 슬롯 지도와 영상 화면.
- `web-dashboard/src/siteLayout.js`: 칸 이름과 위치 안내.
- `web-dashboard/src/design.css`, `styles.css`: 디자인.
- `wrangler.jsonc`: Pages 빌드 출력 설정.

로컬 디자인 수정은 Node.js 22가 설치된 Mac/PC에서:

```bash
npm --prefix web-dashboard ci
npm --prefix web-dashboard run dev:public
```

공개 빌드와 직접 업로드 ZIP을 다시 만들려면:

```bash
npm --prefix web-dashboard run build:public
python3 scripts/package-site.py
```

`school-bread-site.zip`은 Cloudflare Pages **직접 업로드**에도 사용할 수 있습니다. 다만 Git 자동 배포를 원하면 프로젝트를 만들 때 **Git 연동**을 선택하세요. CLI 직접 배포는 자신의 PC에서 `npx --yes wrangler@latest login` 후 `bash scripts/deploy-site.sh`를 실행합니다. `wrangler.jsonc`와 스크립트의 기본 프로젝트명은 `bread-notificator`이므로 다른 이름을 선택했다면 직접 CLI 배포 전에 맞춥니다.

## 이전 재고 분석 코드

`edge-pi/main.py`, `analyzer.py`, Firebase 규칙, 기존 관리자 화면은 이전 구현을 보존한 선택 기능입니다. 현재 영상 사이트를 운영할 때 실행하거나 설정할 필요가 없습니다. 재고 데모는 `npm --prefix web-dashboard run dev`와 `build:preview`로 별도 실행하며 공개 `build:public`과 분리되어 있습니다.
