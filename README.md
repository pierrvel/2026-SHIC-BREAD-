# 쉬는빵 · 교내 자판기 재고 확인

라즈베리 파이에서 30초마다 촬영하고, 빈 칸과의 평균 채도 차이로 **재고 있음 / 품절**을 판별합니다. React는 Firebase Realtime Database를 직접 구독합니다. 별도 상시 백엔드, 유료 AI API, 상품명 인식 모델은 사용하지 않습니다.

**파이에서 지금 바로 실행하려면 아래의 로컬 실행 모드를 사용하세요.** 파이가 카메라·분석기·웹 서버를 함께 실행합니다. 웹 파일이 포함되어 있어 파이에 Node.js/npm을 설치하거나 Firebase 프로젝트를 먼저 만들 필요가 없습니다. 인터넷 공개 서비스는 기존 Firebase 모드를 사용하고, 로컬 모드는 같은 네트워크에서 장치 간 통신이 가능한 환경의 구동·현장 보정에 사용합니다.

1. 기존 저장소를 받은 파이 터미널에서 실행합니다. Raspberry Pi OS 64비트, Python 3.10 이상이 기준입니다.

   ```bash
   cd ~/school-bread
   git pull --ff-only
   bash scripts/run-pi.sh
   ```

   필요한 OS 패키지가 없으면 스크립트가 `apt`로 설치합니다. 관리자 암호가 요청될 수 있습니다. 카메라용 환경은 `.venv-pi`에 분리해 기존 `.venv`와 pip NumPy를 건드리지 않습니다. 기본값은 **실제 Picamera2 카메라**이며 카메라 실패 시 샘플로 바뀌지 않습니다. USB 카메라는 `--camera-backend opencv`를 추가하세요.

2. 다른 터미널에서 `hostname -I`로 파이의 IP를 확인하고 같은 네트워크의 PC/휴대폰 브라우저에서 `http://파이IP:8000`을 엽니다. 예시의 `파이IP`는 실제 주소로 바꾸세요. 이것은 파이의 LAN 주소이며 Codex 파일 미리보기를 사용하지 않습니다.

3. 관리자 화면의 비밀번호는 파이에서 아래 명령으로 확인합니다. 자동 생성된 비밀번호는 저장소에 들어가지 않고, 서버 로그에도 값이 출력되지 않습니다.

   ```bash
   cat ~/.local/share/school-bread/admin-password
   ```

4. 관리자에서 현재 촬영 사진을 보고 칸 좌표를 저장하세요. 자판기의 **모든 칸이 비었을 때** 확인란을 체크하고 **현재 사진을 빈 칸 기준으로 촬영**을 누릅니다. 이 동작은 새 프레임을 촬영하며 기존 기준은 백업합니다. 보정 전에는 재고를 미확인으로 표시합니다. 보정 후 상품을 넣으면 다음 촬영 때 분석 결과와 WebP 사진이 갱신됩니다. **지금 촬영** 버튼으로 촬영을 앞당길 수 있습니다.

5. 종료는 Ctrl+C입니다. 기본 주기는 30초, 웹 포트는 8000입니다. 예: `bash scripts/run-pi.sh --port 8080 --interval 10`. 설정·판별 결과·기준 사진은 `~/.local/share/school-bread/`에 유지되고 다음 실행에 재사용됩니다. 서버를 재시작하면 이전 결과를 현재 재고처럼 표시하지 않고 새 판별을 기다립니다. SSH 세션을 종료하면 프로그램이 종료될 수 있으므로 실행 중에는 터미널을 유지하세요.

카메라가 없는 PC에서 전체 분석·웹 연동을 확인하려면 명시적으로 `bash scripts/run-pi.sh --sample`을 실행합니다. 샘플 표시는 브라우저 임의 점수가 아니라 Python이 합성 사진을 분석한 결과입니다. UI에서 샘플임을 표시합니다. **실제 장비 보정 데이터와 분리**하려면 `--data-dir "$HOME/.local/share/school-bread-sample"`도 지정하세요.

Git 대신 다운로드하려면 저장소의 `school-bread-pi.zip`을 받아 압축을 풀고, 그 안의 `school-bread-pi` 폴더에서 `bash scripts/run-pi.sh`를 실행해도 됩니다. 이 ZIP에는 가상환경·서비스 계정 키·관리자 비밀번호가 포함되지 않습니다.

로컬 학생용 읽기 API는 공개이고 설정 쓰기·전체 사진·보정·즉시 촬영은 관리자 세션이 필요합니다. 로그인은 비밀번호, HttpOnly/SameSite 세션 쿠키, 시도 횟수 제한을 사용합니다. 로컬 API는 기존 `config`/`status` 스키마를 유지하며, 장치 상태만 별도 `meta` 응답으로 전달합니다. Firebase 배포에서는 기존 SDK 실시간 리스너와 Firebase 관리자 인증을 그대로 사용합니다.

개발자가 UI를 수정한 경우 `npm --prefix web-dashboard run build:preview`로 `edge-pi/web/index.html`을 갱신한 뒤 `python3 scripts/package-pi.py`로 Pi ZIP을 다시 만듭니다. Node/npm은 이 빌드 단계에만 필요합니다.

```text
edge-pi/          Python 3.10+, OpenCV 분석·카메라·Firebase Admin
web-dashboard/    React 18, Vite, Tailwind CSS, Firebase JS SDK
database.rules.json  공개 읽기 / 관리자만 config 쓰기 / 클라이언트 status 쓰기 금지
```

## 1. 카메라·Firebase 없이 실행

**Codex 내장 뷰어에서 콘텐츠 차단 오류가 발생하면 `school-bread-preview.zip`을 다운로드해 압축을 풀고, `index.html`을 Chrome 또는 Edge에서 여세요.** 이 오프라인 데모에는 JavaScript·CSS·샘플 사진이 모두 포함되어 있어 개발 서버나 Firebase 연결 없이 학생 화면과 관리자 설정을 확인할 수 있습니다. Codex 내장 뷰어에서의 표시 성공은 확인되지 않았습니다. `web-dashboard/index.html`은 Vite 소스 진입점이므로 Vite 서버를 통해 실행해야 합니다.

미리보기 파일은 `npm --prefix web-dashboard run build:preview`로 다시 생성하고, `python3 scripts/package-preview.py`로 다운로드용 ZIP을 만듭니다. 실제 Firebase 모드는 아래 Vite 실행 절차를 사용합니다. 미리보기에서 브라우저 저장소가 제한되면 설정은 현재 창에만 적용되며 화면에 그 사실을 표시합니다.

저장소 루트에서 실행합니다. Python 3.10 이상, Node 20.19 이상이 필요합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r edge-pi/requirements.txt
.venv/bin/python edge-pi/generate_sample.py
.venv/bin/python edge-pi/main.py --once
cd web-dashboard
npm ci
npm run dev
```

기본값은 `MOCK_MODE=true`입니다. Python은 `edge-pi/sample_vending.jpg`를 분석해 `edge-pi/mock-state.json`에 요청된 `config` / `status` 스키마로 결과를 씁니다. `--once`를 빼면 30초마다 반복합니다. 합성 샘플은 1·3·4·6번 칸에 재고가 있고 2·5번 칸은 비어 있습니다.

웹에는 같은 분석기로 만든 WebP 썸네일과 샘플 설정이 포함되어 있어 Python 없이도 실행됩니다. 관리자에서 설정을 저장하면 같은 브라우저의 학생 화면과 다른 탭에 반영되고, 새 기준값으로 샘플 점수를 재평가합니다. **웹 Mock(localStorage)과 Python Mock(JSON)은 독립 실행**입니다. ROI 변경을 실제 재분석하려면 관리자의 **설정 JSON 내려받기** 후 다음과 같이 실행합니다.

```bash
.venv/bin/python edge-pi/main.py --once --mock-config /path/to/vending-config.json
```

샘플 이미지를 새로 만들고 웹 번들에도 분석 결과를 반영하려면 `generate_sample.py --export-web`을 실행합니다. 이 명령은 샘플 산출물을 다시 생성하므로 실제 촬영 사진을 이 경로에 보관하지 마세요.

## 2. 판별 방식과 DB 스키마

```text
hsv_score = abs(mean(S(현재 ROI)) - mean(S(빈 칸 기준 ROI)))
in_stock = hsv_score > config.threshold  # OpenCV S: 0..255
```

빈 칸 기준 사진은 파이에만 보관합니다. ROI는 `config.slots`의 원본 픽셀 좌표이고, 현재/기준 사진 해상도는 같아야 합니다. 범위를 벗어난 ROI나 잘못된 기준값은 업로드 전에 거부합니다. 썸네일은 최대 160×192px, WebP 품질 55로 압축합니다.

```json
{
  "config": {
    "threshold": 35,
    "slots": {
      "slot_1": { "name": "1번 칸", "x": 50, "y": 50, "w": 150, "h": 180 }
    }
  },
  "status": {
    "updated_at": "2026-10-16 13:00:00",
    "slots": {
      "slot_1": { "in_stock": true, "hsv_score": 68.5, "thumbnail": "data:image/webp;base64,..." }
    }
  }
}
```

`updated_at`은 한국 시간(`Asia/Seoul`)의 **마지막 판별 시각**입니다. 카메라 생존 신호가 아닙니다. 마지막으로 업로드한 프레임과 `cv2.absdiff` 평균값을 비교해 변화가 적으면 판별/업로드를 건너뜁니다. 따라서 느리게 누적된 변화도 감지합니다. 설정이 바뀌면 이미지 변화와 무관하게 다시 분석합니다. 매 주기에 config를 읽으며, 업로드 실패 후에는 이전 프레임을 갱신하지 않아 다음 주기에 재시도합니다.

사진은 상품명 오인식을 피할 수 있지만, 채도 기반 재고 판별은 조명·투명 포장·배경색에 따라 틀릴 수 있습니다. 현장에서 빈/찬 칸을 비교해 threshold와 `DIFF_THRESHOLD`를 조정하세요. 30초 촬영 주기에 네트워크 지연이 더해지므로 실제 물리적 변화가 0.1초 내 반영되지는 않습니다. 웹은 새 DB 값을 받는 즉시 렌더링하며 지연을 보장하지 않습니다.

## 3. 실제 Firebase 연결

1. Firebase 프로젝트에서 **Spark 요금제의 Realtime Database**를 생성합니다. Firestore가 아닙니다. DB URL은 콘솔에서 복사합니다.
2. Authentication에서 **이메일/비밀번호** 로그인을 활성화하고 관리자 사용자를 만듭니다. 로컬 개발과 배포 도메인을 승인된 도메인에 등록합니다.
3. `database.rules.json`을 Realtime Database 규칙에 적용합니다. 또는 인증된 Firebase CLI로 저장소 루트에서 `firebase deploy --only database --project YOUR_PROJECT_ID`를 실행합니다. 테스트 모드의 공개 쓰기를 사용하지 마세요.
4. 관리자 계정에 `admin: true` 커스텀 클레임을 부여합니다. 아래 코드는 신뢰할 수 있는 로컬 기기에서만 실행하세요. 기존 클레임을 보존합니다.

```python
import firebase_admin
from firebase_admin import auth, credentials

firebase_admin.initialize_app(credentials.ApplicationDefault())
user = auth.get_user("FIREBASE_AUTH_USER_UID")
auth.set_custom_user_claims(user.uid, {**(user.custom_claims or {}), "admin": True})
```

클레임 부여 후 로그아웃했다가 다시 로그인하세요. UI와 DB 규칙이 모두 관리자 권한을 확인합니다. 익명 학생은 config/status만 읽을 수 있고, 브라우저는 status를 쓸 수 없습니다. `firebase-admin`은 규칙을 우회하므로 서비스 계정의 권한과 보관 위치를 제한해야 합니다.

5. `web-dashboard/.env.example`을 `.env.local`로 복사해 프로젝트의 공개 웹 설정을 채웁니다. **`VITE_MOCK_MODE=false`**로 지정하세요. 실제 연결 오류가 나도 Mock으로 전환하지 않고 오류를 표시합니다. Vite 재시작/재빌드가 필요합니다. `VITE_` 변수는 브라우저에 공개되므로 서비스 계정 키나 비밀번호를 넣지 마세요.
6. 관리자 화면에서 기본 6칸 설정을 만든 뒤 **실제 카메라 해상도의 전체 사진**을 불러와 ROI와 기준값을 조정하고 저장합니다. 전체 사진은 브라우저에서만 사용합니다. config/status 스키마에 전체 사진 필드를 추가하지 않습니다. 여러 관리자의 동시 편집은 Firebase transaction으로 충돌을 감지하고 최신 설정을 다시 읽도록 합니다.

초기 설정 JSON은 `edge-pi/mock-state.json`의 `config` 또는 관리자에서 내려받은 JSON을 사용할 수 있습니다. Firebase 콘솔의 `/config` 위치로 가져오세요. status는 파이가 첫 분석 때 생성합니다. DB 루트를 매번 덮어쓰지 않습니다.

## 4. 라즈베리 파이 5에서 실제 촬영

Raspberry Pi OS 64-bit에서 Camera Module V2를 연결하고 `rpicam-still` 등으로 먼저 촬영을 확인하세요. CPL 필터와 고정된 카메라 거치대를 권장합니다. Pi 카메라는 Picamera2를 우선 사용하고 USB 카메라는 OpenCV로 설정할 수 있습니다.

```bash
sudo apt update
sudo apt install python3-picamera2 python3-opencv python3-venv
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r edge-pi/requirements.txt
```

Pi OS 배포판의 Picamera2는 해당 배포판의 NumPy ABI에 맞춰 설치됩니다. pip NumPy와 충돌하면 새 venv에서 배포판의 `python3-numpy`, `python3-opencv`, `python3-pil`을 사용하고 `firebase-admin==6.9.0`만 pip로 설치하세요. 클라우드 x86 환경에서는 Picamera2/실제 카메라를 검증하지 않았습니다.

서비스 계정 JSON은 저장소 밖의 권한 제한된 경로에 두세요. `edge-pi/.env.example`은 참고용이며 자동 로드하지 않습니다.

```bash
export MOCK_MODE=false
export FIREBASE_DATABASE_URL='https://YOUR_DATABASE_URL'
export GOOGLE_APPLICATION_CREDENTIALS='/secure/path/service-account.json'
export EMPTY_IMAGE_PATH='/secure/path/empty-machine.jpg'
export CAMERA_BACKEND=picamera2
# 자판기가 완전히 비어 있을 때 한 번만 실행 (기존 기준 사진은 덮어쓰지 않음)
.venv/bin/python edge-pi/main.py --calibrate-empty
# Firebase config를 등록하고 실제 동작 확인
.venv/bin/python edge-pi/main.py --once
.venv/bin/python edge-pi/main.py
```

카메라 이동 시 빈 칸 기준 사진도 같은 각도로 다시 촬영해야 합니다. ROI 편집만으로 기준 사진 정렬이 보정되지는 않습니다. 기본 Pi 촬영 크기는 1280×960이며, 제공된 합성 샘플의 600×480 좌표를 그대로 사용하지 마세요. USB 카메라는 `CAMERA_BACKEND=opencv CAMERA_INDEX=0`을 사용하고 실제 캡처 해상도로 ROI/기준 사진을 맞춥니다.

`CAPTURE_INTERVAL`(기본 30초), `DIFF_THRESHOLD`(기본 2.0)로 주기와 변화 기준을 조절합니다. 종료는 Ctrl+C이고 카메라 자원을 반환합니다. 서버 오류는 다음 주기에 재시도하며 `--once` 오류는 0이 아닌 종료 코드로 보고합니다.

## 5. 검증과 정적 배포

```bash
# 저장소 루트
.venv/bin/python -m unittest discover -s edge-pi/tests -v
cd web-dashboard
npm run build
```

브라우저 기능 검증은 Mock 모드의 Vite 서버를 먼저 실행한 뒤 저장소 루트에서 다음과 같이 실행합니다. Python Playwright를 별도로 설치하고 `python -m playwright install chromium`으로 브라우저를 준비하세요. 기존 Chromium이 있으면 `BREAD_CHROMIUM_PATH=/usr/bin/chromium`으로 지정할 수 있습니다. 기본 테스트 주소는 로컬 5173 포트이며 `BREAD_TEST_URL`로 바꿀 수 있습니다.

```bash
python web-dashboard/tests/smoke.py
```

로컬 런타임 HTTP/인증/분석 테스트는 Python 테스트 모음에 포함되어 있습니다. 전체 브라우저 검증은 별도의 일회용 데이터 폴더로 서버를 `--sample --interval 1 --data-dir /tmp/bread-test-data` 모드에서 띄운 다음, `BREAD_TEST_URL`에 테스트 서버 주소, `BREAD_TEST_DATA_DIR`에 그 폴더를 지정해 `python web-dashboard/tests/local.py`를 실행합니다. 이 검사는 자기 테스트용 샘플 파일을 변경하므로 실제 장비 데이터 폴더에 실행하지 마세요.

단일 HTML 미리보기는 `python web-dashboard/tests/preview.py`로 별도 검증합니다. 이 검사는 서버 없이 `sandbox` iframe에 HTML을 넣고, 저장소 접근이 거부된 환경에서 사진 표시·필터·관리자 설정 적용·초기화가 작동하는지 확인합니다.

DB 규칙 테스트는 Java 21 이상과 Firebase CLI가 필요합니다. 아래 명령은 실제 Firebase 프로젝트에 연결하지 않고 데모 프로젝트에서 권한 허용/거부를 검사합니다.

```bash
firebase emulators:exec --only database --project demo-school-bread 'npm --prefix web-dashboard run test:rules'
```

이 클라우드 환경에서는 에뮬레이터 다운로드 목적지 `storage.googleapis.com`이 네트워크 정책으로 차단되어 규칙 테스트를 실행하지 못했습니다. 이 도메인을 허용한 뒤 위 명령을 실행해야 규칙 검증이 완료됩니다. 클라우드 재설치 절차는 `scripts/setup-cloud.sh`에 있습니다. Firebase SDK의 미사용 Firestore 하위 패키지가 오래된 gRPC를 고정하므로 `package.json`의 override로 호환되는 최신 1.x gRPC를 사용합니다.

무료 운영은 사용량 한도 내에서 가능합니다. 학생 수·열린 탭 수·썸네일 다운로드량에 따라 Spark 제한에 도달할 수 있으니 Firebase 콘솔에서 연결 수와 다운로드량을 확인하세요. 불필요한 사진 재전송을 줄이기 위해 변화가 있을 때만 status를 갱신합니다.

정적 웹은 빌드 후 Firebase Hosting에 올릴 수 있습니다. Firebase CLI 로그인/프로젝트 선택 후 루트에서 `firebase deploy --only hosting --project YOUR_PROJECT_ID`를 실행하세요. 이 저장소의 구현 작업은 실제 Firebase 프로젝트 생성, 규칙 배포, 계정 생성 또는 게시를 수행하지 않습니다.
