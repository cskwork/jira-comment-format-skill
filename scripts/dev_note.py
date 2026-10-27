#!/usr/bin/env python3
"""Jira에 남기지 않는 개발자용 상세를 별도 개발자 노트 보드에 남긴다.

Jira 티켓 1건 = 노트 항목 1건(라벨 jira-<KEY>), Jira 댓글 1건 = 그 항목의 노트 댓글 1건.
노트 댓글에는 Jira에 게시한 기획자용 본문과 개발자용 상세를 둘 다 남긴다.
같은 Jira 댓글로 다시 실행하면 새로 달지 않고 그 노트 댓글을 고친다.

  python3 dev_note.py --key PROJ-101 --jira-comment 10101 --jira-md comment.md dev.md \\
      [--attach 101_2_데이터.png 101_3_흐름.png]

dev.md: 데이터 변화·쿼리·명령·흐름·커밋·빌드·확인 범위(마크다운). 첨부는 노트 항목에 올리고 댓글에 파일 이름을 적는다.

설정(config.env 또는 환경변수):
  DEV_NOTE_CLI        노트 보드 CLI 경로(.py면 python3로 실행). 아래 하위 명령을 지원해야 한다.
  DEV_NOTE_BASE       보드 서버 주소(CLI에 --base로 넘긴다)
  DEV_NOTE_SPACE      항목을 만들 프로젝트/스페이스 키
  DEV_NOTE_WORKSPACE  (선택) whoami의 organization.id와 다르면 멈춘다

CLI 계약 — Jira 비슷한 이슈 트래커 CLI(예: Kira CLI). 모두 JSON을 stdout으로 낸다:
  <cli> --base <BASE> whoami
  <cli> --base <BASE> search --jql '<JQL>' --limit N
  <cli> --base <BASE> issue create --project <SPACE> --json -     (stdin: summary·description·labels)
  <cli> --base <BASE> issue get <ITEM> | issue transition <ITEM> --status Done
  <cli> --base <BASE> attachment list <ITEM> | attachment upload <ITEM> <파일...>
  <cli> --base <BASE> comment list <ITEM> | comment add <ITEM> --body - | comment edit <ITEM> <ID> --body -
다른 보드(사내 위키 등)를 쓰려면 이 계약을 지키는 얇은 래퍼를 DEV_NOTE_CLI로 둔다.

마지막 줄: `devnote=ok item=<ITEM> comment=<id> created|updated` 또는 `devnote=BLOCKED <사유>`(exit 3).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skill_config import load_config  # noqa: E402


class Blocked(Exception):
    pass


def cli_cmd():
    path = os.path.expanduser(os.environ["DEV_NOTE_CLI"])
    return ([sys.executable, path] if path.endswith(".py") else [path]) + ["--base", os.environ["DEV_NOTE_BASE"]]


def note(*args, stdin=None):
    p = subprocess.run(cli_cmd() + list(args), input=stdin, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        err = ((p.stderr or p.stdout).strip().splitlines() or ["unknown"])[-1]
        if "401" in err:
            raise Blocked("노트 보드 세션 만료(401): DEV_NOTE_CLI로 다시 로그인한다")
        raise RuntimeError("devnote %s 실패: %s" % (" ".join(args[:2]), err))
    out = p.stdout.strip()
    return json.loads(out) if out[:1] in "[{" else out


def for_note(md):
    """노트 기록 규칙: Jira 링크는 글자만 남기고, 멘션·이미지 문법은 읽히는 글로 바꾼다."""
    md = re.sub(r"@\[([^\]]+)\]\([^)]+\)", r"@\1", md)
    md = re.sub(r"^!\[([^\]]*)\]\([^)]+\)\s*$", r"[이미지: \1]", md, flags=re.M)
    hosts = [r"[\w.-]*atlassian\.net"]
    if os.environ.get("JIRA_SITE"):
        hosts.append(re.escape(os.environ["JIRA_SITE"]))
    host = "(?:%s)" % "|".join(hosts)
    md = re.sub(r"\[([^\]]+)\]\(https?://%s[^)\s]*\)" % host, r"\1", md)
    return re.sub(r"<?https?://%s[^\s)>]*>?" % host, "", md)


def jira_summary(key):
    out = subprocess.run(["acli", "jira", "workitem", "view", key, "--fields", "summary", "--json"],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out)["fields"]["summary"]
    except (ValueError, KeyError):
        return ""


def rows(result, *names):
    if isinstance(result, list):
        return result
    for n in names:
        if isinstance(result, dict) and isinstance(result.get(n), list):
            return result[n]
    return []


def main(a):
    load_config()
    missing = [k for k in ("DEV_NOTE_CLI", "DEV_NOTE_BASE", "DEV_NOTE_SPACE") if not os.environ.get(k)]
    if missing:
        raise Blocked("%s 없음: config.env에 넣는다" % "·".join(missing))
    space = os.environ["DEV_NOTE_SPACE"]
    ws = os.environ.get("DEV_NOTE_WORKSPACE")
    if ws and note("whoami").get("organization", {}).get("id") != ws:
        raise Blocked("노트 보드 워크스페이스 불일치")

    label = "jira-%s" % a.key
    found = rows(note("search", "--jql", 'project = %s AND labels = "%s"' % (space, label), "--limit", "2"), "items")
    if found:
        item = found[0]["key"]
    else:
        title = a.title or jira_summary(a.key)
        item = note("issue", "create", "--project", space, "--json", "-", stdin=json.dumps({
            "summary": ("[Jira] %s %s" % (a.key, title)).strip(),
            "description": "Jira %s 처리 기록. Jira 댓글 1건마다 노트 댓글 1건(기획자용 게시본 + 개발자용 상세)." % a.key,
            "labels": [label, "jira-dev-note"]}, ensure_ascii=False))["key"]
        if note("issue", "get", item).get("status") != "Done":
            note("issue", "transition", item, "--status", "Done")

    names = []
    if a.attach:
        have = {r.get("filename") or r.get("name") for r in rows(note("attachment", "list", item), "items", "attachments")}
        new = [f for f in a.attach if Path(f).name not in have]
        for i in range(0, len(new), 5):
            note("attachment", "upload", item, *new[i:i + 5])
        names = [Path(f).name for f in a.attach]

    head = "Jira %s 댓글 %s" % (a.key, a.jira_comment)
    parts = [head, ""]
    if a.jira_md:
        parts += ["## Jira 게시본 (기획·QA용)", "", for_note(Path(a.jira_md).read_text(encoding="utf-8")).strip(), ""]
    parts += ["## 개발자용 상세", "", for_note(Path(a.dev_md).read_text(encoding="utf-8")).strip()]
    if names:
        parts += ["", "첨부(이 항목): " + ", ".join(names)]
    body = "\n".join(parts) + "\n"

    mine = [c for c in rows(note("comment", "list", item), "items", "comments")
            if (c.get("body") or "").split("\n", 1)[0].strip() == head]
    if mine:
        cid, result = mine[0]["id"], "updated"
        note("comment", "edit", item, cid, "--body", "-", stdin=body)
    else:
        cid, result = note("comment", "add", item, "--body", "-", stdin=body)["id"], "created"

    saved = [c for c in rows(note("comment", "list", item), "items", "comments") if c.get("id") == cid]
    if not saved or (saved[0].get("body") or "").strip() != body.strip():
        raise RuntimeError("%s 댓글 %s 되읽기 불일치" % (item, cid))
    print("devnote=ok item=%s comment=%s %s" % (item, cid, result))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--key", required=True, help="Jira 티켓 키")
    p.add_argument("--jira-comment", required=True, help="짝이 되는 Jira 댓글 ID(이슈 설명이면 description)")
    p.add_argument("--jira-md", help="Jira에 게시한 기획자용 마크다운")
    p.add_argument("--title", help="노트 항목 제목(없으면 Jira 요약)")
    p.add_argument("--attach", nargs="+", default=[])
    p.add_argument("dev_md")
    try:
        main(p.parse_args())
    except Blocked as e:
        print("devnote=BLOCKED %s" % e)
        sys.exit(3)
