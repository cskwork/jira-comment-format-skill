---
name: jira-comment-format
description: Jira 이슈·하위 티켓 설명과 댓글을 acli로 작성·수정할 때 쓰는 규칙. Jira 글은 기획·QA용만 쓰고(요약 먼저, 요청 → 결과 표, 작동 화면·데이터 전·후 캡처, 확인 방법, 요청자 멘션, 결정 요청), 개발자가 확인할 수 있는 조회 쿼리는 본문 대신 Jira 첨부 .sql 파일로 붙이며, 흐름도·커밋·빌드 같은 나머지 개발자용 상세는 Jira에 남기지 않고 별도 개발자 노트 보드에 Jira 티켓 1건=노트 항목 1건, Jira 댓글 1건=노트 댓글 1건으로 남긴다(dev_note.py). 게시 전(md_to_adf.py)과 되읽기(check_adf.py)에 기획자용 검사(planner_lint.py)를 한다. Jira 생성·정리·서식 개선·댓글 게시·완료 보고·결함 보고·스크린샷/이미지 첨부·배포 단계별 상태 이동 요청에 사용.
---

# jira-comment-format

## 핵심 사실

**Jira 댓글은 마크다운을 렌더링하지 않는다.**

`acli jira workitem comment create --body-file comment.md` 로 마크다운을 올리면
`#`, `|---|`, `**bold**` 가 **문자 그대로 노출**된다. 표는 파이프 기호가 그대로 보인다.

`acli` 가 받는 형식은 두 가지뿐이다.

| 형식 | 입력 | 결과 |
|---|---|---|
| 평문 | `.txt` | 줄바꿈·공백만 유지. 서식 없음 |
| ADF | JSON | 헤딩·표·패널·강조 모두 렌더링 |

마크다운은 **어느 쪽도 아니다.** 평문으로 취급되어 기호가 노출된다.

## 준비

- `acli` 로그인(`acli jira auth login`). 스크립트는 `acli jira auth status`의 Site·Email을 쓴다. `JIRA_SITE`·`JIRA_EMAIL`로 덮어쓸 수 있다.
- 사이트·계정·토큰 파일 경로·사내 URL·노트 보드 설정은 `config.env`(git 무시)에 둔다. 처음이면 `cp config.example.env config.env` 후 값을 채운다. 스크립트는 환경변수가 없을 때 이 파일 값을 쓴다. 아래 명령의 `$JIRA_*`·`$DEV_URL` 등도 `set -a; . <스킬 디렉터리>/config.env; set +a`로 불러 쓴다.
- 같은 계정의 API 토큰: `JIRA_API_TOKEN` 환경변수 또는 `JIRA_TOKEN_FILE`(기본 `~/.config/jira/token`, 권한 600). acli에 업로드 기능이 없어서 이미지 업로드와 상태 판정(읽기)에만 쓴다. 토큰 값을 명령줄·config.example.env·저장소에 쓰지 않는다.
- `python3` + Pillow(`pip install pillow`). 한글 폰트는 macOS·Linux(Noto CJK·나눔)·Windows(맑은 고딕) 순으로 찾고, 없으면 `ASIS_TOBE_FONT=<경로>`.
- 흐름도·엑셀 표 렌더링과 캡처: `agent-browser`(또는 같은 일을 하는 브라우저 도구).
- `acli confluence`는 jira와 **별도 인증**이다. 필요하면 같은 API 토큰으로 로그인한다(토큰은 파일에서 stdin으로 넘긴다).

  ```bash
  acli confluence auth login --site "$JIRA_SITE" --email "$JIRA_EMAIL" --token < "$JIRA_TOKEN_FILE"
  ```

- 개발자 노트 보드: `DEV_NOTE_CLI`·`DEV_NOTE_BASE`·`DEV_NOTE_SPACE`(·`DEV_NOTE_WORKSPACE`)를 `config.env`에 둔다. CLI가 지켜야 할 하위 명령은 `scripts/dev_note.py` 머리말에 있다(Kira CLI가 한 예). 로그인은 사람이 그 CLI로 한다.
- `acli auth status`는 전역 인증이라 실패할 수 있다. 제품별 `acli jira auth status`, `acli confluence auth status`로 확인한다.

## 기본 서식 — Jira는 기획·QA용, 개발자용은 노트 보드

Jira 글(댓글·이슈 설명)은 기획·QA가 읽는다. **개발자용 내용은 Jira에 아예 쓰지 않고 개발자 노트 보드(`DEV_NOTE_SPACE`)에 남긴다.** 기획 티켓 댓글마다 개발자용 절(데이터·쿼리·흐름도)과 커밋·빌드를 넣으면 글이 1,500자를 넘고 개발 용어가 수십 개 섞여 기획자가 "무엇을 작업했는지" 읽지 못한다. 그래서 두 곳으로 나눈다.

| 어디에 | 무엇을 | 도구 |
|---|---|---|
| Jira | 요청하신 것 → 지금 상태, `요청 항목 \| 수정 전 \| 수정 후` 표, 작동 화면 전·후 캡처, 데이터 전·후 캡처(이미지 + 쉬운 말 한 줄), 확인 방법(환경·계정·메뉴), 알아 둘 점, 결정 요청, **개발자 확인용 쿼리 첨부 파일(`.sql` 파일 카드)** | `asis_tobe.py`·`data_table.py` → `md_to_adf.py`(게시 전 기획자용 검사·첨부 업로드) → acli → `check_adf.py` |
| 노트 보드 | Jira 게시본 사본 + 쿼리 원문(같은 `.sql` 첨부), 논리 흐름도, API·명령, 커밋·브랜치·빌드, 시험 건수, 운영 확인·실행 SQL·롤백, 범위 밖 관찰·권고 | `flow_diagram.py` → `dev_note.py` |

노트 구조: Jira 티켓 1건 = 노트 항목 1건(`[Jira] <KEY> <요약>`, 라벨 `jira-<KEY>`, 상태 Done), Jira 댓글 1건 = 그 항목의 노트 댓글 1건(첫 줄 `Jira <KEY> 댓글 <ID>`, `## Jira 게시본` + `## 개발자용 상세`). 같은 Jira 댓글로 다시 실행하면 그 노트 댓글을 고치고, 같은 이름의 첨부는 다시 올리지 않는다. 노트에는 Jira 링크를 넣지 않는다(키·댓글 번호만 글자로, `dev_note.py`가 자동으로 뺀다). 노트 쓰기는 `dev_note.py`로만 한다.

### Jira 기획자용 틀

1. **첫 줄**: 요청자 멘션 + 요청하신 것 → 지금 상태(어느 환경까지) + 기획자가 할 일 하나.
2. **굵은 결론 1문장**: 화면에서 무엇이 어떻게 달라졌는지.
3. **표 5행 이하**: 왼쪽 열은 기획자가 쓴 문장이나 TC 번호를 그대로 쓴다(`요청 항목 -> 결과`). 수정 전·후는 화면 기준.
4. **작동 화면 전·후 1장**(아래 캡처 규칙), 필요하면 **데이터 전·후 캡처 1장**. 이미지 바로 위에 무엇이 달라졌는지 쉬운 말 한 줄. 화면이 없으면 이유 한 줄.
5. **확인 방법**: 환경·계정·메뉴 경로.
6. **알아 둘 점**(있을 때만, 2개 이하)과 **결정 요청**(`> [!NOTE]`).

댓글 유형별로 필요한 칸만 쓴다. 해당 없는 칸은 "해당 없음"이라고 적지 않고 뺀다.

| 유형 | 쓰는 칸 |
|---|---|
| 수정·검증 완료 | 1~6 |
| 질문 답변 | 1, 3(질문 → 답), 결정 요청 |
| 배포 알림(스테이징 반영 등) | 1, 2, 그 환경 E2E 작동 화면 캡처(4, 수정 후 필수·전 화면은 가능할 때), 확인 방법. 빌드 번호·저장소 표 없이. 캡처 없는 배포 알림은 기획자가 확인할 수 없으므로, E2E를 못 했으면 게시하지 말고 막힌 이유와 함께 `BLOCKED`로 보고한다 |
| 계정 전달 | 1, 계정 구성 한 줄, 전달 방법 |
| 결정 요청 | 1, 3(지금 동작 → 바꾸면), 선택지 번호 |

쓰지 않는 것 — 게시 전 `md_to_adf.py`와 되읽기 `check_adf.py`가 `planner_lint.py`로 막는다:

- 커밋 해시, `#빌드`, 브랜치 이름(`fix/…`·`feature/…` 등), API·SQL·curl·쿼리·테이블 같은 개발 용어(한국어·영어), 코드·열 이름, 코드 블록·코드 서식.
- 저장소·서비스 이름처럼 프로젝트마다 다른 이름은 `PLANNER_LINT_EXTRA`(config.env) 또는 `--pattern 정규식`으로 더한다.
- `댓글 12345` 같은 번호 참조. Jira 화면에는 댓글 번호가 보이지 않는다. `[앞서 드린 확인 요청](https://<your-site>/browse/<KEY>?focusedCommentId=<ID>)` 링크와 한 줄 요약으로 쓴다.
- 쿼리를 본문·코드 블록에 넣는 것. 개발자가 확인할 수 있는 쿼리는 아래 "개발자 확인용 쿼리 첨부"대로 파일로 붙인다.
- 800자 초과(공백·멘션·이미지 제외). 이슈 설명은 `--max-chars 0`.
- 기획자도 쓰는 말이라고 확인한 용어만 `--allow 용어`로 연다.

### 캡처·조회 환경 명시

**어느 환경(`로컬` / `개발(dev)` / `스테이징(staging)` / `운영(prod)`)에서 화면을 캡처했거나 데이터를 조회했는지** Jira는 절 제목·이미지 띠·캡션에, 노트는 절 제목·`spec.json`의 `"env"`에 적는다. Jira에서는 `개발계` / `스테이징`처럼 기획자가 쓰는 말로 쓴다.

캡처 규칙:

- **작동 화면(Jira)**: 수정 전·후를 **한 장**으로 합친다(`asis_tobe.py`). 위 빨간 띠 `수정 전 (개발계) — 무엇이 문제인지`, 아래 초록 띠 `수정 후 (개발계) — 무엇이 바뀌었는지`. 바뀐 곳에 테두리(전=빨강, 후=초록)를 치고, 맨 아래 회색 캡션에 **환경·화면 경로·계정·일자**를 적는다. 운영 화면은 캡처하지 않는다. 실제 사용자 이름은 회색으로 가린다(테스트 계정명은 유지 가능). 화면이 없는 순수 배치·백엔드 티켓은 Jira에 결과 문장만 쓴다.
- **데이터 변화(Jira 이미지 + 노트 쿼리)**: 실데이터 조회 결과를 엑셀 형태로 캡처해(`data_table.py`) Jira에 넣고, 바로 위에 쉬운 말 한 줄(예: "글 551건이 쓴 사람에게 연결, 빠진 글 0건")을 쓴다. `spec.json`의 `"env"`에 조회 환경(`개발(dev) DB · <DB 호스트>`, `스테이징(staging) DB`, `운영(prod) DB 조회 결과`)을 넣고, `수정 전 (As-Is)`(빨강)·`수정 후 (To-Be)`(초록) 시트의 바뀐 셀에 `hit: true`를 준다. 쿼리 원문은 이미지·Jira 본문에 넣지 않고, 같은 Jira 댓글에 `.sql` 첨부 파일로 붙인다(아래 절). 노트에는 같은 파일을 첨부하고 코드 블록 사본도 둔다. 사용자 ID는 앞 8자만 노출한다.
- **논리 흐름(노트)**: 수정 전(원인·오류 시나리오)과 수정 후(해결 흐름)를 두 줄로 대조한다(`flow_diagram.py`). 동작이 갈리는 단계에 `hit: true`.
- 파일명은 `<키번호>_<항목>_<요약>.png`처럼 첨부 목록에서도 무엇인지 알 수 있게 짓는다.

실화면 캡처는 프로젝트가 이미 쓰는 E2E 도구(Playwright 시나리오 등)로 뜬다. 진입·이름 가림·시간 제한이 들어 있는 기존 시나리오를 복사해 단계만 바꾸고, 진입 스크립트를 새로 쓰지 않는다. 위임할 때도 프롬프트에 그 경로를 준다. 캡처 결과 PNG가 `asis_tobe.py` 입력이다.

### 배포·검증 완료 댓글 — 환경별 같은 대상 전·후

**전·후는 항상 같은 환경·같은 대상(그룹·계정)이다.** dev 캡처와 staging 캡처를 나란히 둔 것은 전·후 비교가 아니다.

- Jira: 결론 1~2문장(**어느 환경까지 확인했고** 다음에 기획자가 볼 곳) → `경우 | 수정 전 | 수정 후` 표 → 환경별 절(`개발계`, `스테이징`)마다 같은 대상 전·후 합성 1장 + 핵심 변화 1~2줄(데이터 전·후 캡처가 있으면 함께) → 확인 방법(환경·진입 경로·계정·화면).
- 노트(같은 Jira 댓글의 짝): 확인 쿼리, 논리 흐름도, 운영 확인 순서(배포 전/후 쿼리 판정), 개발 근거(브랜치·커밋 → 환경별 빌드 번호), 시험 건수·범위.

수정 전 화면·데이터 만들기:

- 수정이 이미 그 환경에 배포됐으면 시험 계정을 새로 만들고, 수정 전(운영 기준 브랜치)과 수정 후(티켓 브랜치) 코드의 SQL·서버를 **시험 계정·시험 그룹 범위로만** 실행해 전·후 화면과 실데이터 행을 뽑는다. 실제 배치 잡은 돌리지 않는다. 쓰기 직전마다 접속한 DB 호스트를 확인한다.
- 수정이 바꾸는 상황이 데이터에 없으면 그 상황을 만든 뒤 찍는다. 외부 장애로 실제 행동을 못 하면 그 장애를 타지 않는 경로로 같은 시나리오를 만들고, 그것도 안 되면 사용자 승인 후 SQL로 넣고 그 사실을 밝힌다.
- 화면 숫자마다 출처(배치 결과 vs API)를 코드로 확인해, 수정 전 캡처가 어느 부분까지 수정 전 상태인지 적는다.

확인 쿼리(Jira `.sql` 첨부 + 노트 사본): 조회 전용 SELECT(판정용 집계 1문장 + 필요하면 상세 1문장), 입력은 맨 위 CTE 한 곳(기본값=제보 사례), `수정전_계산 | 수정후_계산 | 화면_저장값 | 판정` 열, 사용자 ID는 앞 8자만(`LIKE 'abcd1234%'`처럼 써서 원문에도 전체 ID를 넣지 않는다), 맨 위 `--` 주석 1~2줄에 무엇을 보는지와 판정 기준(예: `수정 후 0행`). dev/staging에서 먼저 실행해 결과는 `data_table.py` 캡처로 Jira 본문에 넣는다.

```bash
S=<이 스킬 디렉터리>/scripts      # 예: ~/.agents/skills/jira-comment-format/scripts
# Jira: 작동 화면 전·후 한 장 (라벨과 캡션에 환경 명시)
python3 $S/asis_tobe.py before.png after.png -o 101_1_화면_임시저장_전후.png \
  --before-label "수정 전 (개발계) — 임시 저장인데 '배포일 + 날짜'가 보임" \
  --after-label  "수정 후 (개발계) — 임시 저장은 '임시 저장'으로 표시" \
  --mark-before 16,320,322,36 --mark-after 16,320,214,36 --mask-before 610,8,170,32 \
  --caption "환경: 개발계 · 메뉴 > 목록 화면 · 계정 <테스트 계정> · YYYY-MM-DD"
# Jira: 데이터 전·후 엑셀 캡처 (spec.json의 env에 환경·DB 호스트, 쿼리 원문은 노트)
python3 $S/data_table.py data_spec.json -o 101_2_데이터_전후.png
# Jira 첨부: 개발자 확인용 쿼리 (조회 전용, 맨 위 -- 주석에 무엇을 보는지·판정 기준)
#   101_4_확인.sql
# 노트: 논리 흐름도
python3 $S/flow_diagram.py flow_spec.json -o 101_3_논리흐름_전후.png
```

넓은 화면은 위아래(`--layout stack`, 기본), 좁은 화면은 `--layout side`.

### 개발자 확인용 쿼리 첨부

개발자가 직접 돌려 확인할 수 있는 쿼리는 Jira 본문에 넣지 않고 **같은 Jira 댓글에 첨부 파일로** 붙인다. 기획자는 본문만 읽고, 개발자는 파일을 내려받아 바로 실행한다.

- 대상: 조회 전용 확인 쿼리(위 "확인 쿼리" 규칙). 데이터 보정·쓰기·롤백 SQL과 운영 실행 순서는 Jira에 붙이지 않고 노트에만 둔다.
- 파일: `<키번호>_<항목>_확인.sql`. 맨 위 `--` 주석 1~2줄에 무엇을 보는지·판정 기준·실행한 환경(`개발(dev) DB · <DB 호스트>`)을 쓴다. 설명 줄은 모두 `-- `로 시작해 파일을 그대로 실행할 수 있게 한다. 사용자 ID는 앞 8자만.
- 본문: 맨 끝(확인 방법 다음)에 `개발자 확인용 자료(첨부)` 한 줄과 `![개발자 확인용](101_4_확인.sql)`. `md_to_adf.py`가 이미지가 아닌 파일을 업로드해 파일 카드(`mediaGroup`)로 넣는다. 파일 이름은 노드 속성이라 기획자용 검사에 걸리지 않는다. 기존 첨부는 `![개발자 확인용](attachment:<ID>)`.
- 되읽기: `check_adf.py --min-file 1`(파일 카드 수). `--min-media`는 인라인 이미지만 센다.
- 노트: 같은 `.sql`을 `dev_note.py --attach`로 붙이고 `### 확인 명령·쿼리`에 코드 블록 사본을 둔다.

### 게시 — 마크다운으로 쓰고 한 번에 ADF로

Jira는 마크다운을 렌더링하지 않는다. 글은 마크다운으로 쓰고 `md_to_adf.py`로 ADF를 만든다. 이미지 줄(`![설명](파일.png)`)은 업로드되어 그 자리에 인라인으로 들어간다. 이미 올린 첨부는 `![설명](attachment:43475)`.

**특정 사용자에게 요청·답할 때는 멘션한다.** 호칭 앞에 `@[이름](<accountId>) 님,`처럼 쓰면 `mention` 노드가 되어 알림이 간다. accountId는 그 사람이 reporter·assignee·댓글 작성자인 이슈의 `view --json`에서 얻는다(`fields.reporter.accountId`, `comment.comments[].author.accountId`). 이름만 평문으로 쓰면 알림이 가지 않는다. 되읽기에서 `check_adf.py --min-mention 1`로 노드 저장을 확인한다(텍스트 렌더링에는 안 보여도 ADF에 남는다).

```bash
# 0-a) 게시 전 중복 확인: 같은 이슈의 내 최근 댓글 5건(id·작성 시각·첫 줄)을 읽는다.
#      같은 사건을 다룬 내 댓글이 이미 있으면(동시 세션이 먼저 올린 경우 포함) 새로 달지 않고 그 댓글을 갱신한다.
acli jira workitem view PROJ-101 --fields comment --json 2>/dev/null \
  | python3 -c "import json,os,sys,re;me=os.environ['JIRA_MY_NAME'];c=[c for c in json.load(sys.stdin)['fields']['comment']['comments'] if c['author']['displayName'].startswith(me)][-5:];[print(c['id'],c['created'][:16],' '.join(re.findall(r'\"text\": \"([^\"]*)\"',json.dumps(c['body'],ensure_ascii=False)))[:120]) for c in c]"
# 0) 기존 댓글을 고칠 때만: 원본 백업 (git 무시 경로)
mkdir -p ~/.agents/backups/jira
acli jira workitem view PROJ-101 --fields comment --json 2>/dev/null \
  | python3 -c "import json,sys;c=[c for c in json.load(sys.stdin)['fields']['comment']['comments'] if c['id']=='10101'][0];print(json.dumps(c['body'],ensure_ascii=False))" \
  > ~/.agents/backups/jira/PROJ-101_10101.adf.json
# 1) 기획자용 검사 + 변환 + 이미지 업로드 (개발 용어·코드·800자 초과면 업로드 전에 exit 1)
python3 $S/md_to_adf.py --key PROJ-101 comment.md -o comment.adf.json
# 2) 게시 (새 댓글 / 기존 댓글 갱신 / 이슈 설명)
acli jira workitem comment create --key PROJ-101 --body-file comment.adf.json
acli jira workitem comment update --key PROJ-101 --id 10101 --body-adf comment.adf.json
acli jira workitem edit --key PROJ-101 --description-file comment.adf.json --yes
# 3) 되읽기: 노드·이미지 수·마크다운 누출·기획자용 검사 (걸리면 exit 1)
acli jira workitem view PROJ-101 --fields comment --json 2>/dev/null | python3 $S/check_adf.py --comment 10101 --min-media 3   # 사람에게 요청·답이면 --min-mention 1, 확인 쿼리 첨부면 --min-file 1 추가
# 4) 개발자용 상세는 노트 보드에 (Jira 댓글 1건 = 노트 댓글 1건, 같은 댓글로 다시 실행하면 갱신)
python3 $S/dev_note.py --key PROJ-101 --jira-comment 10101 --jira-md comment.md dev.md --attach 101_3_논리흐름_전후.png 101_4_확인.sql
```

`comment.md` 예시 (Jira 기획자용 틀):

````markdown
@[이름](<accountId>) 님, 문의하신 '담당자를 바꿔도 이전 담당자 화면에 항목이 남는 문제'를 고쳐 개발계에 반영했습니다.
**이제 담당자를 바꾸면 이전 담당자 화면에서 그 항목은 미배정으로 보이고, 이전 담당자에게 알림도 가지 않습니다.**

| 문의하신 내용 (이전 담당자 화면) | 수정 전 | 수정 후 (개발계) |
|---|---|---|
| 홈 화면 배정 목록 | 배정으로 남음 | 미배정 |
| 알림 보내기 (개별 · 전체) | 알림이 감 | 알림이 가지 않음 |
| 프로필 표시 | 담당자 구분 없이 공통 | 그대로 — 아래 결정 필요 |

![같은 항목을 이전·현재 담당자 화면에서 나란히 (개발계)](101_1_화면_전후.png)
담당자별 데이터(개발계): 담당자를 바꾼 직후 이전 담당자 쪽에서는 미배정, 알림 0건으로 바뀝니다.
![담당자별 데이터 (개발계)](101_2_데이터_전후.png)

### 확인 방법 (개발계)
- 테스트 계정 <시험 계정>으로 들어가 상단에서 담당자를 바꿉니다.
- 이전 담당자 홈 > 배정 목록에서 그 항목이 미배정인지 봅니다.

> [!NOTE] 결정 요청: 프로필 표시를 담당자별로 나눌지 정해 주세요. 선택지는 [앞서 드린 확인 요청](https://<your-site>/browse/PROJ-101?focusedCommentId=10100)에 있습니다.

개발자 확인용 자료(첨부):
![개발자 확인용](101_4_확인.sql)
````

`dev.md` 예시 (노트 — 같은 Jira 댓글의 짝):

````markdown
### 시험·범위
- 개발(dev) 배포본 8건 통과. 시험 그룹 <그룹 코드>, 사용자 앞 8자 <id8>, YYYY-MM-DD HH:MM~.
- 이번 비교에 없음: 수정 전 화면, '전체 알림' 버튼(다른 사용자에게 알림이 가서 API로 대신 확인).

### 확인 명령·쿼리
```bash
curl -s -X POST "$H/api/assignment/current" ...   # 이전 담당자면 status=null
```

### 개발 근거
fix/PROJ-101 — <서비스> <커밋> → dev 머지 <커밋> (<빌드 잡> #480 SUCCESS)
````

이미지 업로드만 개별로 할 때는 `jira_inline_image.py --key <KEY> 파일...` (기존 첨부는 `--attachment-id ID...`)가 mediaSingle 노드 JSON을 출력한다.

### 인라인 이미지 함정 (실측)

- 원리: 첨부 `GET /rest/api/3/attachment/content/{id}`가 303으로 Atlassian media 서비스의 `/file/<mediaId>/binary`를 가리킨다. 그 UUID가 `media.attrs.id`다. `collection`은 `""`.
- **media에 원본 `width`/`height`(px)가 꼭 있어야 한다.** 없으면 Jira가 760×608(4:5) 고정 칸을 잡아 낮은 이미지는 위아래 흰 공백, 긴 이미지는 폭이 줄어든다. 스크립트가 자동으로 넣는다.
- 이미지 안에 바로 위 제목과 같은 문구를 다시 넣지 않는다.
- Jira 구조상 인라인 이미지도 이슈의 첨부 목록에 함께 표시된다. 본문에서 보이는 것이 목적이므로 그대로 둔다. 교체해서 안 쓰게 된 내 업로드는 `acli jira workitem attachment delete --id <ID>`로 지운다.

```json
{"type":"mediaSingle","attrs":{"layout":"align-start","width":760,"widthType":"pixel"},
 "content":[{"type":"media","attrs":{"type":"file","id":"<mediaId>","collection":"","alt":"파일명.png","width":1100,"height":361}}]}
```

### 텍스트 구성

개발 작업 티켓의 권장 구성. 짧은 티켓은 필요한 항목만 쓴다.

1. 문제와 변경 목적: 핵심을 짧은 문단으로 먼저 설명.
2. 상위 티켓·담당/서비스·협의 상대·선행 작업: 간결한 표.
3. 작업 내용 / 완료 기준 / 검증 방법: 각각 실제 heading + bulletList. 문단 앞에 `-`만 붙이지 않는다.
4. 코드 근거: Jira에 쓰지 않고 `dev_note.py --jira-comment description`으로 노트에 남긴다. 실제 티켓 번호는 link mark.
5. 확인 수준·미확정 정책: 필요할 때만 note panel. 정적 분석과 API/DB 실행 증거를 구분.

- 부모 요약은 하위 티켓 링크/작업 표 → 진행 순서 → 확정 정책 → 협의 항목 순으로 정리.
- 임시 번호보다 실제 Jira 키와 링크를 쓴다.
- 가독성 수정은 기존 본문/댓글을 갱신한다. 내용·범위·담당자·상태·의존관계는 임의 변경하지 않는다. 남의 댓글은 고치지 않는다.
- 기존 댓글을 고치기 전에 원본 ADF를 `~/.agents/backups/jira/<KEY>_<ID>.adf.json`(git 무시 경로)에 저장해 되돌릴 수 있게 한다.
- Jira 글은 개발 티켓이어도 쉬운 말로 쓴다. 구현에 필요한 코드 근거는 노트에 둔다.
- 경로/코드 자동 인식 시 ASCII 문자 범위를 사용하여 한국어 조사까지 code mark에 넣지 않는다.

## 명령

```bash
# 이슈 설명: 실제 제목·표·목록이 있는 ADF 파일
acli jira workitem edit --key PROJ-1234 --description-file description.adf.json --yes

# ADF 댓글 수정: --body-adf 사용
acli jira workitem comment update --key PROJ-1234 --id 48770 --body-adf comment.adf.json

# 짧은 평문 댓글 게시
acli jira workitem comment create --key PROJ-1234 --body-file comment.txt

# 수정 (같은 댓글 갱신 — 새로 달지 않는다)
acli jira workitem comment update --key PROJ-1234 --id 48770 --body-file comment.txt

# 목록 (ID 확인)
acli jira workitem comment list --key PROJ-1234

# 삭제
acli jira workitem comment delete --key PROJ-1234 --id 48771
```

`--key` 는 `create`/`update`/`delete` 모두에 필요하다. `comment` 상위 명령에는 `--key` 가 없다.
서브커맨드(`create` 등)를 반드시 붙인다.

### 새 티켓을 만들기 전 — 같은 증상 티켓 검색

결함·요청 티켓을 새로 만들기 전에 담당자와 관계없이 같은 화면·증상의 최근 티켓을 찾는다. 검색을 건너뛰면 같은 결함이 두 티켓으로 나뉘어 두 담당자가 따로 고치게 된다.

```bash
acli jira workitem search --jql 'project = PROJ AND updated >= -14d AND text ~ "<증상 핵심어>"' --fields key,summary,assignee,status --limit 20
```

핵심어는 화면 이름·API 경로·오류 문구로 2~3번 바꿔 검색한다. 로컬 작업 메모(이슈 폴더 등)가 있으면 같은 핵심어로 함께 찾는다. 후보가 있으면 새로 만들지 말고, 그 티켓에 댓글을 달지, 연결 이슈로 만들지 사용자에게 먼저 묻는다. 검색한 JQL과 결과 수를 보고에 남긴다.

## ADF 스니펫 (실제 게시 성공 확인)

```json
{"version":1,"type":"doc","content":[
 {"type":"heading","attrs":{"level":3},"content":[{"type":"text","text":"제목"}]},
 {"type":"paragraph","content":[
   {"type":"text","text":"굵게","marks":[{"type":"strong"}]},
   {"type":"text","text":" 그리고 "},
   {"type":"text","text":"코드","marks":[{"type":"code"}]}
 ]},
 {"type":"panel","attrs":{"panelType":"warning"},"content":[
   {"type":"paragraph","content":[{"type":"text","text":"경고 패널"}]}
 ]},
 {"type":"table","attrs":{"isNumberColumnEnabled":false,"layout":"default"},"content":[
  {"type":"tableRow","content":[
    {"type":"tableHeader","content":[{"type":"paragraph","content":[{"type":"text","text":"열1"}]}]},
    {"type":"tableHeader","content":[{"type":"paragraph","content":[{"type":"text","text":"열2"}]}]}
  ]},
  {"type":"tableRow","content":[
    {"type":"tableCell","content":[{"type":"paragraph","content":[{"type":"text","text":"값1"}]}]},
    {"type":"tableCell","content":[{"type":"paragraph","content":[{"type":"text","text":"값2"}]}]}
  ]}
 ]}
]}
```

`panelType`: `info` · `note` · `warning` · `success` · `error`

## 게시 후 반드시 확인한다

```bash
acli jira workitem view PROJ-1234 --fields 'description,comment,assignee,parent,issuelinks' --json
```

- 서버에 저장된 description/해당 comment.body의 heading, table, bulletList, code/link marks와 본문을 확인한다. 성공 메시지만으로 끝내지 않는다. `scripts/check_adf.py`로 노드 수·`media` 수를 확인한다.
- 이미지를 넣었으면 브라우저로 해당 댓글을 열어 이미지가 본문 안에 렌더링되는지 한 번 본다.
- JSON 텍스트나 마크다운 기호가 본문으로 들어가지 않았는지 검사한다.
- ADF 비교 시 Jira가 붙인 localId와 빈 attrs는 정규화해도 되지만, 본문·링크·서식 노드는 보존한다.
- 서식만 수정했으면 담당자·상위 티켓·의존관계·제목이 유지됐는지 확인한다.
- API 조회는 저장된 서식 구조의 증거다. 실제 화면 렌더링을 보지 않았다면 육안 검증으로 표현하지 않는다.

## 상태 이동

배포를 확인하면 같은 작업 안에서 티켓의 Jira 상태를 **실제 배포·검증 단계**에 맞춘다. 상태 이름은 워크플로마다 다르므로 `JIRA_STATUS_*`(config.env)로 맞춘다. 기본값:

| 확인한 단계 | 목표 상태 |
|---|---|
| dev 배포·검증 | `개발 QA 요청` |
| staging 배포·검증 | `스테이징 QA 요청` |

- dev 반영을 운영 완료로 처리하지 않는다(운영 단계 상태로 옮기지 않는다).
- 워크플로는 단계를 건너뛸 수 없고 이슈 유형마다 다르다. 전환 전에 `python3 scripts/jira_status_check.py <KEY> <dev|staging>`로 판정한다(읽기 전용). `MOVE`면 출력된 명령을 실행하고, `STEP`이면 출력된 한 단계 명령만 실행하고 다시 판정한다. 다음 상태를 전환 목록에서 직접 고르거나 반복문으로 돌리지 않는다 — 전환 목록의 마지막 항목은 운영 단계일 수 있어서 한 번에 운영 상태로 잘못 옮겨진다. `STOP`이면 옮기지 않고 보고한다. 시험: `cd scripts && python3 -m unittest test_jira_status_check`.
- `하위 작업` 같은 유형에는 스테이징 단계가 없을 수 있다. 판정이 `KEEP`이면 현재 상태에 두고, 댓글에 "하위 작업 유형이라 스테이징 단계 없음, 현재 `<상태>` 유지"를 한 줄로 쓴다.
- **사용자에게 하는 최종 보고의 첫 줄은 Jira 상태 줄이다**: `Jira: <KEY> <전 상태> → <후 상태>` 또는 `Jira: <KEY> <상태> 유지 | <사유>`(예: `Jira: PROJ-123 개발 검수 완료 유지 | 하위 작업 유형이라 스테이징 단계 없음`). 보고 끝에 묻힌 상태 사유는 사용자가 놓친다. 상태 줄이 없는 보고는 미완료다.
- 쓰기는 `acli`만 쓴다. 성공 출력만 믿지 말고 되읽어 상태와 댓글을 확인한다.

```bash
acli jira workitem transition --key <KEY> --status "<상태>" --yes   # 허용된 전환을 한 단계씩
acli jira workitem view <KEY> --fields comment,status --json         # 되읽기
```

## 작성 원칙

- Jira 독자는 기획·QA다. 코드명 대신 화면 이름과 결과로 쓰고, 코드 근거는 노트에 둔다.
- 육하원칙으로 쓴다. `[누가] [언제] [어디서] [무엇을] [왜] [어떻게]`
- **읽는 사람이 오해할 지점을 맨 위에 둔다.** 예: "배포했는데 왜 그대로 보이나" → 첫 문단에 이유를 설명
- 길이보다 순서가 중요하다. 판단이 필요한 요청은 맨 아래 별도 문단으로 분리한다.
- 잘못 안내했으면 첫 줄에서 짧게 인정하고 넘어간다. 사과를 반복하지 않는다.

### 길이 상한 (기획·QA 대상 댓글 · 800자는 `planner_lint.py`가 검사)

이점 나열, 긴 검증 범위, 시험 방법 단락이 이어지면 기획자는 "너무 길다"며 읽지 않는다. 화면 한 장 안에 읽히게 쓴다.

- 결론은 굵은 1문장이고, 숫자 1개를 같이 쓴다. 요약 표는 5행 이하로 한다.
- 텍스트 절은 2~3개로 하고, 절마다 bullet을 3개 이하로 둔다. bullet 하나는 1~2문장이다.
- 검증 범위는 `확인함` / `이번 비교에 없음` / `남은 확인` 3줄로 쓴다. 수치·조건·미확인 경고는 줄이지 않는다.
- 이미지 아래 설명은 0~1줄이다. 이미지가 이미 말하는 내용은 다시 쓰지 않는다.
- 시험 방법·커밋·빌드는 Jira에 쓰지 않고 노트에 둔다.
- 근거가 약한 이유를 길게 따지는 내용(적대적 검토 과정 등)은 개발자 대상 내용이다. 기획 댓글에는 그 결론(무엇이 빠졌는지)만 남긴다.
- 게시 전에 같은 사실이 두 번 나오는지 확인하고, 나오면 하나를 지운다.

## 규칙

- Jira **쓰기는 `acli` 로만** 한다. 예외는 acli에 없는 이미지 업로드뿐이며 `md_to_adf.py`·`jira_inline_image.py`(acli 계정과 같은 계정의 토큰 REST)로 한다. 다른 Jira 연동(MCP 등)은 읽기 전용으로 쓴다.
- 개발자용 내용은 Jira에 쓰지 않는다. 노트 쓰기는 `dev_note.py`로만 하고, 노트에는 Jira 링크를 넣지 않는다.
- 같은 내용을 고칠 때는 `update` 로 기존 댓글을 갱신한다. 새 댓글을 쌓지 않는다.
- 시험용 댓글을 올렸으면 `delete` 로 반드시 지운다.
