"""클러스터 지도와 Python 장소 선택을 연결하는 양방향 컴포넌트."""
from pathlib import Path
import streamlit.components.v1 as components

_map = components.declare_component('location_cluster_map', path=str(Path(__file__).with_name('map_frontend')))


def render_location_map(places, selected_id, focus=False):
    points = [dict(id=p['id'], name=p['name'], address=p['address'], works=', '.join(p['works']),
                   lat=p['latitude'], lon=p['longitude']) for p in places
              if p.get('latitude') is not None and p.get('longitude') is not None]
    event = _map(points=points, selected=selected_id, focus=focus, key='archive_cluster_map_v2', default=None)
    return len(points), event
