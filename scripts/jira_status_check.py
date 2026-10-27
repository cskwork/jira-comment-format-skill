#!/usr/bin/env python3
"""배포 단계에 맞는 Jira 목표 상태를 판정한다(읽기 전용).

사용: python3 jira_status_check.py <KEY> <dev|staging>
출력: 이슈 유형·현재 상태·목표 상태·지금 가능한 전환과 판정 한 줄.
  MOVE  — 목표가 바로 다음 전환에 있다. 출력된 acli 명령을 실행한다.
  KEEP  — 이슈 유형 워크플로에 목표 상태가 없다(예: 하위 작업 유형에는 스테이징 단계 없음). 현재 상태를 두고 이유를 보고에 쓴다.
  DONE  — 이미 목표 상태이거나 그 뒤 단계다.
  STEP  — 목표가 워크플로에는 있지만 바로 갈 수 없다. 출력된 다음 한 단계 acli 명령만 실행하고 다시 판정한다.
  STOP  — 정순 안에서 목표 쪽으로 갈 전환이 없다. 옮기지 않고 보고한다.

상태 이름은 워크플로마다 다르다. 기본값과 다르면 config.env 또는 환경변수로 바꾼다(쉼표 구분):
  JIRA_STATUS_ORDER   앞으로 가는 정순(스테이징 목표까지)
  JIRA_STATUS_DEV     dev 배포·검증 후 목표 상태
  JIRA_STATUS_STAGING staging 배포·검증 후 목표 상태
  JIRA_STATUS_LATER   ORDER 뒤의 단계(이미 지났으면 되돌리지 않는다)
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skill_config import load_config  # noqa: E402

load_config()


def _list(name, default):
    v = os.environ.get(name)
    return [s.strip() for s in v.split(",") if s.strip()] if v else default


# 앞으로 가는 정순. 목록에 없는 상태는 맨 앞으로 본다.
ORDER = _list("JIRA_STATUS_ORDER", ["백로그", "할 일", "진행 중", "개발 QA 요청", "개발 검수 완료", "스테이징 QA 요청"])
TARGET = {"dev": os.environ.get("JIRA_STATUS_DEV") or "개발 QA 요청",
          "staging": os.environ.get("JIRA_STATUS_STAGING") or "스테이징 QA 요청"}
LATER = _list("JIRA_STATUS_LATER", ["스테이징 검수 완료", "릴리즈 대기", "핫픽스 대기", "운영 배포 완료", "운영 검수(QA)", "운영 검수 완료"])
# 목표 상태보다 뒤 단계(이미 지나갔으면 되돌리지 않는다)
AFTER = {env: set(ORDER[ORDER.index(t) + 1:] if t in ORDER else []) | set(LATER) for env, t in TARGET.items()}


def next_step(current, target, moves):
    """정순에서 현재 뒤·목표 앞(목표 포함)이면서 지금 갈 수 있는 가장 먼 단계. 없으면 None.

    전환 목록의 순서(예: 마지막 항목)로 고르면 운영 단계로 건너뛸 수 있어서, 다음 단계는 이 함수만 정한다.
    """
    if target not in ORDER:
        return None
    start = ORDER.index(current) + 1 if current in ORDER else 0
    allowed = [s for s in ORDER[start:ORDER.index(target) + 1] if s in moves]
    return allowed[-1] if allowed else None


def get(path, cred):
    import jira_inline_image as j  # auth·SITE 재사용(Pillow 필요), 시험은 next_step만 쓴다
    with urllib.request.urlopen(j.request(path, cred)) as r:
        return json.load(r)


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in TARGET:
        sys.exit(__doc__)
    key, env = sys.argv[1], sys.argv[2]
    import jira_inline_image as j
    cred = j.auth()
    issue = get(f"issue/{key}?fields=issuetype,status,parent", cred)["fields"]
    itype, current = issue["issuetype"]["name"], issue["status"]["name"]
    project = key.split("-")[0]
    statuses = next((t["statuses"] for t in get(f"project/{project}/statuses", cred) if t["name"] == itype), [])
    names = {s["name"] for s in statuses}
    moves = [t["to"]["name"] for t in get(f"issue/{key}/transitions", cred)["transitions"]]
    target = TARGET[env]
    parent = issue.get("parent", {}).get("key")
    print(f"{key} 유형={itype} 현재={current} 목표={target} 가능한 전환={' / '.join(moves) or '-'}" + (f" 상위={parent}" if parent else ""))
    if current == target or current in AFTER[env]:
        print(f"DONE 이미 '{current}' — 상태를 유지한다.")
    elif target not in names:
        print(f"KEEP '{itype}' 워크플로에 '{target}'이(가) 없다. '{current}'에 두고, 보고·댓글에 '{itype} 유형이라 {target} 단계 없음'을 쓴다.")
    elif target in moves:
        print(f'MOVE acli jira workitem transition --key {key} --status "{target}" --yes')
    elif nxt := next_step(current, target, moves):
        print(f'STEP acli jira workitem transition --key {key} --status "{nxt}" --yes  # 이 한 단계만 옮기고 다시 판정한다')
    else:
        print(f"STOP '{current}'에서 정순({' → '.join(ORDER)}) 안의 다음 전환이 없다. 옮기지 않고 보고한다.")


if __name__ == "__main__":
    main()
