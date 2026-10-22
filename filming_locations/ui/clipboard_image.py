"""권한 팝업 없이 사용자가 실행한 이미지 paste 이벤트를 받는 컴포넌트."""
import base64
import binascii

import streamlit as st
from streamlit.components.v2 import component

HTML = '''<div class="paste-box" role="textbox" aria-label="스크린샷 붙여넣기 영역" tabindex="0">
  <img class="capture-preview" alt="붙여넣은 장면 미리보기" hidden>
  <div class="icon" aria-hidden="true">▧</div>
  <strong>여기를 클릭하고 Ctrl+V</strong>
  <p>복사한 스크린샷을 붙여넣으세요</p>
  <small>Windows: Win+Shift+S로 캡처 후 붙여넣기<br>Mac: Control+Shift+Command+4로 복사 후 Command+V</small>
</div><div class="paste-status" role="status" aria-live="polite"></div>
<button class="clear" type="button" hidden>붙인 이미지 지우기</button>'''

CSS = '''@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');
@font-face {font-family:'Gowun Dodum';font-style:normal;font-weight:400;font-display:swap;src:url('https://fonts.gstatic.com/s/gowundodum/v12/3Jn5SD_00GqwlBnWc1TUJF0F.ttf') format('truetype');}
.paste-box,.paste-status,.clear{font-family:'Gowun Dodum','Malgun Gothic',sans-serif;line-height:1.8;}
.paste-box{border:2px dashed #c5ceda;border-radius:12px;padding:24px 16px;
text-align:center;cursor:text;color:var(--st-text-color,#243247);background:var(--st-secondary-background-color,#f8fafc);outline:none;}
.paste-box:focus{border-color:#f45a69;box-shadow:0 0 0 3px #f45a691a;}
.icon{font-size:32px;margin-bottom:12px;color:#64748b;}
strong{font-size:17px;}p{font-size:14px;margin:9px 0;}small{font-size:12px;line-height:1.8;color:#64748b;}
.paste-status{font-size:13px;margin:10px 0;color:var(--st-text-color,#243247);}
.clear{border:1px solid #cbd5e1;border-radius:8px;background:transparent;color:var(--st-text-color,#243247);padding:7px 12px;cursor:pointer;}
.paste-box{min-height:290px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;align-items:center;background:#202823;color:#f4f0e5;border:1px dashed #8e9f8c;border-radius:5px;padding:24px 16px}.paste-box:focus{border-color:#e7d9b6;box-shadow:0 0 0 3px #e7d9b622}.icon{color:#d7c59e}small{color:#b2c0b3}.paste-status{color:#c9d5c8}.clear{border-color:#82917f;color:#e6eddf;border-radius:4px}
.capture-preview{display:block;width:100%;max-height:310px;object-fit:contain;border-radius:3px}.paste-box.has-image{padding:12px}
.paste-box,.paste-status,.clear{font-family:'Malgun Gothic',sans-serif}.paste-box{background:#f3f3f1;color:#25292b;border:1px dashed #9ba2a4;border-radius:0;min-height:310px}.paste-box:focus{border-color:#ad382d;box-shadow:0 0 0 2px #ad382d22}.icon{color:#3e464a}small{color:#5d6569}.paste-status{color:#424a4e}.clear{color:#24292c;border-color:#999;border-radius:0}.paste-box,.paste-status,.clear{font-family:'Noto Sans KR','Malgun Gothic',sans-serif;font-synthesis:none}.paste-box strong{font-size:18px;font-weight:700}.paste-box p{font-size:15px;font-weight:500}.paste-box small{font-size:13px;line-height:1.8;color:#535d62}[hidden]{display:none!important;}'''

JS = r'''export default function({parentElement, data, setStateValue}) {
  const box = parentElement.querySelector('.paste-box');
  const status = parentElement.querySelector('.paste-status');
  const preview = parentElement.querySelector('.capture-preview');
  const guide = box.querySelectorAll('.icon,strong,p,small');
  const clear = parentElement.querySelector('.clear');
  let active = true;
  let reader = null;
  let sequence = 0;
  function render(value) {
    const shown = typeof value?.data_url === 'string' && /^data:image\/(png|jpeg|webp);base64,/.test(value.data_url);
    preview.hidden = !shown;
    if (shown) preview.src = value.data_url; else preview.removeAttribute('src');
    guide.forEach(el => {el.hidden = shown;});
    box.classList.toggle('has-image', shown);
    status.textContent = value ? '스크린샷이 준비됐어요. 다시 붙여넣으면 새 이미지로 바뀝니다.' : '';
    clear.hidden = !value;
  }
  render(data?.image);
  const click = () => box.focus();
  const paste = event => {
    const item = Array.from(event.clipboardData?.items || []).find(item => item.type.startsWith('image/'));
    if (!item) return; // 작품명·장면 설명의 일반 텍스트 붙여넣기는 그대로 둔다.
    event.preventDefault();
    const file = item.getAsFile();
    if (!file) return;
    if (!['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 8 * 1024 * 1024) {
      status.textContent = '8MB 이하의 PNG·JPG·WEBP 캡처를 붙여넣어 주세요.';
      return;
    }
    const current = ++sequence;
    if (reader?.readyState === 1) reader.abort();
    reader = new FileReader();
    reader.onload = () => {
      if (!active || current !== sequence) return;
      const value = {data_url: reader.result, name: file.name || 'clipboard.png'};
      render(value);
      setStateValue('image', value);
    };
    reader.onerror = () => { if (active) status.textContent = '스크린샷을 읽지 못했습니다. 다시 복사해 주세요.'; };
    reader.readAsDataURL(file);
  };
  const reset = () => { ++sequence; render(null); setStateValue('image', null); };
  box.addEventListener('click', click);
  document.addEventListener('paste', paste, true);
  clear.addEventListener('click', reset);
  return () => {
    active = false;
    if (reader?.readyState === 1) reader.abort();
    document.removeEventListener('paste', paste, true);
    box.removeEventListener('click', click);
    clear.removeEventListener('click', reset);
  };
}'''

_paste = component("scene_clipboard_image", html=HTML, css=CSS, js=JS)


def decode_image(value):
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("data_url"), str):
        raise ValueError("붙여넣은 이미지 형식이 올바르지 않습니다.")
    data_url = value["data_url"]
    prefix, separator, encoded = data_url.partition(",")
    if prefix not in {"data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"} or not separator:
        raise ValueError("PNG·JPG·WEBP 스크린샷을 붙여넣어 주세요.")
    if len(encoded) > (8 * 1024 * 1024 + 2) // 3 * 4:
        raise ValueError("스크린샷은 8MB 이하로 붙여넣어 주세요.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("스크린샷 데이터를 읽지 못했습니다.") from error
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise ValueError("스크린샷은 8MB 이하로 붙여넣어 주세요.")
    return raw


def clipboard_image(key="scene_clipboard"):
    stored = st.session_state.get(key)
    initial = stored.get("image") if stored else None
    state = _paste(key=key, data={"image": initial}, default={"image": None},
                   on_image_change=lambda: None)
    return decode_image(state.get("image"))
