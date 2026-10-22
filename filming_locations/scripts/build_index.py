"""python scripts/build_index.py: 로컬 모델 최초 다운로드 후 재사용."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from services.vector_store import build_index
from services.confirmed_places import load_catalog, saved_records, mark_indexed

if __name__ == '__main__':
    catalog = load_catalog()
    print(json.dumps(build_index(catalog), ensure_ascii=False))
    for saved in saved_records():
        mark_indexed(saved['id'])
