# 재빵소 · 빵 남았나, 창문으로 보고 가요

학교 빵 자판기 앞 **실시간 카메라를 보는 사이트**입니다. 학생이 화면을 보고 빵이 남았는지 직접 판단합니다. 재고 수량·품절 판별·상품 인식·Firebase·로그인은 사용하지 않습니다.

첨부된 재빵소 v4 HTML과 Git 번들의 디자인·이력을 반영했습니다. 초록 간판, 차양, 나무 팻말, 블라인드 화면을 실제 카메라 연결 상태와 연동합니다. 디자인 원본은 `docs/design/index.html`입니다.

**[Cloudflare 게시와 파이 영상 연결 안내 → docs/DEPLOY.md](docs/DEPLOY.md)**

## 바로 사용할 파일

- `jaebbangso-site.zip`: Cloudflare Pages 직접 업로드용 정적 사이트.
- `jaebbangso-pi.zip`: 카메라 송출만 포함한 Raspberry Pi 실행 파일. Node/npm·DB가 필요하지 않습니다.
- `jaebbangso-preview.zip`: 별도 웹 서버 없이 열어 보는 단일 HTML. 실제 카메라 주소가 없으면 ‘개업 준비중’으로 표시합니다.
- `jaebbangso-repo.bundle`: 소스와 Git 이력을 함께 옮길 때 사용하는 스냅샷. Cloudflare 업로드에는 사이트 ZIP을 사용합니다.
- `school-bread-*.zip`: 이전 다운로드 주소를 사용하는 사용자를 위한 최신 호환 사본.

## 실행

파이에서 최신 코드를 받고 USB 웹캠을 실행합니다.

```bash
bash scripts/preview-camera.sh
```

기본은 USB/OpenCV, 1920×1080, 목표 60 FPS, JPEG 품질 90입니다. 카메라 지원 모드와 조명·처리 속도에 따라 실제 값이 달라집니다. `http://파이IP:8081`에서 실제 영상과 FPS·화질·노이즈 설정을 확인합니다. CSI 카메라에는 `--camera-backend picamera2`를 지정합니다.

카메라를 켠 상태에서 다른 파이 터미널에서 공식 `cloudflared` 설치 후:

```bash
bash scripts/share-camera.sh
```

출력된 HTTPS 주소에 `/stream.mjpg`를 붙여 사이트의 **카메라 설정**에 입력합니다. 모든 학생에게 같은 주소를 적용하려면 Cloudflare의 `VITE_CAMERA_STREAM_URL`에 등록하고 재배포합니다. 터널은 읽기 전용 `127.0.0.1:8082`를 연결하며 8081 관리자 화면은 공개하지 않습니다.

## 실제 사이트 소스와 빌드

- `web-dashboard/index.html`: 재빵소 디자인·문구·메타데이터.
- `web-dashboard/src/shopfront.js`: 영상 시작/중단·상태 팻말·전체 화면·연결 설정.
- `web-dashboard/src/cameraConnection.js`: HTTPS 주소 검증, 이전 주소 승계, 기본 주소 복원.

```bash
npm --prefix web-dashboard ci
npm --prefix web-dashboard run dev:public
npm --prefix web-dashboard run build:public
```

Cloudflare 빌드 명령은 `npm --prefix web-dashboard ci && npm --prefix web-dashboard run build:public`, 출력 폴더는 `web-dashboard/dist`, Node 버전은 22입니다. 기존 Git 연결과 이 빌드 설정을 유지할 수 있습니다.

영상은 첫 프레임이 수신된 뒤 표시합니다. 수동 일시정지와 탭 이동에 따른 자동 멈춤을 구분하며, 페이지 복귀 시 자동으로 멈춘 영상만 다시 연결합니다. 카메라 상태 API가 새 프레임 중단을 알리면 오래된 화면 대신 오류 블라인드를 표시합니다. 합성 테스트 영상은 실제 영상과 구별해 표시합니다. FHD 원본 비율을 유지하며 녹화하지 않습니다.

## 검증

```bash
.venv/bin/python -m unittest discover -s edge-pi/tests -v
# 별도 터미널: 합성 카메라를 명시적으로 실행
.venv/bin/python edge-pi/camera_preview.py --sample --camera-backend opencv --host 127.0.0.1 --port 18120 --public-port 18121 --fps 30
# 별도 터미널: 공개 빌드 후 정적 서버
npm --prefix web-dashboard run preview -- --host 127.0.0.1 --port 14190
# Python Playwright/Chromium이 설치된 환경
BREAD_TEST_URL=http://127.0.0.1:14190 BREAD_TEST_STREAM_URL=http://127.0.0.1:18121/stream.mjpg python web-dashboard/tests/student_camera.py
```

단일 HTML은 `npm --prefix web-dashboard run build:preview` 후 `python web-dashboard/tests/preview.py`로 확인합니다. 브라우저 테스트는 `/usr/bin/chromium`을 기본 사용하고 `BREAD_CHROMIUM_PATH`로 변경할 수 있습니다.

이전 재고 분석기·React/Firebase 파일은 과거 구현을 보관한 것으로 현재 사이트의 진입점에서 불러오지 않으며, 새 파이 실행 ZIP에도 포함하지 않습니다. GitHub에 코드를 올리는 것과 실제 Cloudflare 게시·학교 장비 연결은 별도로 확인해야 합니다.
