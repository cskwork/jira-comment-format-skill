#!/usr/bin/env python3
"""수정 전/후 화면 캡처를 빨강·초록 라벨 띠가 붙은 이미지 1장으로 합친다.

예:
  python3 asis_tobe.py before.png after.png -o 01_asis_tobe.png \
    --before-label "수정 전 (dev) — 확인 화면에서 답이 비어 있음" \
    --after-label  "수정 후 (로컬) — 답 ③ 표시 + 정답·해설" \
    --mask-before 610,8,170,32 --mark-after 220,395,30,30 \
    --caption "계정 <테스트 계정>, YYYY-MM-DD"

좌표는 각 원본 이미지 픽셀 기준 x,y,w,h. --mask-*는 회색으로 가린다(개인정보),
--mark-*는 바뀐 곳에 테두리를 친다(전=빨강, 후=초록). 여러 번 줄 수 있다.
"""
import argparse
import os
import sys
from PIL import Image, ImageDraw, ImageFont

RED, GREEN, GRAY = (200, 35, 35), (46, 125, 50), (150, 150, 150)
# 한글 폰트 후보(macOS → Linux → Windows). ASIS_TOBE_FONT로 직접 지정 가능.
FONTS = [("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6, 0),
         ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1, 1),
         ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 1, 1),
         ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 0, 0),
         ("C:/Windows/Fonts/malgunbd.ttf", 0, 0)]


def box(s):
    x, y, w, h = (int(v) for v in s.split(","))
    return x, y, x + w, y + h


def font(size, bold=True):
    custom = os.environ.get("ASIS_TOBE_FONT")
    for path, bold_idx, reg_idx in ([(custom, 0, 0)] if custom else FONTS):
        if os.path.exists(path):
            return ImageFont.truetype(path, size, index=bold_idx if bold else reg_idx)
    sys.exit("한글 폰트를 찾지 못함: ASIS_TOBE_FONT=<ttf/ttc 경로> 지정")


def banner(text, width, color):
    f = font(26)
    h = 52
    im = Image.new("RGB", (width, h), color)
    ImageDraw.Draw(im).text((16, h // 2), text, fill="white", font=f, anchor="lm")
    return im


def prepare(path, masks, marks, color, width):
    im = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(im)
    for m in masks:
        d.rectangle(box(m), fill=GRAY)
    for m in marks:
        d.rectangle(box(m), outline=color, width=4)
    if im.width != width:
        im = im.resize((width, round(im.height * width / im.width)), Image.Resampling.LANCZOS)
    return im


def main():
    p = argparse.ArgumentParser()
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--before-label", default="수정 전")
    p.add_argument("--after-label", default="수정 후")
    p.add_argument("--caption", help="맨 아래 회색 글씨: 계정·환경·일자")
    p.add_argument("--layout", choices=["stack", "side"], default="stack",
                   help="stack=위아래(기본, 넓은 화면), side=좌우(좁은 화면)")
    for side in ("before", "after"):
        p.add_argument(f"--mask-{side}", action="append", default=[])
        p.add_argument(f"--mark-{side}", action="append", default=[])
    a = p.parse_args()

    w = max(Image.open(a.before).width, Image.open(a.after).width)
    if a.layout == "side":
        w = min(w, 900)
    panels = []
    for path, label, masks, marks, color in (
        (a.before, a.before_label, a.mask_before, a.mark_before, RED),
        (a.after, a.after_label, a.mask_after, a.mark_after, GREEN),
    ):
        shot = prepare(path, masks, marks, color, w)
        col = Image.new("RGB", (w, 52 + shot.height), "white")
        col.paste(banner(label, w, color), (0, 0))
        col.paste(shot, (0, 52))
        panels.append(col)

    gap = 16
    if a.layout == "stack":
        W, H = w, sum(c.height for c in panels) + gap
        pos = [(0, 0), (0, panels[0].height + gap)]
    else:
        W, H = w * 2 + gap, max(c.height for c in panels)
        pos = [(0, 0), (w + gap, 0)]
    cap_h = 40 if a.caption else 0
    out = Image.new("RGB", (W, H + cap_h), "white")
    for c, xy in zip(panels, pos):
        out.paste(c, xy)
    if a.caption:
        ImageDraw.Draw(out).text((12, H + cap_h // 2), a.caption, fill=(90, 90, 90),
                                 font=font(20, bold=False), anchor="lm")
    out.save(a.out)
    print(a.out, out.size)


if __name__ == "__main__":
    main()
