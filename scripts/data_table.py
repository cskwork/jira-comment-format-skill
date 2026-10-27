#!/usr/bin/env python3
"""DB 실데이터 조회 결과(As-Is / To-Be)를 엑셀(스프레드시트) 형태 PNG 이미지로 만든다.
어느 환경(로컬 / 개발(dev) / 스테이징(staging) / 운영(prod))에서 조회한 데이터인지 상단 배지와 캡션에 명시한다.

  python3 data_table.py spec.json -o 1234_2_데이터_전후.png

spec.json (전·후 분리 시트 또는 단일 비교 시트):
  {"env": "개발(dev) DB · <DB 호스트>",
   "query": "SELECT user_id, group_cd, score ... -- 핵심 조건 요약(선택)",
   "columns": ["사용자(앞8자)", "그룹", "유형", "집계 점수", "화면 표시"],
   "before": {"label": "수정 전 (As-Is) — 다른 그룹 점수가 합산됨",
              "env": "개발(dev) DB",
              "rows": [["a1b2c3d4", "GRP_02(2그룹)", "TYPE_A", {"value": "80", "hit": true}, {"value": "80점", "hit": true}]]},
   "after":  {"label": "수정 후 (To-Be) — 같은 그룹(GROUP_CD 일치)만 집계",
              "env": "개발(dev) DB",
              "rows": [["a1b2c3d4", "GRP_02(2그룹)", "TYPE_A", {"value": "NULL", "hit": true}, {"value": "- (미응시)", "hit": true}]]},
   "caption": "조회 환경: 개발(dev) DB (<DB 호스트>) 실데이터 조회 · YYYY-MM-DD"}

단일 표로 비교할 때는 before/after 대신 "sheets": [{"label": "...", "env": "...", "tone": "good", "columns": [...], "rows": [...]}] 형식도 지원한다.
셀 값은 문자열/숫자 또는 {"value": "...", "hit": true|"bad"|"good"} 로 지정한다.
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys

CSS = """
body{margin:0;padding:12px 0 4px;font-family:"Apple SD Gothic Neo","Noto Sans CJK KR","Malgun Gothic",sans-serif;background:#fff;width:1100px;color:#222}
.fx{display:flex;align-items:center;justify-content:space-between;gap:12px;background:#f3f4f6;border:1px solid #cbd5e1;border-radius:6px;padding:7px 12px;margin-bottom:12px;font-size:14px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#334155}
.fx-left{display:flex;align-items:center;min-width:0;flex:1}
.fx b{background:#e2e8f0;color:#475569;padding:2px 7px;border-radius:4px;margin-right:10px;font-style:italic;font-family:serif;font-size:15px;flex-shrink:0}
.env-pill{background:#0f172a;color:#f8fafc;font-family:"Apple SD Gothic Neo","Noto Sans CJK KR",sans-serif;font-size:13px;font-weight:700;padding:3px 10px;border-radius:999px;white-space:nowrap;flex-shrink:0}
.sheet{margin:0 0 14px;border:2px solid #94a3b8;border-radius:7px;overflow:hidden;background:#fff}
.sheet.bad{border-color:#c82323}.sheet.good{border-color:#2e7d32}
.bar{padding:8px 14px;color:#fff;font-weight:700;font-size:17px;display:flex;justify-content:space-between;align-items:center;gap:10px}
.bar .env-tag{background:rgba(255,255,255,0.22);border:1px solid rgba(255,255,255,0.45);color:#fff;font-size:13px;font-weight:700;padding:2px 9px;border-radius:4px;white-space:nowrap}
.bad .bar{background:#c82323}.good .bar{background:#2e7d32}.neutral .bar{background:#1e3a8a}
table{width:100%;border-collapse:collapse;font-size:15px;table-layout:auto}
th,td{border:1px solid #cbd5e1;padding:7px 10px;text-align:left;vertical-align:middle}
.col-hdr th{background:#e2e8f0;color:#475569;font-weight:700;text-align:center;font-size:12px;padding:3px 6px}
.tbl-hdr th{background:#f8fafc;color:#0f172a;font-weight:700;border-bottom:2px solid #94a3b8}
.rn{width:32px;background:#e2e8f0!important;color:#475569;text-align:center;font-weight:600;font-size:12px}
td.hit-bad{background:#fde8e8;color:#991b1b;font-weight:700;border:2px solid #c82323}
td.hit-good{background:#dcfce7;color:#166534;font-weight:700;border:2px solid #2e7d32}
.cap{font-size:14px;color:#475569;font-weight:600;margin-top:-4px}
"""


def col_letter(idx):
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def norm_sheets(spec):
    if "sheets" in spec:
        return spec["sheets"]
    out = []
    for key, tone, dflt in (("before", "bad", "수정 전 (As-Is)"), ("after", "good", "수정 후 (To-Be)")):
        if key in spec and spec[key]:
            sec = spec[key]
            out.append({
                "label": sec.get("label", dflt),
                "env": sec.get("env") or spec.get("env", ""),
                "tone": sec.get("tone", tone),
                "columns": sec.get("columns") or spec.get("columns", []),
                "rows": sec.get("rows", []),
            })
    return out


def render_html(spec):
    e = html.escape
    parts = []
    top_env = spec.get("env", "")
    if spec.get("query") or top_env:
        q_html = f'<div class="fx-left"><b>fx</b><span>{e(spec.get("query", ""))}</span></div>' if spec.get("query") else '<div class="fx-left"></div>'
        env_html = f'<span class="env-pill">조회 환경: {e(top_env)}</span>' if top_env else ""
        parts.append(f'<div class="fx">{q_html}{env_html}</div>')
    for sh in norm_sheets(spec):
        tone = sh.get("tone", "neutral")
        cols = sh.get("columns", [])
        sh_env = sh.get("env") or top_env
        env_tag = f'<span class="env-tag">환경: {e(sh_env)}</span>' if sh_env else ""
        letters = "".join(f"<th>{col_letter(i)}</th>" for i in range(len(cols)))
        headers = "".join(f"<th>{e(str(c))}</th>" for c in cols)
        body_rows = []
        for r_idx, row in enumerate(sh.get("rows", []), start=2):
            tds = [f'<td class="rn">{r_idx}</td>']
            for cell in row:
                if isinstance(cell, dict):
                    val = e(str(cell.get("value", "")))
                    hit = cell.get("hit")
                    cls = f' class="hit-{"bad" if (hit is True and tone == "bad") or hit == "bad" else "good"}"' if hit else ""
                else:
                    val, cls = e(str(cell)), ""
                tds.append(f"<td{cls}>{val.replace(chr(10), '<br>')}</td>")
            body_rows.append(f"<tr>{''.join(tds)}</tr>")
        parts.append(
            f'<div class="sheet {e(tone)}"><div class="bar"><span>{e(sh.get("label", ""))}</span>{env_tag}</div>'
            f'<table><thead><tr class="col-hdr"><th class="rn"></th>{letters}</tr>'
            f'<tr class="tbl-hdr"><th class="rn">1</th>{headers}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table></div>'
        )
    if spec.get("caption"):
        parts.append(f'<div class="cap">{e(spec["caption"])}</div>')
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(parts)}</body></html>'


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
