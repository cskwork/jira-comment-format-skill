# jira-comment-format

An agent skill (Claude Code, Codex, and similar agents) for writing Jira issue descriptions and comments **for planners and QA**, posted through [`acli`](https://developer.atlassian.com/cloud/acli/) as ADF (Atlassian Document Format). The skill instructions (`SKILL.md`) are written in Korean.

## Why

- **Jira comments do not render Markdown.** If you post `.md` through `acli`, readers see literal `#`, `|---|`, and `**`. The skill writes Markdown and converts it to ADF, so headings, tables, panels, inline images, and mentions render properly.
- **Planners can't read developer comments.** When every comment includes queries, flow diagrams, commit hashes, and build numbers, it grows past 1,500 characters and is full of jargon. The skill splits the content:
  - **Jira** (for planners/QA): summary first, a request → result table, a before/after screenshot, a before/after data capture, how to verify, a requester mention, and any decision request.
  - **Developer-note board** (for developers): queries, flow diagrams, API calls, commits, branches, builds, test counts, and rollback SQL. Each Jira ticket gets one note item and each Jira comment gets one note comment.
- **Gates, not guidelines.** `planner_lint.py` rejects developer content before upload. `check_adf.py` re-checks what Jira actually stored. `jira_status_check.py` moves workflow states one step at a time, so a ticket can't jump to a production state.

## Setup

```bash
cp config.example.env config.env      # gitignored; fill in your values
acli jira auth login                  # the scripts reuse acli's Site/Email
# API token (used only for image upload and read-only status checks):
#   export JIRA_API_TOKEN=...   or   put it in ~/.config/jira/token (chmod 600)
pip install pillow                    # for asis_tobe.py and image sizing
# optional: agent-browser on PATH for data_table.py / flow_diagram.py rendering
```

Token values never go on a command line or into this repository. They come from the environment or from a gitignored file. `jira_inline_image.py` passes credentials to `curl` through stdin (`-K -`), so they don't appear in `ps`.

## Scripts (`scripts/`)

| Script | Purpose |
|---|---|
| `md_to_adf.py` | Converts a Markdown subset to ADF and uploads `![alt](file.png)` as inline images. `@[Name](accountId)` becomes a mention node. Runs `planner_lint` first and exits 1 before uploading if the lint fails. |
| `planner_lint.py` | The planner-readability gate. It rejects commit hashes, `#build` numbers, branch names (`fix/…`, `feature/…`), Korean and English dev terms, code identifiers, code blocks and code marks, "comment 12345" references, and bodies over 800 characters. Add project-specific names (repos, services) with `PLANNER_LINT_EXTRA` or `--pattern`. Use `--allow` to whitelist a term. |
| `check_adf.py` | The read-back gate. Reads `acli ... view --json` from stdin and checks node counts, `--min-media`, `--min-mention`, Markdown/JSON leakage, and `planner_lint`. |
| `jira_inline_image.py` | Uploads attachments over REST (acli can't upload) and emits correctly sized `mediaSingle` nodes. |
| `jira_status_check.py` | A read-only transition planner for `dev` or `staging`. Prints `MOVE`, `STEP` (one step only, then re-check), `KEEP`, `DONE`, or `STOP`. Status names are configurable with `JIRA_STATUS_*`. |
| `dev_note.py` | Posts the developer detail to a separate note board through a configurable CLI (`DEV_NOTE_CLI`/`DEV_NOTE_BASE`/`DEV_NOTE_SPACE`). The CLI contract is in the file header. Kira's CLI is one backend that fits it; any wrapper with the same subcommands works. |
| `asis_tobe.py` | Merges before/after screenshots into one image with red and green banners, highlight boxes, masks, and a caption. |
| `data_table.py` | Renders before/after query results as a spreadsheet-style PNG, labelled with the environment. |
| `flow_diagram.py` | Renders a two-row before/after logic flow PNG (for the note board). |
| `skill_config.py` | Loads `config.env` without overriding real environment variables. |

Tests:

```bash
cd scripts && python3 -m unittest test_jira_status_check
```

## Typical flow

```bash
S=scripts
python3 $S/md_to_adf.py --key PROJ-123 comment.md -o comment.adf.json        # lint + convert + upload
acli jira workitem comment create --key PROJ-123 --body-file comment.adf.json
acli jira workitem view PROJ-123 --fields comment --json \
  | python3 $S/check_adf.py --comment <ID> --min-media 1 --min-mention 1     # read-back gate
python3 $S/dev_note.py --key PROJ-123 --jira-comment <ID> --jira-md comment.md dev.md
python3 $S/jira_status_check.py PROJ-123 dev                                  # then run only the printed command
```

## Related

[cskwork/dark-factory](https://github.com/cskwork/dark-factory) has a matching `factory.comment_check` gate that applies the same planner-readability rule to comments posted by its automation.

## License

MIT. See [LICENSE](LICENSE).
