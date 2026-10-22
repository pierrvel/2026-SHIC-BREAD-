# 빵살핌 공개 사이트 연결

웹사이트는 **Cloudflare Pages**, 영상 공개는 **Cloudflare Tunnel**을 사용합니다. Firebase `bread-notificator`는 자동 재고 동기화를 추가할 때 사용하는 선택 연동입니다. `docs/design/index.html`은 사용자가 제공한 디자인 원본이고 실제 사이트는 `web-dashboard`의 React 코드입니다. 슬롯 지도·재고 사진은 Firebase의 `config`/`status`를, CCTV 상세는 별도의 HTTPS MJPEG 주소를 사용합니다. 지도 화면에서는 영상에 연결하지 않습니다.

## 1. 파이의 FHD 카메라 실행

최신 Pi ZIP을 새 폴더에 풀거나 저장소를 업데이트하고 실행합니다.

```bash
bash scripts/preview-camera.sh --camera-backend opencv
```

기본 요청은 **1920×1080 / 목표 60 FPS / JPEG 품질 90**입니다. FHD 30 FPS까지만 지원하는 카메라는 실제로 60 FPS를 촬영할 수 없습니다. 드라이버가 60 요청에 30 미만을 선택하면 같은 해상도에서 30 FPS를 다시 요청합니다. 해상도를 자동으로 낮추지 않습니다. 조명·필터·인코딩 부하로 처리 FPS가 30 미만일 수도 있으므로 실제 값을 확인하세요.

LAN 관리자 화면은 `http://파이IP:8081`입니다. 영상 아래에서 FHD와 목표 FPS 30..60, JPEG 화질, 노이즈 제거를 조절합니다. 설정은 현재 실행에 적용되고 다음 시작값은 명령줄 옵션을 따릅니다. CLI의 저해상도·저FPS 옵션은 진단용입니다.

기본 `127.0.0.1:8082`는 터널용 **읽기 전용** 원본입니다. `/stream.mjpg`와 `/api/health`만 제공하고 관리자 HTML, 설정 변경 API, 요청 토큰은 제공하지 않습니다. 변경 시 `--public-port`를 사용합니다. **8081 관리자 포트를 공개 터널에 연결하지 마세요.**

## 2. 공개 HTTPS 영상 주소

파이에 공식 `cloudflared`를 설치합니다: <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/>. 카메라 실행 터미널을 유지하고 다른 터미널에서:

```bash
bash scripts/share-camera.sh
```

스크립트는 원본의 `read_only` 표시를 확인한 후 8082에 터널을 연결합니다. 출력되는 실제 `https://…trycloudflare.com`에 `/stream.mjpg`를 붙인 주소를 사용합니다. 임시 터널은 종료하면 끊어지고 재실행하면 주소가 바뀔 수 있습니다. 지속 운영에는 자신의 계정·도메인으로 고정 터널을 설정하고 같은 읽기 전용 포트를 연결합니다. FHD MJPEG의 동시 시청은 파이 업로드 대역폭과 터널 제공자의 사용량·정책 제한을 따릅니다.

사이트의 **영상 연결 설정**에 입력하면 해당 브라우저에 적용됩니다. 모든 학생에게 같은 기본 주소를 제공하려면 배포 전에 `VITE_CAMERA_STREAM_URL`에 설정합니다. 주소에 비밀번호나 API 토큰을 넣지 마세요.

## 3. Cloudflare Pages에 웹사이트 게시

Firebase 설정 없이도 슬롯 지도와 학생용 CCTV 상세를 배포할 수 있습니다. 이 모드에서는 자동 재고·샘플 재고를 표시하지 않으며, 학생이 영상에서 직접 확인합니다.

### GitHub 연결로 자동 배포

1. Cloudflare 대시보드에서 **Workers & Pages → Pages 프로젝트 생성 → GitHub 저장소 연결**을 선택합니다.
2. 저장소는 `pierrvel/2026-SHIC-BREAD-`, 운영 브랜치는 `main`, 루트 디렉터리는 저장소 루트로 지정합니다.
3. 빌드 명령은 `npm --prefix web-dashboard ci && npm --prefix web-dashboard run build:public`, 출력 디렉터리는 `web-dashboard/dist`입니다. 프레임워크 프리셋은 Vite 또는 없음으로 설정할 수 있습니다.
4. 환경 변수 `NODE_VERSION=22`를 지정합니다. 파이에서 확보한 실제 HTTPS 영상 주소를 `VITE_CAMERA_STREAM_URL`에 입력하면 모든 학생에게 같은 기본 영상을 제공합니다. 아직 주소가 없으면 사이트에서 영상 연결 설정으로 해당 브라우저에만 입력할 수 있습니다.
5. 배포 후 Cloudflare가 표시하는 실제 `https://…pages.dev` 주소를 사용합니다. `wrangler.jsonc`의 기본 프로젝트명은 `bread-notificator`이며 실제 생성 여부와 주소는 배포 결과에서 확인합니다.

이후 GitHub `main`에 푸시하면 Cloudflare가 다시 빌드합니다. 카메라 임시 터널 주소가 바뀌면 환경 변수를 수정하고 다시 배포하세요. API 토큰·관리자 비밀번호·서비스 계정 키는 `VITE_` 변수에 넣지 않습니다.

### 빌드 파일을 직접 업로드

`school-bread-site.zip`은 Mock을 끈 검증된 정적 빌드입니다. Cloudflare Pages의 **직접 업로드**에 ZIP을 올리면 됩니다. 파일은 압축 안의 루트에 `index.html`이 있으며, Node/npm을 파이에 설치할 필요가 없습니다. Git 연동과 직접 업로드는 프로젝트 생성 방식이 다르므로 자동 갱신을 원하면 Git 연결을 선택하세요.

소스에서 ZIP을 다시 만들려면 Node.js LTS가 설치된 빌드용 Mac/PC에서:

```bash
npm --prefix web-dashboard ci
npm --prefix web-dashboard run build:public
python3 scripts/package-site.py
```

CLI 배포를 사용하려면 자신의 PC에서 `npx --yes wrangler@latest login`으로 로그인한 뒤 `bash scripts/deploy-site.sh`를 실행합니다. 배포 스크립트는 검증한 Cloudflare 공개 빌드 표시를 확인합니다. 이 저장소를 수정하거나 빌드하는 것만으로 계정에 사이트가 게시되지는 않습니다.

### 선택: Firebase 자동 재고 연결

자동 재고 사진·품절 표시를 추가할 때 `bread-notificator`의 공개 웹 설정 전체를 `.env.local` 또는 Cloudflare 환경 변수에 넣습니다. 필요한 값은 `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_DATABASE_URL`이며 DB는 Realtime Database입니다. 일부 값만 있으면 빌드를 중단해 잘못된 연결을 방지합니다. `build:public`은 항상 Mock을 끕니다.

Firebase 관리자에는 이메일/비밀번호 로그인과 `admin: true` 클레임이 필요합니다. DB 규칙은 로그인한 Firebase CLI에서 `firebase deploy --only database --project bread-notificator`로 배포하며 웹사이트 Hosting 배포와 별개입니다. Firebase 자격증명·파이 연결은 루트 README의 Firebase 절차를 따릅니다.

## 4. 같은 카메라에서 재고 분석

카메라 실행을 유지하면서 LAN 보정 사이트를 함께 열려면:

```bash
bash scripts/run-pi.sh --camera-url http://127.0.0.1:8081/api/frame.jpg
```

`http://파이IP:8000`에서 관리자 로그인 후 ROI와 빈 칸 기준을 보정합니다. 최신 JPEG를 받아 분석하므로 USB 장치를 두 번 열지 않습니다. 이 LAN 상태와 인터넷 Firebase DB는 별개입니다. Firebase 업로드에도 같은 프레임을 사용할 수 있습니다.

```bash
export MOCK_MODE=false
export CAMERA_URL=http://127.0.0.1:8081/api/frame.jpg
# Firebase Admin 자격증명·DB URL·실제 빈 칸 기준은 루트 README대로 설정
.venv-pi/bin/python edge-pi/main.py
```

영상은 가능한 카메라 속도로 제공하며, 재고 판별·업로드는 기존 30초 주기와 변화 감지를 유지합니다.
