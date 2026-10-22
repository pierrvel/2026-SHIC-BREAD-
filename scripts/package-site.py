"""Package the verified production output for Cloudflare Pages Direct Upload."""
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
directory = root / 'web-dashboard/dist'
manifest = directory / 'public-build.json'
if not manifest.exists():
    raise SystemExit('Run npm --prefix web-dashboard run build:public first.')
state = json.loads(manifest.read_text())
if state.get('hosting') != 'cloudflare-pages' or state.get('mode') != 'camera' or state.get('mockMode') is not False or state.get('inventoryEnabled') is not False:
    raise SystemExit('Only a verified production build can be packaged.')
archive = root / 'school-bread-site.zip'
with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as bundle:
    for path in sorted(directory.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        if relative.startswith('.') or '/.' in relative or path.suffix == '.map':
            continue
        info = ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        bundle.writestr(info, path.read_bytes())
with ZipFile(archive) as bundle:
    if bundle.testzip() is not None or 'index.html' not in bundle.namelist():
        raise SystemExit('Production ZIP verification failed.')
print(f'Created Cloudflare Pages Direct Upload archive: {archive.name}')
