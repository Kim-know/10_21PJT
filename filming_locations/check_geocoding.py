"""지오코더 질의 분리, 좌표 검증과 통신 오류 구분."""
from unittest.mock import patch, Mock
import requests
from services.geocoding import lookup, _lookup_one

def run():
    point = dict(label='갯골생태공원', latitude=37.39, longitude=126.78, source='https://example.com')
    with patch('services.geocoding._lookup_one', side_effect=[[], [], [], [point]]) as api:
        result = lookup('갯골생태공원 경기 시흥시 동서로 287', name='갯골생태공원', address='경기 시흥시 동서로 287')
        assert result[0]['query_used'] == '갯골생태공원'
        assert [c.args[0] for c in api.call_args_list] == ['갯골생태공원 경기 시흥시 동서로 287', '경기도 시흥시 동서로 287', '경기 시흥시 동서로 287', '갯골생태공원']
    with patch('services.geocoding._lookup_one', side_effect=requests.Timeout), patch('services.geocoding.cache.get', return_value=None):
        try:
            lookup('주소', name='공원', address='주소')
        except requests.Timeout:
            pass
        else:
            raise AssertionError('통신 실패를 빈 결과로 숨기면 안 됨')
    with patch('services.geocoding.cache.get', return_value=None), patch('services.geocoding.wait_turn'), patch('services.geocoding.requests.get') as get:
        get.return_value.json.return_value = {'features': [{'geometry': {'coordinates': [126.78, 37.39]}, 'properties': {'name':'공원'}}, {'geometry': {'coordinates':[200, 100]}}]}
        with patch('services.geocoding.cache.put'):
            points = _lookup_one('공원')
        assert len(points) == 1 and points[0]['latitude'] == 37.39
    print('PASS: split address/name fallback, no silent network failure, coordinate validation')

if __name__ == '__main__':
    run()
