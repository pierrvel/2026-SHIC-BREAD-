"""Package the offline demo for download and opening outside an embedded viewer."""
from pathlib import Path
from shutil import copyfile
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
html = root / 'index.html'
if not html.read_text(encoding='utf-8').startswith('<!-- Generated offline demo:'):
    raise SystemExit('Generate the portable demo first: npm --prefix web-dashboard run build:preview')

archive = root / 'jaebbangso-preview.zip'
with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as bundle:
    bundle.write(html, 'index.html')
    bundle.writestr('README.txt',
        '재빵소 · 실시간 카메라 화면\n\n'
        '1. 압축을 풀어 주세요.\n'
        '2. index.html을 Chrome 또는 Edge에서 열어 주세요.\n'
        '카메라 주소 없이 열면 개업 준비중 화면을 표시합니다. Firebase는 필요하지 않습니다.\n'
        '실제 영상은 카메라 설정에 공개 HTTPS MJPEG 주소를 입력해야 표시됩니다.\n'
        'Codex 내장 파일 미리보기는 콘텐츠 표시를 차단할 수 있습니다.\n'
        '브라우저 저장소가 제한되면 설정은 현재 창에서만 유지됩니다.\n')
with ZipFile(archive) as bundle:
    if bundle.testzip() is not None:
        raise SystemExit('ZIP integrity check failed')
copyfile(archive, root / 'school-bread-preview.zip')
print(f'Created and verified: {archive.name}')
