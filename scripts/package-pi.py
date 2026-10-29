"""Package only the camera runtime: no database, inventory worker or Node."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
files = ['README.md', 'docs/DEPLOY.md', 'edge-pi/camera_preview.py',
         'scripts/preview-camera.sh', 'scripts/share-camera.sh']
for filename, prefix in [('jaebbangso-pi.zip', 'jaebbangso-pi'), ('school-bread-pi.zip', 'school-bread-pi')]:
    archive = root / filename
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as bundle:
        for name in files:
            info = ZipInfo(prefix + '/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, (root / name).read_bytes())
    with ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise SystemExit('Pi runtime ZIP integrity check failed')
    print(f'Created and verified camera-only runtime: {archive.name}')
