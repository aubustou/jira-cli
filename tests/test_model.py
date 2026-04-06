"""Unit tests for jira_cli.model"""

from datetime import datetime

from jira_cli.model import Issue, Sprint, from_issue, from_sprint, get_versions

# ---------------------------------------------------------------------------
# get_versions
# ---------------------------------------------------------------------------


class TestGetVersions:
    def test_returns_names(self):
        assert get_versions([{"name": "1.0"}, {"name": "2.0"}]) == ["1.0", "2.0"]

    def test_empty_list(self):
        assert get_versions([]) == []

    def test_none_returns_empty(self):
        assert get_versions(None) == []


# ---------------------------------------------------------------------------
# Sprint dataclass
# ---------------------------------------------------------------------------


class TestSprint:
    def _sprint(self, **overrides):
        defaults = dict(
            id=1,
            name="Sprint 5",
            project_id=10,
            state="active",
            start_date=datetime(2024, 1, 1),
        )
        defaults.update(overrides)
        return Sprint(**defaults)

    def test_number_extracted_from_name(self):
        s = self._sprint(name="Sprint 42")
        assert s.number == 42

    def test_number_multidigit(self):
        s = self._sprint(name="Team Sprint 123 Beta")
        assert s.number == 123

    def test_day_start_date(self):
        s = self._sprint(start_date=datetime(2024, 3, 15, 9, 0, 0))
        assert s.day_start_date.year == 2024
        assert s.day_start_date.month == 3
        assert s.day_start_date.day == 15

    def test_listed_goals(self):
        s = self._sprint(goals=["Goal A", "Goal B"])
        assert s.listed_goals == "Goal A\n#Goal B"

    def test_empty_goals(self):
        s = self._sprint(goals=[])
        assert s.listed_goals == ""


# ---------------------------------------------------------------------------
# from_sprint deserializer
# ---------------------------------------------------------------------------


class TestFromSprint:
    def _content(self, **overrides):
        defaults = {
            "id": 10,
            "name": "Sprint 3",
            "originBoardId": 99,
            "state": "closed",
            "startDate": "2024-01-01T08:00:00.000Z",
            "completeDate": "2024-01-14T08:00:00.000Z",
            "goal": "Ship feature X\nFix bug Y",
        }
        defaults.update(overrides)
        return defaults

    def test_basic_deserialization(self):
        s = from_sprint(self._content())
        assert s.id == 10
        assert s.name == "Sprint 3"
        assert s.project_id == 99
        assert s.state == "closed"
        assert s.number == 3

    def test_goals_split_by_line(self):
        s = from_sprint(self._content(goal="Goal A\nGoal B\n"))
        assert s.goals == ["Goal A", "Goal B"]

    def test_no_goal_gives_empty_list(self):
        s = from_sprint(self._content(goal=None))
        assert s.goals == []

    def test_no_complete_date(self):
        s = from_sprint(self._content(completeDate=None))
        assert s.completion_date is None

    def test_complete_date_parsed(self):
        s = from_sprint(self._content(completeDate="2024-01-14T08:00:00.000Z"))
        assert s.completion_date == datetime(2024, 1, 14, 8, 0, 0)


# ---------------------------------------------------------------------------
# Issue dataclass
# ---------------------------------------------------------------------------


class TestIssue:
    def _issue(self, **overrides):
        defaults = dict(
            key="FOO-1",
            summary="Test",
            project="FOO",
            reporter="Alice",
            type="Bug",
            priority="High",
            status="Open",
            creation_date=datetime(2024, 1, 1),
        )
        defaults.update(overrides)
        return Issue(**defaults)

    def test_url_set_from_key(self):
        issue = self._issue(key="FOO-42")
        assert issue.url == "https://jira.outscale.internal/browse/FOO-42"

    def test_optional_fields_default_to_none(self):
        issue = self._issue()
        assert issue.assignee is None
        assert issue.sprint is None
        assert issue.resolution is None

    def test_list_fields_default_empty(self):
        issue = self._issue()
        assert issue.labels == []
        assert issue.comments == []
        assert issue.fix_versions == []


# ---------------------------------------------------------------------------
# from_issue deserializer
# ---------------------------------------------------------------------------


class TestFromIssue:
    def _content(self, **overrides):
        defaults = {
            "key": "FOO-7",
            "fields": {
                "summary": "Do the thing",
                "project": {"key": "FOO"},
                "reporter": {"displayName": "Alice"},
                "issuetype": {"name": "Story"},
                "priority": {"name": "Medium"},
                "status": {"name": "In Progress"},
                "created": datetime(2024, 2, 1),
                "updated": datetime(2024, 2, 5),
                "resolutiondate": None,
                "assignee": {"displayName": "Bob"},
                "description": "Some description",
                "resolution": None,
                "epic": None,
                "labels": ["label-a"],
                "customfield_10003": 5,
                "versions": [{"name": "1.0"}],
                "fixVersions": [],
            },
        }
        # Allow nested field overrides
        if "fields" in overrides:
            defaults["fields"].update(overrides.pop("fields"))
        defaults.update(overrides)
        return defaults

    def test_basic_fields(self):
        issue = from_issue(self._content())
        assert issue.key == "FOO-7"
        assert issue.summary == "Do the thing"
        assert issue.project == "FOO"
        assert issue.reporter == "Alice"
        assert issue.type == "Story"
        assert issue.status == "In Progress"

    def test_assignee_populated(self):
        issue = from_issue(self._content())
        assert issue.assignee == "Bob"

    def test_assignee_none_when_missing(self):
        issue = from_issue(self._content(fields={"assignee": None}))
        assert issue.assignee is None

    def test_story_points(self):
        issue = from_issue(self._content())
        assert issue.story_points == 5

    def test_affect_versions(self):
        issue = from_issue(self._content())
        assert issue.affect_versions == ["1.0"]

    def test_resolution_name_extracted(self):
        issue = from_issue(self._content(fields={"resolution": {"name": "Fixed"}}))
        assert issue.resolution == "Fixed"

    def test_resolution_none_when_not_set(self):
        issue = from_issue(self._content())
        assert issue.resolution is None

    def test_color_label_from_epic(self):
        issue = from_issue(self._content(fields={"epic": {"name": "My Epic"}}))
        assert issue.color_label == "My Epic"

    def test_color_label_none_without_epic(self):
        issue = from_issue(self._content())
        assert issue.color_label is None

    def test_labels(self):
        issue = from_issue(self._content())
        assert issue.labels == ["label-a"]
