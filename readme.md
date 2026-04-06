# jira-cli

[![PyPI version](https://badge.fury.io/py/jira-cli-top-moumoute.svg)](https://pypi.org/project/jira-cli-top-moumoute/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI](https://github.com/aubustou/jira-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/aubustou/jira-cli/actions/workflows/ci.yml)

A command-line tool for querying and exporting JIRA issues. Wraps `atlassian-python-api` with a chainable interface — browse issues, filter by project/sprint/status, and export to CSV without writing custom scripts.

---

## Installation

### From PyPI

```bash
pip install jira-cli-top-moumoute
```

### From source

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

---

## Configuration

Create `~/.config/jira-cli/config.json` before first use:

```json
{
  "jira_url": "https://jira.example.com",
  "confluence_url": "https://confluence.example.com",
  "user": "your-username",
  "password": "your-password-or-token"
}
```

---

## Usage

Commands can be **chained** together — the output of one flows into the next, Unix-pipe style.

```
jira-cli [COMMAND1 [ARGS]...] [COMMAND2 [ARGS]...]...
```

### `read` — query issues

| Option | Type | Default | Description |
|---|---|---|---|
| `--issue-number` | str | — | Fetch a single issue by key (e.g. `FOO-123`) |
| `--project` | str | — | Project key to query |
| `--sprint` | str | — | Sprint name substring (requires `--project`) |
| `--limit` | int | 10 | Max issues returned (JQL queries only) |
| `--status` | str | — | Post-filter by status (case-insensitive) |
| `--resolution` | str | — | Post-filter by resolution (case-insensitive) |
| `--reduced` | flag | false | Print only key + summary |
| `--comment-summary` | flag | false | Include the `#Summary` comment section |

### `create_csv` — export to CSV

| Option | Type | Default | Description |
|---|---|---|---|
| `--filename` | path | `output.csv` | Output file path |

Writes a semicolon-delimited CSV with columns: `ticket;title;summary`.
`summary` is extracted from the `#Summary` section of issue comments.

### `create` — create issues

Create a new JIRA issue, either by CLI arguments or by providing a JSON payload.

| Option | Type | Default | Description |
|---|---|---|---|
| `--project` | str | — | Project key (e.g. `FOO`) |
| `--summary` | str | — | Issue summary/title |
| `--description` | str | — | Issue description body |
| `--issuetype` | str | `Task` | Issue type name |
| `--priority` | str | — | Priority name |
| `--assignee` | str | — | Assignee username |
| `--labels` | str | — | Labels (repeatable) |
| `--components` | str | — | Component names (repeatable) |
| `--json` | str | — | Inline JSON with issue fields |
| `--json-file` | path | — | Path to JSON file with issue fields |
| `--extra-fields` | str | — | Additional fields as JSON string |
| `--base64` | flag | false | Decode description from base64 |

**Two input modes** (mutually exclusive):
- **Arguments:** `--project` and `--summary` are required; other options are optional.
- **JSON:** provide `--json` (inline) or `--json-file` (path). Shorthand forms like `"project": "FOO"` are auto-normalized to `{"key": "FOO"}`.

The `--base64` flag works in both modes — it decodes the `description` field from base64 before sending to JIRA. Useful for pushing formatted content (e.g. HTML) without shell escaping issues.

### Examples

```bash
# Fetch a single issue
jira-cli read --issue-number=FOO-123

# Most recent 20 issues in a project
jira-cli read --project=FOO --limit=20

# All issues in a sprint, filter by status, compact output
jira-cli read --project=FOO --sprint="Sprint 42" --status=Open --reduced

# Export open issues to CSV
jira-cli read --project=FOO --status=Open create_csv --filename=open_issues.csv

# Chain two reads into one CSV
jira-cli read --project=FOO --sprint="Sprint 42" read --project=BAR --limit=5 create_csv

# Create by arguments
jira-cli create --project=FOO --summary="Fix login bug" --issuetype=Bug --priority=High

# Create by inline JSON
jira-cli create --json='{"project":"FOO","summary":"New task","issuetype":"Task"}'

# Create by JSON file
jira-cli create --json-file=issue.json

# Create with base64-encoded description
jira-cli create --project=FOO --summary="Formatted" --description="PHA+SGVsbG88L3A+" --base64

# Chain: create and export to CSV
jira-cli create --project=FOO --summary="Bug" create_csv --filename=new.csv
```

---

## Python API

The internal functions can be imported directly:

```python
from jira_cli.main import get_jira_connection, read, display_issues

conn = get_jira_connection()

issues = read(conn, project="FOO", status="In Progress", limit=50)
display_issues(issues, reduced=True)
```

**`get_jira_connection() -> Jira`**
Reads `~/.config/jira-cli/config.json` and returns an authenticated client.

**`read(jira_conn, issue_number=None, project=None, sprint=None, limit=10, status=None, resolution=None) -> List[Dict]`**
Core query function. Returns raw JIRA API dicts. Requires either `issue_number` or `project`.

**`display_issues(issues, reduced=False, comment_summary=False)`**
Prints issues to stdout with ANSI colors.

**`create_issue_fields(json_str=None, json_file=None, project=None, summary=None, description=None, issuetype="Task", priority=None, assignee=None, labels=(), components=(), extra_fields=None, is_base64=False) -> dict`**
Builds and validates a JIRA issue fields dict from either JSON or individual arguments. Handles base64 decoding and shorthand normalization.

---

## Development

Requires Python 3.7, 3.8, or 3.9.

```bash
# Lint (errors only)
pip install pylint
pylint --disable=all --enable=E jira_cli/

# Format
pip install black isort
black jira_cli/
isort jira_cli/
```
