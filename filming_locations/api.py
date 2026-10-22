"""독립 HTML 프론트엔드용 API. 실행: python -m uvicorn api:app --host 127.0.0.1 --port 8000."""
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
from services.cache import call_count
from services.confirmed_places import load_catalog, save_confirmed, mark_indexed, saved_records
from services.geocoding import lookup
from services.rag_graph import graph
from services.research import explore, collect_for_question
from services.scene_finder import find_scene
from services.vector_store import counts, build_index, search_items
from settings import limits
from ui.sources import cited_sources

app = FastAPI(title='장면에서 여행으로 API', version='1.0.0')
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
app.mount('/assets', StaticFiles(directory=ROOT / 'frontend'), name='assets')
_pending = {}
_lock = threading.Lock()


@app.middleware('http')
async def same_origin_write(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin != str(request.base_url).rstrip('/'):
        return JSONResponse(status_code=403, content={'detail': '같은 사이트의 화면에서 요청해 주세요.'})
    return await call_next(request)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    return JSONResponse(status_code=500, content={'detail': '처리를 완료하지 못했습니다. 설정과 연결을 확인해 주세요.'})


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    return JSONResponse(status_code=422, content={'detail': '입력 형식과 길이를 확인해 주세요.'})


def item_by_id(item_id):
    item = next((p for p in load_catalog() if p['id'] == item_id), None)
    if not item:
        raise HTTPException(404, '장소를 찾지 못했습니다.')
    return item


def require_key():
    if not os.getenv('GMS_KEY', '').strip():
        raise HTTPException(503, 'AI 연결 전입니다. 로컬 .env의 GMS_KEY와 지원 모델을 설정해 주세요.')


@app.get('/')
def home():
    return FileResponse(ROOT / 'frontend/index.html')


@app.get('/api/status')
def status():
    return dict(index=counts(), places=len(load_catalog()), ai_ready=bool(os.getenv('GMS_KEY', '').strip()),
                calls=call_count(), daily_limit=limits()['daily_calls'])


@app.get('/api/places')
def places():
    return {'places': load_catalog()}


@app.post('/api/index')
def index():
    result = build_index(load_catalog())
    for saved in saved_records():
        mark_indexed(saved['id'])
    return result


class ExploreRequest(BaseModel):
    condition: str = Field(min_length=1, max_length=300)


@app.post('/api/explore')
def explore_places(body: ExploreRequest):
    require_key()
    return {'matches': explore(body.condition, search_items(body.condition))}


class Message(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    place_id: str = Field(max_length=120)
    question: str = Field(min_length=1, max_length=600)
    history: list[Message] = Field(default_factory=list, max_length=4)
    mode: Literal['similarity', 'mmr'] = 'similarity'


@app.post('/api/chat')
def chat(body: ChatRequest):
    require_key()
    started = time.perf_counter()
    state = graph.invoke(dict(item=item_by_id(body.place_id), question=body.question,
                              history=[m.model_dump() for m in body.history], search_mode=body.mode))
    result = state['result']
    return dict(answer=result['answer'], sources=[dict(source, number=number)
                for number, source in cited_sources(result['answer'], state['sources'])],
                no_citations=not bool(cited_sources(result['answer'], state['sources'])),
                cache_hit=result.get('cache_hit', False), usage=result.get('usage', {}),
                seconds=round(time.perf_counter()-started, 3))


class ResearchRequest(BaseModel):
    place_id: str = Field(max_length=120)
    question: str = Field(min_length=1, max_length=600)


@app.post('/api/research')
def research(body: ResearchRequest):
    require_key()
    return collect_for_question(item_by_id(body.place_id), body.question)


@app.post('/api/scene')
def scene(image: UploadFile = File(...), work: str = Form(..., min_length=1, max_length=100),
          media_type: Literal['영화', '드라마', '유튜브', '기타 영상'] = Form('영화'),
          hint: str = Form('', max_length=300), channel: str = Form('', max_length=80),
          compare_photos: bool = Form(True)):
    require_key()
    raw = image.file.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, '8MB 이하의 캡처를 붙여넣어 주세요.')
    started = time.perf_counter()
    try:
        result = find_scene(work, raw, hint, load_catalog(), compare_photos=compare_photos,
                            media_type=media_type, channel=channel)
    except ValueError:
        raise HTTPException(400, '이미지·입력 형식 또는 AI 사용 한도를 확인해 주세요.')
    token = uuid.uuid4().hex
    with _lock:
        now = time.monotonic()
        for key in list(_pending):
            if now-_pending[key]['created'] > 1800:
                _pending.pop(key)
        while len(_pending) >= 100:
            _pending.pop(next(iter(_pending)))
        _pending[token] = dict(created=now, result=result, work=work, media_type=media_type)
    return dict(result=result, review_token=token, seconds=round(time.perf_counter()-started, 3))


class GeocodeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)


@app.post('/api/geocode')
def geocode(body: GeocodeRequest):
    return {'points': lookup(body.query)}


class ConfirmRequest(BaseModel):
    review_token: str = Field(min_length=32, max_length=32)
    candidate_index: int = Field(ge=0, le=2)
    confirmed: bool = False
    name: str = Field(min_length=1, max_length=150)
    address: str = Field(min_length=1, max_length=300)
    region: str = Field(min_length=1, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    coordinates_confirmed: bool = False
    coordinate_source: str = Field(default='', max_length=500)


@app.post('/api/confirm')
def confirm(body: ConfirmRequest):
    if not body.confirmed:
        raise HTTPException(400, '찾던 장소가 맞는지 확인한 뒤 저장해 주세요.')
    with _lock:
        pending = _pending.get(body.review_token)
    if not pending or time.monotonic()-pending['created'] > 1800:
        raise HTTPException(410, '검수할 검색 결과가 만료됐습니다. 다시 검색해 주세요.')
    result = pending['result']
    if body.candidate_index >= len(result['candidates']):
        raise HTTPException(400, '유효하지 않은 후보입니다.')
    try:
        record = save_confirmed(candidate=result['candidates'][body.candidate_index], sources=result['sources'],
                work=pending['work'], media_type=pending['media_type'], name=body.name, address=body.address,
                region=body.region, confirmed=True, latitude=body.latitude, longitude=body.longitude,
                coordinates_confirmed=body.coordinates_confirmed, coordinate_source=body.coordinate_source)
    except ValueError as error:
        raise HTTPException(400, str(error))
    indexed = True
    try:
        build_index([record])
        mark_indexed(record['id'])
    except Exception:
        indexed = False
    return dict(place=record, indexed=indexed)
