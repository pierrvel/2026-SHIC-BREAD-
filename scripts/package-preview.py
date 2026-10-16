"""Package the offline demo for download and opening outside an embedded viewer."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
html = root / 'index.html'
if not html.read_text(encoding='utf-8').startswith('<!-- Generated offline demo:'):
    raise SystemExit('Generate the portable demo first: npm --prefix web-dashboard run build:preview')

archive = root / 'school-bread-preview.zip'
with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as bundle:
    bundle.write(html, 'index.html')
    bundle.writestr('README.txt',
        '쉬는빵 오프라인 데모\n\n'
        '1. 압축을 풀어 주세요.\n'
        '2. index.html을 Chrome 또는 Edge에서 열어 주세요.\n'
        '서버 설치나 Firebase 계정 없이 샘플 재고·사진·필터·관리자 설정을 볼 수 있습니다.\n'
        '실제 자판기 재고가 아닌 합성 샘플입니다.\n'
        'Codex 내장 파일 미리보기는 콘텐츠 표시를 차단할 수 있습니다.\n'
        '브라우저 저장소가 제한되면 설정은 현재 창에서만 유지됩니다.\n')
with ZipFile(archive) as bundle:
    if bundle.testzip() is not None:
        raise SystemExit('ZIP integrity check failed')
print(f'Created and verified: {archive.name}')
