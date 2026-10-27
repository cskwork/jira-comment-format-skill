#!/usr/bin/env python3
"""Jira 글은 기획·QA가 읽는다. 개발자용 내용이 섞이면 찾아낸다.

개발자용 상세(데이터·쿼리·흐름도·커밋·빌드·운영 실행 순서)는 Jira에 남기지 않고
dev_note.py로 개발자 노트 보드에 남긴다. md_to_adf.py(게시 전)와 check_adf.py(되읽기)가 쓴다.

  python3 planner_lint.py comment.adf.json [--max-chars 800] [--allow 용어] [--pattern 정규식]

프로젝트 고유 이름(저장소·서비스·모듈 이름 등)은 --pattern 또는 환경변수 PLANNER_LINT_EXTRA
(config.env에 둘 수 있음)에 정규식으로 더한다. 예: PLANNER_LINT_EXTRA='\\bmyapp-(?:api|web)\\b'
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skill_config import load_config  # noqa: E402

MAX_CHARS = 800  # 댓글 본문 글자 수 상한(멘션·이미지 제외). 이슈 설명은 0(끄기)

RULES = [
    ("커밋 해시", r"(?<![\w-])(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}(?![\w-])"),
    ("빌드 번호", r"(?<!\w)#\d{2,4}\b"),
    ("브랜치", r"\b(?:fix|feat|feature|hotfix|bugfix|release|merge)/[\w.-]+"),
    ("개발 용어", r"\b(?:API|SQL|Redis|curl|JSON|Jenkins|Kafka|JWT|HTTP|SELECT|UPDATE|INSERT|DELETE|JOIN|"
                 r"null|true|false|hash|payload|endpoint|commit|merge|branch|pod|token|query|schema)\b"
                 r"|커밋|머지|병합|빌드|파드|토큰|쿼리|스키마|컬럼|테이블|인덱스|마이그레이션|브랜치|단위 시험"),
    ("코드 이름", r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b|\b[a-z][a-z0-9]*_[a-z0-9_]+\b"
                 r"|\b[a-z]+(?:[A-Z][a-z0-9]+)+\b|\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+){2,}\b"
                 r"|\b\w+\.(?:java|kt|xml|vue|ts|tsx|js|py|go|rb|sql)\b|\b[A-Z]\d{3}\b"),
    ("댓글 번호 참조(링크+한 줄 요약으로)", r"댓글\s*\d{5}"),
    ("'해당 없음' 절(절째 뺀다)", r"해당\s*없음"),
]


def extra_rules(patterns=()):
    """--pattern 값과 PLANNER_LINT_EXTRA(쉼표 대신 줄바꿈 또는 '||'로 여러 개)를 프로젝트 규칙으로 더한다."""
    load_config()
    env = os.environ.get("PLANNER_LINT_EXTRA", "")
    pats = [p for p in re.split(r"\n|\|\|", env) if p.strip()] + list(patterns)
    return [("프로젝트 고유 이름", p.strip()) for p in pats]


def collect(node, texts, marks, nodes):
    if isinstance(node, dict):
        t = node.get("type")
        nodes.append(t)
        if t == "text":
            texts.append(node.get("text", ""))
            marks.extend(m.get("type") for m in node.get("marks", []))
        for c in node.get("content", []) or []:
            collect(c, texts, marks, nodes)


def lint(doc, max_chars=MAX_CHARS, allow=(), patterns=()):
    """문제 목록 [(규칙, 예시)]을 돌려준다. 비어 있으면 통과."""
    texts, marks, nodes = [], [], []
    collect(doc, texts, marks, nodes)
    body = "\n".join(texts)
    found = []
    for name, pat in RULES + extra_rules(patterns):
        hits = sorted({m.group(0) for m in re.finditer(pat, body)} - set(allow))
        if hits:
            found.append((name, ", ".join(hits[:5])))
    if "codeBlock" in nodes:
        found.append(("코드 블록", "쿼리·명령은 개발자 노트로"))
    if "code" in marks:
        found.append(("코드 서식", "`...` 대신 화면 이름·메뉴 경로로"))
    chars = len(re.sub(r"\s+", "", body))
    if max_chars and chars > max_chars:
        found.append(("길이", f"{chars}자 > {max_chars}자"))
    return found


def report(found, out=sys.stderr):
    for name, ex in found:
        print(f"기획자용 검사 실패 — {name}: {ex}", file=out)


def add_args(p):
    """md_to_adf.py·check_adf.py와 같은 검사 옵션."""
    p.add_argument("--allow", action="append", default=[], help="기획자도 아는 용어로 확인한 것만 허용")
    p.add_argument("--pattern", action="append", default=[],
                   help="프로젝트 고유 이름 정규식(여러 번 가능, PLANNER_LINT_EXTRA와 합쳐짐)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("adf")
    p.add_argument("--max-chars", type=int, default=MAX_CHARS)
    add_args(p)
    a = p.parse_args()
    found = lint(json.load(open(a.adf, encoding="utf-8")), a.max_chars, a.allow, a.pattern)
    report(found)
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
