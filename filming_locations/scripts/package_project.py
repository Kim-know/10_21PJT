"""비밀키·DB·캐시·모델을 제외한 로컬 검토용 ZIP. 외부 제출은 하지 않는다."""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.tmp', '.venv', 'venv', '.cache', '.vectors', '.models', '__pycache__', 'output', 'reference', 'collected'}
SUFFIXES = {'.py', '.md', '.json', '.csv', '.txt', '.html', '.js', '.css', '.png', '.mmd'}
PATTERNS = [re.compile(r'sk-[A-Za-z0-9_-]{24,}'),
            re.compile(r'AIza[A-Za-z0-9_-]{30,}'),
            re.compile(r'''(?:GMS_KEY|OPENAI_API_KEY|api_key)\s*=\s*["'][A-Za-z0-9_-]{24,}["']''')]


def run():
    files, findings = [], []
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(p in EXCLUDED for p in relative.parts) or relative.as_posix() == 'data/research/data_go_kr.html':
            continue
        if path.name not in ('.env.example', '.gitignore') and path.suffix not in SUFFIXES:
            continue
        if path.name.startswith('.env') and path.name != '.env.example':
            continue
        if path.suffix != '.png':
            text = path.read_text(encoding='utf-8-sig', errors='replace')
            if any(pattern.search(text) for pattern in PATTERNS):
                findings.append(str(relative))
        files.append(path)
    if findings:
        # 일치한 비밀값 자체는 출력하지 않는다.
        print(json.dumps({'status': 'BLOCKED', 'files_to_review': findings}, ensure_ascii=False))
        raise SystemExit(1)
    manifest = {'kind': '검토용 패키지 / 최종 제출 승인 아님', 'secret_pattern_scan': 'PASS (알려진 패턴만 검사)',
                'excluded': sorted(EXCLUDED | {'.env', '*.sqlite3', 'secrets.toml'}),
                'files': [dict(path=str(p.relative_to(ROOT)).replace('\\', '/'),
                               sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]}
    output = ROOT / 'output'
    output.mkdir(exist_ok=True)
    path = output / 'filming_locations_review.zip'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for source in files:
            archive.write(source, 'filming_locations/' + source.relative_to(ROOT).as_posix())
        archive.writestr('filming_locations/package_manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert not any(n.endswith(('.sqlite3', 'secrets.toml', '/.env')) for n in archive.namelist())
    (output / 'package_report.json').write_text(json.dumps(dict(zip=str(path), included_files=len(files),
        bytes=path.stat().st_size, zip_integrity='PASS', secret_patterns='PASS', external_submission=False),
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'included_files': len(files), 'zip_integrity': 'PASS', 'secret_patterns': 'PASS'}, ensure_ascii=False))


if __name__ == '__main__':
    run()
