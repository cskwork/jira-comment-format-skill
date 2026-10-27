#!/usr/bin/env python3
"""간단한 마크다운을 Jira ADF로 바꾸고, 이미지는 업로드해 본문 인라인으로 넣는다.

  python3 md_to_adf.py --key PRJ-1234 comment.md -o comment.adf.json
  acli jira workitem comment create --key PRJ-1234 --body-file comment.adf.json
  acli jira workitem comment update --key PRJ-1234 --id <ID> --body-adf comment.adf.json

지원하는 문법 (Jira가 마크다운을 렌더링하지 않으므로 이 범위만 쓴다):
  # ~ ######  제목              - / *  글머리 목록       1.  번호 목록
  | a | b |   표(첫 줄 = 머리)  ```lang  코드 블록
  > [!NOTE] / [!INFO] / [!WARNING] / [!SUCCESS] / [!ERROR]  패널(이어지는 > 줄 포함)
  ![설명](파일.png)            업로드 후 인라인 이미지
  ![설명](attachment:43475)    이미 올린 첨부를 인라인 이미지로
  ![설명](파일.sql)            이미지가 아닌 파일은 업로드 후 파일 카드(개발자 확인용 쿼리 등)
  인라인: **굵게**  `코드`  [글자](https://링크)  @[표시 이름](accountId) → 멘션(알림)
빈 줄이 문단을 나누고, 문단 안 줄바꿈은 줄바꿈(hardBreak)으로 유지한다.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# @[표시 이름](accountId) → Jira mention 노드(알림 발송). accountId는 이슈 reporter/assignee/댓글 author에서 얻는다.
INLINE = re.compile(r"@\[([^\]]+)\]\(([0-9a-f]+:[0-9a-f-]+|[0-9a-f]{24})\)|\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?://[^)\s]+)\)")
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
PANEL = re.compile(r"^>\s*\[!(NOTE|INFO|WARNING|SUCCESS|ERROR)\]\s*(.*)$", re.I)


def inline(text):
    out, pos = [], 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            out.append({"type": "text", "text": text[pos:m.start()]})
        if m.group(1):
            out.append({"type": "mention", "attrs": {"id": m.group(2), "text": "@" + m.group(1)}})
        elif m.group(3):
            out.append({"type": "text", "text": m.group(3), "marks": [{"type": "strong"}]})
        elif m.group(4):
            out.append({"type": "text", "text": m.group(4), "marks": [{"type": "code"}]})
        else:
            out.append({"type": "text", "text": m.group(5),
                        "marks": [{"type": "link", "attrs": {"href": m.group(6)}}]})
        pos = m.end()
    if pos < len(text):
        out.append({"type": "text", "text": text[pos:]})
    return out


def paragraph(lines):
    content = []
    for i, line in enumerate(lines):
        if i:
            content.append({"type": "hardBreak"})
        content += inline(line.strip())
    return {"type": "paragraph", "content": content}


def cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def table(rows):
    rows = [r for r in rows if not re.fullmatch(r"\|?[\s:|-]+\|?", r.strip())]
    return {"type": "table", "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
            "content": [{"type": "tableRow", "content": [
                {"type": "tableHeader" if i == 0 else "tableCell", "content": [paragraph([c])]}
                for c in cells(r)]} for i, r in enumerate(rows)]}


def convert(md, image):
    """image(alt, src) → mediaSingle 노드. 블록 단위로 ADF content를 만든다."""
    lines, blocks, i = md.splitlines(), [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
        elif s.startswith("```"):
            lang, body = s[3:].strip(), []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            node = {"type": "codeBlock", "content": [{"type": "text", "text": "\n".join(body)}]}
            if lang:
                node["attrs"] = {"language": lang}
            blocks.append(node)
        elif m := re.match(r"^(#{1,6})\s+(.*)$", s):
            blocks.append({"type": "heading", "attrs": {"level": len(m.group(1))}, "content": inline(m.group(2))})
            i += 1
        elif m := IMAGE.match(s):
            blocks.append(image(m.group(1), m.group(2)))
            i += 1
        elif m := PANEL.match(s):
            body = [m.group(2)] if m.group(2) else []
            i += 1
            while i < len(lines) and lines[i].strip().startswith(">"):
                body.append(lines[i].strip()[1:].strip())
                i += 1
            blocks.append({"type": "panel", "attrs": {"panelType": m.group(1).lower()},
                           "content": [paragraph([b]) for b in body if b]})
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            blocks.append(table(rows))
        elif re.match(r"^([-*]|\d+\.)\s+", s):
            ordered = bool(re.match(r"^\d+\.", s))
            items = []
            while i < len(lines) and re.match(r"^([-*]|\d+\.)\s+", lines[i].strip()):
                items.append(re.sub(r"^([-*]|\d+\.)\s+", "", lines[i].strip()))
                i += 1
            blocks.append({"type": "orderedList" if ordered else "bulletList",
                           "content": [{"type": "listItem", "content": [paragraph([t])]} for t in items]})
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(
                    r"^(#{1,6}\s|```|>|\||[-*]\s|\d+\.\s|!\[)", lines[i].strip()):
                para.append(lines[i])
                i += 1
            blocks.append(paragraph(para))
    return {"version": 1, "type": "doc", "content": blocks}


def main():
    import planner_lint
    p = argparse.ArgumentParser()
    p.add_argument("--key", help="이미지가 있으면 필수: 업로드할 이슈 키")
    p.add_argument("--width", type=int, default=760, help="이미지 최대 표시 폭(px)")
    p.add_argument("--max-chars", type=int, default=planner_lint.MAX_CHARS, help="본문 글자 상한, 이슈 설명은 0")
    planner_lint.add_args(p)
    p.add_argument("md")
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()
    base = os.path.dirname(os.path.abspath(a.md))
    state = {}
    md = open(a.md, encoding="utf-8").read()

    # 업로드 전에 기획자용 검사: 개발자용 내용은 Jira가 아니라 dev_note.py로 개발자 노트에 남긴다.
    found = planner_lint.lint(convert(md, lambda alt, src: {"type": "mediaSingle"}), a.max_chars, a.allow, a.pattern)
    if found:
        planner_lint.report(found)
        sys.exit(1)

    def image(alt, src):
        if not a.key:
            sys.exit(f"첨부 {src}: --key 필요")
        if "cred" not in state:
            import jira_inline_image as jii
            state["jii"], state["cred"] = jii, jii.auth()
        jii, cred = state["jii"], state["cred"]
        if src.startswith("attachment:"):
            r = jii.resolve(a.key, src.split(":", 1)[1], cred, a.width, existing=True)
        else:
            r = jii.resolve(a.key, os.path.join(base, src), cred, a.width)
        if alt and r["node"]["type"] == "mediaSingle":
            r["node"]["content"][0]["attrs"]["alt"] = alt
        print(f"첨부 {src} → attachment {r['attachmentId']}", file=sys.stderr)
        return r["node"]

    doc = convert(md, image)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    print(a.out)


if __name__ == "__main__":
    main()
