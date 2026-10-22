"""GMS 호출 없이 테스트 결과를 실행 증거로 저장한다."""
import json
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ['check_grounding.py', 'check_rag.py', 'check_scene.py', 'check_app.py',
          'check_savings.py', 'check_confirmed.py', 'check_api.py', 'check_source_policy.py', 'check_geocoding.py', 'check_improvements.py', 'check_photo_compare.py']

if __name__ == '__main__':
    results = []
    for name in CHECKS:
        started = perf_counter()
        process = subprocess.run([sys.executable, name], cwd=ROOT,
                                 env=dict(os.environ, PYTHONUTF8='1'), capture_output=True, text=True, encoding='utf-8')
        results.append(dict(check=name, status='PASS' if process.returncode == 0 else 'FAIL',
                            exit_code=process.returncode, seconds=round(perf_counter()-started, 3),
                            output=process.stdout.strip(), diagnostics=process.stderr.strip()))
        print(name, results[-1]['status'], flush=True)
    out = ROOT / 'data/validation'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'test_results.json').write_text(json.dumps(dict(real_gms_used=False, results=results),
                                                     ensure_ascii=False, indent=2), encoding='utf-8')
    raise SystemExit(0 if all(r['exit_code'] == 0 for r in results) else 1)
