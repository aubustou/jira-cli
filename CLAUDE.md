# CLAUDE.md — jira-cli

## Overview

`jira-cli` (PyPI: `jira-cli-top-moumoute`) is a Python CLI tool for querying and exporting JIRA issues from the command line. It wraps `atlassian-python-api` with a chainable Click interface, solving the problem of quickly browsing issues, filtering by project/sprint/status, and exporting results to CSV without writing custom scripts.

It is a **CLI application**, not an importable library — though its internal functions (`read`, `display_issues`, etc.) can be imported directly if needed.

---

## Architecture

```
jira_cli/
├── __init__.py       # empty
├── main.py           # CLI entry point, connection management, commands
└── model.py          # Dataclass models (Sprint, Issue) with apischema deserializers
```

**Data flow:**
1. `main()` (Click group, `chain=True`) initializes the JIRA connection on startup.
2. Each CLI command is registered as a `@generator` or `@processor` — wrappers that turn commands into stream functions.
3. `process_commands()` (result callback) pipes the output of each command into the next, Unix-pipe style.
4. `read()` queries raw JIRA API dicts; `display_issues()` renders them; `create_csv()` writes them to disk.

**Note:** `model.py` defines `Sprint` and `Issue` dataclasses but they are **not used** by `main.py`. The CLI works entirely with raw `dict` responses from `atlassian-python-api`.

---

## Core Concepts & Terminology

| Term | Meaning |
|------|---------|
| **generator** | A `@generator`-decorated command that produces issues into the stream (source). |
| **processor** | A `@processor`-decorated command that consumes and re-yields issues from the stream (transform/sink). |
| **stream** | The lazy iterator of raw JIRA issue dicts passed between chained commands. |
| **chain** | Click `chain=True` group — multiple subcommands can be listed in one invocation and their outputs pipe into each other. |
| **raw issue dict** | The unmodified `dict` returned by `atlassian-python-api` for a JIRA issue — shape mirrors the JIRA REST API response. |
| **COMMENT_TAGS** | Structured section headers in JIRA comments: `#Summary`, `#Details`, `#API changes`, `#Configuration changes`. |
| **config file** | `~/.config/jira-cli/config.json` — must exist with `jira_url`, `confluence_url`, `user`, `password`. |

---

## Public API Reference

### CLI Commands

```
jira-cli [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...
```

#### `read` (generator)
Query issues from JIRA and print them to stdout.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--issue-number` | str | None | Fetch a single issue by key (e.g. `FOO-123`) |
| `--project` | str | None | Project key to query |
| `--sprint` | str | None | Sprint name substring (requires `--project`) |
| `--limit` | int | 10 | Max issues returned (JQL queries only) |
| `--reduced` | flag | False | Print only key + summary |
| `--comment-summary` | flag | False | Include the `#Summary` comment section |
| `--status` | str | None | Post-filter by status name (case-insensitive) |
| `--resolution` | str | None | Post-filter by resolution name (case-insensitive) |

#### `create_csv` (processor)
Consume issues from the stream and write a semicolon-delimited CSV.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--filename` | Path | `output.csv` | Output file path |

CSV columns: `ticket;title;summary` — where `summary` is extracted from the `#Summary` comment tag.

---

### Python Functions (importable)

**`jira_cli.main`**

```python
get_jira_connection() -> atlassian.Jira
```
Reads `~/.config/jira-cli/config.json` and returns an authenticated `Jira` client. Sets the global `JIRA_CONN`.

```python
get_confluence_connection() -> atlassian.Confluence
```
Same as above for Confluence. Sets `CONFLUENCE_CONN`.

```python
read(
    jira_conn: Jira,
    issue_number: str | None = None,
    project: str | None = None,
    sprint: str | None = None,
    limit: int = 10,
    status: str | None = None,
    resolution: str | None = None,
) -> List[Dict]
```
Core query function. Returns raw JIRA API dicts. Raises `RuntimeError` if neither `issue_number` nor `project` is provided.

```python
display_issues(issues: List[Dict], reduced: bool = False, comment_summary: bool = False)
```
Prints issues to stdout with ANSI colors.

```python
get_summary_from_comment(comment: str) -> str
```
Extracts text between `#Summary` and the next `COMMENT_TAGS` marker. Strips `\xa0`.

```python
paginate(func: Callable, key: str = "values", start: int = 0, limit: int = 50, **kwargs)
```
Generator that pages through an `atlassian-python-api` paginated endpoint. Stops at empty results or 1,000,000 items.

```python
processor(f: Callable) -> Callable   # decorator
generator(f: Callable) -> Callable   # decorator
```
Decorators for building chainable Click commands. `generator` yields into the stream; `processor` consumes and re-yields.

**`jira_cli.model`**

```python
@dataclass
class Sprint:
    id: int; name: str; project_id: int; state: str; start_date: datetime
    goals: list[str]; completion_date: Optional[datetime]; number: int  # extracted from name

@dataclass
class Issue:
    key: str; summary: str; project: str; reporter: str; type: str; priority: str
    status: str; creation_date: datetime; update_date: Optional[datetime]
    resolution_date: Optional[datetime]; assignee: Optional[str]; sprint: Optional[str]
    description: Optional[str]; resolution: Optional[str]; color_label: Optional[str]
    labels: list[str]; story_points: Optional[int]
    affect_versions: list[str]; fix_versions: list[str]
    comments/notes_to_dev/comment_summary/...: list[str]
    url: str  # auto-set to https://jira.outscale.internal/browse/{key}

from_sprint(content: dict) -> Sprint   # apischema deserializer
from_issue(content: dict) -> Issue     # apischema deserializer
get_versions(content: list[dict]) -> list[str]
```

---

## Usage Examples

```bash
# 1. Read the 20 most recent issues in a project
jira-cli read --project=FOO --limit=20

# 2. Read a single issue by key
jira-cli read --issue-number=FOO-123

# 3. Read all issues in a sprint, filter by status, compact output
jira-cli read --project=FOO --sprint="Sprint 42" --status=Open --reduced

# 4. Chain: read open issues and export to CSV
jira-cli read --project=FOO --status=Open create_csv --filename=open_issues.csv

# 5. Chain multiple reads into one CSV (both sets flow through the stream)
jira-cli read --project=FOO --sprint="Sprint 42" read --project=BAR --limit=5 create_csv
```

**Programmatic use:**
```python
from jira_cli.main import get_jira_connection, read, display_issues

conn = get_jira_connection()
issues = read(conn, project="FOO", status="In Progress", limit=50)
display_issues(issues, reduced=True)
```

---

## Integration Guide

### Install

```bash
pip install jira-cli-top-moumoute
# or from source:
pip install -e .
```

**Dependencies:** `click==8.0.0`, `atlassian-python-api==3.10.0`, `apischema`

### Configuration

Create `~/.config/jira-cli/config.json` before first use:

```json
{
  "jira_url": "https://jira.example.com",
  "confluence_url": "https://confluence.example.com",
  "user": "your-username",
  "password": "your-password-or-token"
}
```

- No environment variables are used.
- No `init()` call is required; connection is established automatically when the CLI starts or when `get_jira_connection()` is called.
- SSL verification is always disabled (`verify_ssl=False`). Suppress `urllib3` warnings — they are silenced globally on import.

---

## Conventions & Constraints

- **Raw dicts, not models:** The CLI pipeline passes raw `atlassian-python-api` dicts, not `Issue`/`Sprint` dataclass instances. `model.py` types must be instantiated manually via `from_issue()`/`from_sprint()` if needed.
- **One required argument to `read()`:** Must provide `issue_number` OR `project`. Omitting both raises `RuntimeError("Missing argument")`.
- **Status/resolution filtering is post-fetch:** Filtering by `--status` or `--resolution` downloads all matching issues first, then filters in Python. For large projects, prefer JQL-level filtering or use `--limit`.
- **Sprint lookup by name substring:** `--sprint` matches any sprint whose `name` contains the given string. Non-unique matches return the first hit.
- **Hardcoded JIRA URL in display and model:** `display_issues()` and `Issue.__post_init__` hardcode `https://jira.outscale.internal/browse/` for the `url` field. This does not affect querying.
- **Hardcoded custom fields:** Epic link = `customfield_10500`, story points = `customfield_10003`. These may not match your JIRA instance.
- **Credentials stored in plaintext** in config.json.
- **`processor` decorator pattern:** When adding a new chained command, decorate with `@main.command()` + `@processor` (sink) or `@generator` (source). The first argument of a `@processor` function is always the upstream `stream` iterator.
- **`paginate()` off-by-one:** `start` increments by `limit + 1` per page. This matches the `atlassian-python-api` pagination convention.

---

## Testing

No test files exist in this repository.

**Lint only (CI):**
```bash
pip install pylint
pylint --disable=all --enable=E jira_cli/
```

**Code style:**
```bash
pip install black isort
black jira_cli/          # line-length=88
isort jira_cli/          # profile: default, multi_line_output=3
```

Python version targets: 3.7, 3.8, 3.9 (per `.travis.yml`). Note: `model.py` uses `list[str]` (PEP 585) which requires Python 3.9+ at runtime without `from __future__ import annotations`.
