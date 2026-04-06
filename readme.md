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
