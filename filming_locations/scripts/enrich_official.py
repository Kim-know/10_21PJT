"""키 없이 기존 공식 출처 본문을 검토 대기함에 수집한다."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.confirmed_places import load_catalog
from services.enrichment import collect_official
if __name__=='__main__':
    report=collect_official(load_catalog(),max(1,min(10,int(sys.argv[1]) if len(sys.argv)>1 else 5)))
    (ROOT/'data/validation/enrichment_collection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
