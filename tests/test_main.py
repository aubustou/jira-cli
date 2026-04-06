"""Unit tests for jira_cli.main"""

import base64
import binascii
import json
from unittest.mock import MagicMock

import click
import pytest

from jira_cli.main import (
    create_csv,
    create_issue_fields,
    generator,
    get_summary_from_comment,
    paginate,
    processor,
    read,
)

# ---------------------------------------------------------------------------
# get_summary_from_comment
# ---------------------------------------------------------------------------


class TestGetSummaryFromComment:
    def test_extracts_summary(self):
        comment = "#Summary\nThis is the summary text.\n"
        assert get_summary_from_comment(comment) == "This is the summary text."

    def test_stops_at_next_tag(self):
        comment = "#Summary\nSummary line.\n#Details\nDetails line.\n"
        assert get_summary_from_comment(comment) == "Summary line."

    def test_multiline_summary(self):
        comment = "#Summary\nLine one.\nLine two.\n#Details\nignored\n"
        assert get_summary_from_comment(comment) == "Line one.\nLine two."

    def test_no_summary_tag_returns_empty(self):
        assert get_summary_from_comment("Just some text.") == ""

    def test_strips_nbsp(self):
        comment = "#Summary\n\xa0real text\xa0\n"
        assert get_summary_from_comment(comment) == "real text"

    def test_empty_lines_inside_summary_skipped(self):
        comment = "#Summary\n\nActual content.\n"
        assert get_summary_from_comment(comment) == "Actual content."


# ---------------------------------------------------------------------------
# paginate
# ---------------------------------------------------------------------------


class TestPaginate:
    def test_single_page(self):
        func = MagicMock(return_value={"values": [1, 2, 3]})
        # Return empty on second call to stop pagination
        func.side_effect = [
            {"values": [1, 2, 3]},
            {"values": []},
        ]
        pages = list(paginate(func, key="values", limit=50))
        assert pages == [[1, 2, 3]]

    def test_multiple_pages(self):
        func = MagicMock()
        func.side_effect = [
            {"values": ["a", "b"]},
            {"values": ["c"]},
            {"values": []},
        ]
        pages = list(paginate(func, key="values", limit=2))
        assert pages == [["a", "b"], ["c"]]

    def test_none_result_stops(self):
        func = MagicMock(return_value={"values": None})
        pages = list(paginate(func))
        assert pages == []

    def test_kwargs_forwarded(self):
        func = MagicMock(side_effect=[{"values": [1]}, {"values": []}])
        list(paginate(func, key="values", limit=10, board_id=42))
        func.assert_any_call(limit=10, start=0, board_id=42)


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


def _make_issue(key="FOO-1", summary="Test issue", status="Open", resolution=None):
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "resolution": {"name": resolution} if resolution else None,
            "comment": {"comments": []},
            "issuetype": {"name": "Bug"},
            "assignee": {"displayName": "Alice"},
            "creator": {"displayName": "Bob"},
            "description": "desc",
        },
    }


class TestRead:
    def test_reads_single_issue(self):
        conn = MagicMock()
        conn.issue.return_value = _make_issue("FOO-1")
        issues = read(conn, issue_number="FOO-1")
        conn.issue.assert_called_once_with("FOO-1")
        assert len(issues) == 1
        assert issues[0]["key"] == "FOO-1"

    def test_reads_by_project_jql(self):
        conn = MagicMock()
        conn.jql.return_value = {"issues": [_make_issue("FOO-1"), _make_issue("FOO-2")]}
        issues = read(conn, project="FOO", limit=5)
        conn.jql.assert_called_once_with("project=FOO ORDER BY key DESC", limit=5)
        assert len(issues) == 2

    def test_raises_without_issue_or_project(self):
        conn = MagicMock()
        with pytest.raises(RuntimeError, match="Missing argument"):
            read(conn)

    def test_status_filter(self):
        conn = MagicMock()
        conn.jql.return_value = {
            "issues": [
                _make_issue("FOO-1", status="Open"),
                _make_issue("FOO-2", status="Closed"),
            ]
        }
        issues = read(conn, project="FOO", status="open")
        assert len(issues) == 1
        assert issues[0]["key"] == "FOO-1"

    def test_status_filter_case_insensitive(self):
        conn = MagicMock()
        conn.jql.return_value = {"issues": [_make_issue("FOO-1", status="In Progress")]}
        issues = read(conn, project="FOO", status="IN PROGRESS")
        assert len(issues) == 1

    def test_resolution_filter(self):
        conn = MagicMock()
        conn.jql.return_value = {
            "issues": [
                _make_issue("FOO-1", resolution="Fixed"),
                _make_issue("FOO-2", resolution=None),
            ]
        }
        issues = read(conn, project="FOO", resolution="fixed")
        assert len(issues) == 1
        assert issues[0]["key"] == "FOO-1"

    def test_reads_sprint(self):
        conn = MagicMock()
        # Board lookup
        conn.get_all_agile_boards.return_value = {"values": [{"id": 7}]}
        # Sprint pagination: one page with the target sprint, then empty
        conn.get_all_sprint.side_effect = [
            {"values": [{"id": 99, "name": "Sprint 42"}]},
            {"values": []},
        ]
        # Sprint issues pagination: one page then empty
        conn.get_sprint_issues.side_effect = [
            {"issues": [_make_issue("FOO-1")]},
            {"issues": []},
        ]
        issues = read(conn, project="FOO", sprint="42")
        assert len(issues) == 1
        assert issues[0]["key"] == "FOO-1"


# ---------------------------------------------------------------------------
# processor / generator decorators
# ---------------------------------------------------------------------------


class TestDecoratorHelpers:
    def test_processor_passes_stream(self):
        @processor
        def double(stream):
            for item in stream:
                yield item * 2

        wrapped = double()
        result = list(wrapped(iter([1, 2, 3])))
        assert result == [2, 4, 6]

    def test_generator_appends_to_stream(self):
        @generator
        def source():
            yield from [10, 20]

        wrapped = source()
        result = list(wrapped(iter([1, 2])))
        assert result == [1, 2, 10, 20]


# ---------------------------------------------------------------------------
# create_csv (CLI command via processor decorator)
# ---------------------------------------------------------------------------


class TestCreateCsv:
    def _issue_with_comment(self, key="FOO-1", summary="My Issue", comment_body=None):
        comments = [{"body": comment_body}] if comment_body else []
        return {
            "key": key,
            "fields": {
                "summary": summary,
                "comment": {"comments": comments},
            },
        }

    def test_writes_header_and_rows(self, tmp_path):
        out = tmp_path / "out.csv"
        issues = [self._issue_with_comment("FOO-1", "Issue One")]

        # create_csv is a Click command; .callback is the processor-wrapped fn
        stream_fn = create_csv.callback(filename=out)
        list(stream_fn(iter(issues)))

        content = out.read_text()
        assert "ticket;title;summary" in content
        assert "FOO-1" in content
        assert "Issue One" in content

    def test_extracts_summary_from_comment(self, tmp_path):
        out = tmp_path / "out.csv"
        comment = "#Summary\nThis is extracted.\n#Details\nignored"
        issues = [self._issue_with_comment("FOO-2", "T", comment_body=comment)]

        stream_fn = create_csv.callback(filename=out)
        list(stream_fn(iter(issues)))

        content = out.read_text()
        assert "This is extracted." in content

    def test_no_comment_writes_empty_summary(self, tmp_path):
        out = tmp_path / "out.csv"
        issues = [self._issue_with_comment("FOO-3", "No comment issue")]

        stream_fn = create_csv.callback(filename=out)
        list(stream_fn(iter(issues)))

        content = out.read_text()
        assert "FOO-3" in content


# ---------------------------------------------------------------------------
# create_issue_fields
# ---------------------------------------------------------------------------

_DEFAULTS = dict(
    json_str=None,
    json_file=None,
    project=None,
    summary=None,
    description=None,
    issuetype="Task",
    priority=None,
    assignee=None,
    labels=(),
    components=(),
    extra_fields=None,
    is_base64=False,
)


def _fields(**overrides):
    """Call create_issue_fields with defaults, applying overrides."""
    return create_issue_fields(**{**_DEFAULTS, **overrides})


class TestCreateIssueFieldsFromArgs:
    def test_minimal_args(self):
        result = _fields(project="FOO", summary="Title")
        assert result == {
            "project": {"key": "FOO"},
            "summary": "Title",
            "issuetype": {"name": "Task"},
        }

    def test_all_args(self):
        result = _fields(
            project="FOO",
            summary="Title",
            description="Body",
            issuetype="Bug",
            priority="High",
            assignee="alice",
            labels=("backend", "urgent"),
            components=("api", "auth"),
        )
        assert result["project"] == {"key": "FOO"}
        assert result["summary"] == "Title"
        assert result["description"] == "Body"
        assert result["issuetype"] == {"name": "Bug"}
        assert result["priority"] == {"name": "High"}
        assert result["assignee"] == {"name": "alice"}
        assert result["labels"] == ["backend", "urgent"]
        assert result["components"] == [{"name": "api"}, {"name": "auth"}]

    def test_missing_project_raises(self):
        with pytest.raises(click.UsageError, match="--project and --summary"):
            _fields(summary="Title")

    def test_missing_summary_raises(self):
        with pytest.raises(click.UsageError, match="--project and --summary"):
            _fields(project="FOO")

    def test_no_input_raises(self):
        with pytest.raises(click.UsageError, match="Provide --json"):
            _fields()

    def test_description_omitted_when_none(self):
        result = _fields(project="FOO", summary="Title")
        assert "description" not in result

    def test_optional_fields_omitted_when_empty(self):
        result = _fields(project="FOO", summary="Title")
        for key in ("priority", "assignee", "labels", "components"):
            assert key not in result


class TestCreateIssueFieldsFromJson:
    def test_inline_json(self):
        payload = json.dumps(
            {
                "project": "BAR",
                "summary": "From JSON",
                "issuetype": "Story",
            }
        )
        result = _fields(json_str=payload)
        assert result["project"] == {"key": "BAR"}
        assert result["summary"] == "From JSON"
        assert result["issuetype"] == {"name": "Story"}

    def test_json_file(self, tmp_path):
        f = tmp_path / "issue.json"
        f.write_text(
            json.dumps(
                {
                    "project": {"key": "BAZ"},
                    "summary": "From file",
                    "issuetype": {"name": "Task"},
                }
            )
        )
        result = _fields(json_file=f)
        assert result["project"] == {"key": "BAZ"}
        assert result["summary"] == "From file"

    def test_json_preserves_nested_dicts(self):
        payload = json.dumps(
            {
                "project": {"key": "FOO"},
                "summary": "Nested",
                "issuetype": {"name": "Epic"},
            }
        )
        result = _fields(json_str=payload)
        assert result["project"] == {"key": "FOO"}
        assert result["issuetype"] == {"name": "Epic"}

    def test_json_normalizes_shorthand_project(self):
        payload = json.dumps({"project": "FOO", "summary": "S", "issuetype": "Bug"})
        result = _fields(json_str=payload)
        assert result["project"] == {"key": "FOO"}
        assert result["issuetype"] == {"name": "Bug"}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _fields(json_str="{bad json")


class TestCreateIssueFieldsMutualExclusivity:
    def test_json_and_project_raises(self):
        with pytest.raises(click.UsageError, match="Cannot combine"):
            _fields(json_str='{"project":"X","summary":"S"}', project="FOO")

    def test_json_and_summary_raises(self):
        with pytest.raises(click.UsageError, match="Cannot combine"):
            _fields(json_str='{"project":"X","summary":"S"}', summary="Title")

    def test_json_file_and_project_raises(self, tmp_path):
        f = tmp_path / "issue.json"
        f.write_text("{}")
        with pytest.raises(click.UsageError, match="Cannot combine"):
            _fields(json_file=f, project="FOO")


class TestCreateIssueFieldsBase64:
    def test_decodes_base64_description_from_args(self):
        encoded = base64.b64encode(b"<p>Hello</p>").decode()
        result = _fields(
            project="FOO", summary="T", description=encoded, is_base64=True
        )
        assert result["description"] == "<p>Hello</p>"

    def test_decodes_base64_description_from_json(self):
        encoded = base64.b64encode(b"formatted text").decode()
        payload = json.dumps(
            {
                "project": "FOO",
                "summary": "S",
                "issuetype": "Task",
                "description": encoded,
            }
        )
        result = _fields(json_str=payload, is_base64=True)
        assert result["description"] == "formatted text"

    def test_base64_flag_without_description_is_noop(self):
        result = _fields(project="FOO", summary="T", is_base64=True)
        assert "description" not in result

    def test_invalid_base64_raises(self):
        with pytest.raises(binascii.Error):
            _fields(
                project="FOO", summary="T", description="!!!invalid!!!", is_base64=True
            )


class TestCreateIssueFieldsExtraFields:
    def test_merges_extra_fields(self):
        result = _fields(
            project="FOO",
            summary="T",
            extra_fields='{"customfield_10500": "EPIC-1", "labels": ["override"]}',
        )
        assert result["customfield_10500"] == "EPIC-1"
        assert result["labels"] == ["override"]

    def test_extra_fields_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _fields(project="FOO", summary="T", extra_fields="{bad}")
