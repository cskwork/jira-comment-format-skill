#!/usr/bin/env python3
"""게시한 본문·댓글을 되읽어 서식 노드와 인라인 이미지 수를 확인한다.

  acli jira workitem view PRJ-1234 --fields description,comment --json 2>/dev/null \
    | python3 check_adf.py --comment 10101 --min-media 3
  ... | python3 check_adf.py --description --min-media 1

media 수가 --min-media보다 적거나, 마크다운·JSON 문자열이 본문에 그대로 들어가 있거나,
기획자용 검사(planner_lint.py: 커밋·빌드·코드 이름·코드 블록·댓글 번호 참조·길이)에 걸리면 종료 코드 1.
개발자용 상세는 Jira가 아니라 dev_note.py로 개발자 노트에 남긴다. --min-code는 이전 호환용이다.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planner_lint  # noqa: E402


def walk(n, cnt, media, texts):
    if isinstance(n, dict):
        cnt[n.get("type")] += 1
        if n.get("type") == "media":
            media.append(n["attrs"].get("alt") or n["attrs"].get("id"))
        texts.append(n.get("text", ""))
        for c in n.get("content", []):
            walk(c, cnt, media, texts)


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--comment")
    g.add_argument("--description", action="store_true")
    p.add_argument("--max-chars", type=int, help=f"본문 글자 상한(기본: 댓글 {planner_lint.MAX_CHARS}, 이슈 설명 0=끄기)")
    planner_lint.add_args(p)
    p.add_argument("--min-media", type=int, default=0)
    p.add_argument("--min-code", type=int, default=0, help="쿼리 등 복사용 codeBlock 최소 수")
    p.add_argument("--min-mention", type=int, default=0, help="특정 사용자에게 요청·답할 때 mention 노드 최소 수")
    a = p.parse_args()
    f = json.load(sys.stdin)["fields"]
    if a.description:
        body, meta = f["description"], {}
    else:
        c = next((c for c in f["comment"]["comments"] if c["id"] == a.comment), None)
        if not c:
            sys.exit(f"댓글 {a.comment} 없음")
        body, meta = c["body"], {"author": c["author"]["displayName"], "updated": c["updated"],
                                 "comments": len(f["comment"]["comments"])}
    cnt, media, texts = collections.Counter(), [], []
    walk(body, cnt, media, texts)
    leak = [s for s in ("**", "|---", '{"type"', "](http") if any(s in t for t in texts)]
    # Jira 글은 기획·QA용만. 개발자용 내용이 남아 있으면 실패
    max_chars = a.max_chars
    if max_chars is None:
        max_chars = 0 if a.description else planner_lint.MAX_CHARS
    planner = planner_lint.lint(body, max_chars, a.allow, a.pattern)
    planner_lint.report(planner)
    leak += [name for name, _ in planner]
    print(json.dumps({**meta, "nodes": dict(cnt), "media": media, "leak": leak}, ensure_ascii=False, indent=1))
    if len(media) < a.min_media or cnt["codeBlock"] < a.min_code or cnt["mention"] < a.min_mention or leak:
        sys.exit(1)


if __name__ == "__main__":
    main()
