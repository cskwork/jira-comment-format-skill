#!/usr/bin/env python3
"""논리 흐름·시나리오의 변화 흐름을 '수정 전 / 수정 후' 두 줄 흐름도 PNG로 만든다.

  python3 flow_diagram.py spec.json -o 1234_3_논리흐름_전후.png

spec.json:
  {"env": "개발(dev) 반영 · <서비스 이름>",
   "rows": [
     {"label": "수정 전", "tone": "bad",
      "steps": [{"title": "① 선생님", "text": "탭에서 문제 해제"},
                {"title": "② 저장", "text": "해제를 저장 안 함", "hit": true}]},
     {"label": "수정 후", "tone": "good",
      "steps": [{"title": "① 선생님", "text": "탭에서 문제 해제"},
                {"title": "② 저장", "text": "세 탭 모두 저장", "hit": true}]}],
   "caption": "확인 환경: 개발(dev) · YYYY-MM-DD"}

hit=true인 단계는 행 색 테두리로 강조한다. 바로 위 Jira 제목과 같은 제목은 넣지 않는다.
렌더링은 agent-browser(없으면 HTML 경로만 출력)로 한다.
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys

CSS = """
body{margin:0;padding:12px 0 4px;font-family:"Apple SD Gothic Neo","Noto Sans CJK KR","Malgun Gothic",sans-serif;background:#fff;width:1100px}
.top-env{display:flex;justify-content:flex-end;margin-bottom:8px}
.env-pill{background:#0f172a;color:#f8fafc;font-size:13px;font-weight:700;padding:3px 10px;border-radius:999px}
.row{display:flex;margin:0 0 18px}
.tag{width:120px;color:#fff;font-weight:700;font-size:20px;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:8px 0 0 8px;text-align:center;padding:6px}
.tag small{font-size:12px;font-weight:600;opacity:0.9;margin-top:3px}
.steps{flex:1;display:flex;align-items:center;gap:10px;padding:16px;border:2px solid;border-left:none;border-radius:0 8px 8px 0}
.bad .tag{background:#c82323}.bad .steps{border-color:#c82323;background:#fdf1f1}.bad .hit{border:2px solid #c82323}
.good .tag{background:#2e7d32}.good .steps{border-color:#2e7d32;background:#f1f8f1}.good .hit{border:2px solid #2e7d32}
.box{flex:1;background:#fff;border:1px solid #ccc;border-radius:8px;padding:12px 14px;font-size:17px;line-height:1.45;min-height:80px}
.box b{display:block;font-size:14px;color:#555;margin-bottom:4px}
.arr{font-size:26px;color:#888}.cap{font-size:14px;color:#475569;font-weight:600;margin-top:-6px}
"""


def render_html(spec):
    e = html.escape
    top = f'<div class="top-env"><span class="env-pill">적용·확인 환경: {e(spec["env"])}</span></div>' if spec.get("env") else ""
    rows = []
    for r in spec["rows"]:
        steps = '<div class="arr">→</div>'.join(
            f'<div class="box{" hit" if s.get("hit") else ""}"><b>{e(s.get("title", ""))}</b>'
            f'{e(s["text"]).replace(chr(10), "<br>")}</div>' for s in r["steps"])
        lbl = e(r["label"]).replace("\n", "<br>")
        sub = f'<small>{e(r["env"])}</small>' if r.get("env") else ""
        rows.append(f'<div class="row {e(r.get("tone", "bad"))}"><div class="tag">{lbl}{sub}</div>'
                    f'<div class="steps">{steps}</div></div>')
    cap = f'<div class="cap">{e(spec["caption"])}</div>' if spec.get("caption") else ""
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{top}{"".join(rows)}{cap}</body></html>'


def is_blank(path):
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        return im.getextrema() == ((255, 255), (255, 255), (255, 255))
    except Exception:
        return False


def main():
    import time
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()
    out = os.path.abspath(a.out)
    page = os.path.splitext(out)[0] + ".html"
    with open(page, "w", encoding="utf-8") as f:
        f.write(render_html(json.load(open(a.spec, encoding="utf-8"))))
    ab = shutil.which("agent-browser")
    if not ab:
        sys.exit(f"agent-browser 없음: {page} 를 브라우저로 열어 1100px 폭으로 캡처")
    run = lambda *args: subprocess.run([ab, *args], capture_output=True, text=True)
    for attempt in range(3):
        run("open", f"file://{page}")
        run("set", "viewport", "1100", "800")
        h_out = run("eval", "document.body ? document.body.scrollHeight : 0").stdout.strip().splitlines()
        height = h_out[-1] if h_out and h_out[-1].isdigit() and int(h_out[-1]) > 50 else "400"
        run("set", "viewport", "1100", height)
        shot = run("screenshot", out)
        if shot.returncode == 0 and os.path.exists(out) and not is_blank(out):
            break
        time.sleep(0.4)
    run("close")
    if not os.path.exists(out) or is_blank(out):
        sys.exit("캡처 실패(빈 화면)")
    print(out)


if __name__ == "__main__":
    main()
