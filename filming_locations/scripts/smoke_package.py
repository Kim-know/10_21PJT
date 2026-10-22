"""검토 ZIP을 새 폴더에 풀고 현재 설치된 의존성으로 HTTP·파일 경계를 검사."""
import compileall
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    (ROOT / '.tmp').mkdir(exist_ok=True)
    with TemporaryDirectory(dir=ROOT / '.tmp') as directory:
        with zipfile.ZipFile(ROOT / 'output/filming_locations_review.zip') as archive:
            assert archive.testzip() is None
            archive.extractall(directory)
        package = Path(directory) / 'filming_locations'
        assert compileall.compile_dir(package, quiet=1)
        code = """
from fastapi.testclient import TestClient
from api import app
with TestClient(app) as c:
    assert c.get('/').status_code == 200
    for asset in ('app.js','style.css','map.html'):
        assert c.get('/assets/'+asset).status_code == 200
    assert len(c.get('/api/places').json()['places']) == 266
    assert c.get('/api/status').status_code == 200
print('PASS')
"""
        result = subprocess.run([sys.executable, '-c', code], cwd=package,
                                env=dict(os.environ, GMS_KEY='', PYTHONUTF8='1'), capture_output=True,
                                text=True, encoding='utf-8', timeout=60)
        assert result.returncode == 0, result.stderr
    report = dict(zip_integrity='PASS', python_compile='PASS', extracted_frontend_assets='PASS',
                  extracted_http_catalog_status='PASS', real_gms_used=False,
                  dependency_environment='현재 설치된 requirements 환경 재사용; 완전히 새 PC 설치 검증은 아님')
    (ROOT / 'output/package_smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
