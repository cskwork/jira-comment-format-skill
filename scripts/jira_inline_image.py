#!/usr/bin/env python3
"""Jira 본문·댓글 안에 넣을 이미지 ADF 노드(mediaSingle)를 만든다.

acli에는 첨부 업로드가 없어서 업로드만 REST로 한다. acli에 로그인한 계정과 같은
계정의 API 토큰을 쓰므로 작성자는 같다. 본문·댓글 게시는 계속 acli로 한다.

  # 새 이미지 업로드 → 노드 출력
  python3 jira_inline_image.py --key PRJ-1234 01_asis_tobe.png 02_flow.png > nodes.json
  # 이미 올라간 첨부를 본문에 넣기만
  python3 jira_inline_image.py --key PRJ-1234 --attachment-id 43471 43472 > nodes.json

출력: [{"file", "attachmentId", "mediaId", "node"}] — node를 ADF content에 그대로 넣는다.
Jira 구조상 인라인 이미지도 이슈 첨부 목록에 함께 보인다.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from io import BytesIO

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skill_config import load_config  # noqa: E402,F401  (다른 스크립트가 여기서도 가져간다)

TOKEN_FILES = ["~/.config/jira/token"]
SITE = ""


def acli_profile():
    # acli에 로그인한 계정을 그대로 쓴다(작성자를 acli 게시와 맞추기 위해).
    try:
        out = subprocess.run(["acli", "jira", "auth", "status"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return {}
    return dict(re.findall(r"^\s*(Site|Email):\s*(\S+)", out, re.M))


def auth():
    """JIRA_SITE/JIRA_EMAIL → 없으면 acli 로그인 정보. 토큰은 JIRA_API_TOKEN → JIRA_TOKEN_FILE → TOKEN_FILES."""
    global SITE
    load_config()
    prof = acli_profile() if not (os.environ.get("JIRA_SITE") and os.environ.get("JIRA_EMAIL")) else {}
    SITE = os.environ.get("JIRA_SITE") or prof.get("Site", "")
    email = os.environ.get("JIRA_EMAIL") or prof.get("Email", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    if not token:
        files = [os.environ["JIRA_TOKEN_FILE"]] if os.environ.get("JIRA_TOKEN_FILE") else TOKEN_FILES
        path = next((p for p in map(os.path.expanduser, files) if os.path.exists(p)), None)
        if path:
            with open(path) as f:
                token = f.read().strip()
    if not (SITE and email and token):
        sys.exit("Jira 인증 정보 없음: acli jira auth login 후 JIRA_API_TOKEN 또는 JIRA_TOKEN_FILE(기본 ~/.config/jira/token)을 설정")
    return f"{email}:{token}"


def upload(key, path, cred):
    # 토큰이 프로세스 목록(ps)에 보이지 않게 인증은 명령줄 대신 stdin 설정(-K -)으로 넘긴다.
    user = cred.replace("\\", "\\\\").replace('"', '\\"')
    r = subprocess.run(
        ["curl", "-sS", "-f", "-K", "-", "-X", "POST", "-H", "X-Atlassian-Token: no-check",
         "-F", f"file=@{path}", f"https://{SITE}/rest/api/3/issue/{key}/attachments"],
        input=f'user = "{user}"\n', capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"업로드 실패 {path}: {r.stderr.strip()}")
    return json.loads(r.stdout)[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def request(path, cred):
    req = urllib.request.Request(f"https://{SITE}/rest/api/3/{path}")
    req.add_header("Authorization", "Basic " + base64.b64encode(cred.encode()).decode())
    return req


def attachment_name(att_id, cred):
    with urllib.request.urlopen(request(f"attachment/{att_id}", cred)) as r:
        return json.load(r)["filename"]


def size_of(att_id, cred):
    with urllib.request.urlopen(request(f"attachment/content/{att_id}", cred)) as r:
        return Image.open(BytesIO(r.read())).size


def media_id(att_id, cred):
    # 첨부 본문 URL은 303으로 media 서비스(/file/<mediaId>/binary)로 보낸다.
    req = request(f"attachment/content/{att_id}", cred)
    try:
        urllib.request.build_opener(NoRedirect).open(req)
    except urllib.error.HTTPError as e:
        m = re.search(r"/file/([0-9a-f-]{36})/", e.headers.get("Location", ""))
        if m:
            return m.group(1)
        sys.exit(f"mediaId 확인 실패 attachment {att_id}: HTTP {e.code}")
    sys.exit(f"mediaId 확인 실패 attachment {att_id}: 리다이렉트 없음")


def node(mid, alt, size, max_width):
    # media의 width/height(원본 px)가 없으면 Jira가 4:5 고정 칸을 잡아 빈 공간이 생기거나 이미지가 줄어든다.
    w, h = size
    return {"type": "mediaSingle", "attrs": {"layout": "align-start", "width": min(w, max_width), "widthType": "pixel"},
            "content": [{"type": "media", "attrs": {"type": "file", "id": mid, "collection": "", "alt": alt,
                                                    "width": w, "height": h}}]}


def resolve(key, item, cred, max_width=760, existing=False):
    """파일 경로(업로드) 또는 기존 첨부 ID → {file, attachmentId, mediaId, node}."""
    if existing:
        att_id, name, size = item, attachment_name(item, cred), size_of(item, cred)
    else:
        size = Image.open(item).size
        att = upload(key, item, cred)
        att_id, name = att["id"], att["filename"]
    mid = media_id(att_id, cred)
    return {"file": name, "attachmentId": att_id, "mediaId": mid, "node": node(mid, name, size, max_width)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--key", required=True)
    p.add_argument("--attachment-id", action="store_true", help="인자를 파일 대신 기존 첨부 ID로 본다")
    p.add_argument("--width", type=int, default=760, help="본문 최대 표시 폭(px), 원본이 더 좁으면 원본 폭")
    p.add_argument("items", nargs="+")
    a = p.parse_args()
    cred = auth()
    out = [resolve(a.key, it, cred, a.width, a.attachment_id) for it in a.items]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
