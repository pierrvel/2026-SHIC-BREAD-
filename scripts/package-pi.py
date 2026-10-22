"""Create a reproducible, Node-free Raspberry Pi runtime ZIP. No credentials."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
files = ['README.md', 'edge-pi/server.py', 'edge-pi/main.py', 'edge-pi/analyzer.py',
         'edge-pi/generate_sample.py', 'edge-pi/requirements.txt', 'edge-pi/.env.example',
         'edge-pi/web/index.html', 'scripts/run-pi.sh', 'scripts/preview-camera.sh',
         'edge-pi/camera_preview.py']
archive = root / 'school-bread-pi.zip'
for name in files:
    if not (root / name).is_file():
        raise SystemExit(f'Missing runtime file: {name}. Rebuild the web bundle first.')
with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as bundle:
    for name in files:
        info = ZipInfo('school-bread-pi/' + name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        bundle.writestr(info, (root / name).read_bytes())
with ZipFile(archive) as bundle:
    if bundle.testzip() is not None:
        raise SystemExit('Pi runtime ZIP integrity check failed')
print(f'Created and verified: {archive.name}')
