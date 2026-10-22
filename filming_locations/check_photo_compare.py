"""비교 사진 선택, 원본 병렬 표시, 미확보 안내. 실제 AI 호출 없음."""
from streamlit.testing.v1 import AppTest

CODE='''
import io
from PIL import Image
from ui.photo_compare import render_photo_compare
image=io.BytesIO();Image.new('RGB',(40,30),'#87b9a4').save(image,'PNG')
render_photo_compare(image.getvalue(),[
 {'id':1,'title':'검색 사진','image_url':'https://example.com/a.jpg','url':'https://example.com/a'},
 {'id':2,'title':'모델 비교 사진','image_url':'https://example.com/b.jpg','url':'https://example.com/b'}],{'reference_ids':[2]},'test')
'''

def run():
    app=AppTest.from_string(CODE).run()
    assert not app.exception
    assert len(app.get('image'))==2
    assert app.selectbox[0].options[0]=='모델 비교 사진'
    app.selectbox[0].select(1).run()
    assert not app.exception and any('채택된 사진은 아닙니다' in c.value for c in app.caption)
    empty=AppTest.from_string("from ui.photo_compare import render_photo_compare\nrender_photo_compare(b'',[],{'reference_ids':[]},'empty')").run()
    assert not empty.exception and any('확보한 참고사진이 없습니다' in c.value for c in empty.caption)
    print('PASS: original/reference pair, model-used photo priority, selector, evidence distinction, missing-reference notice')

if __name__=='__main__':run()

