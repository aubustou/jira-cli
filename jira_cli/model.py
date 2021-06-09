from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from apischema import deserializer


@dataclass
class Sprint:
    id: int
    name: str
    project_id: int
    state: str
    start_date: datetime
    goals: list[str] = field(default_factory=list)
    completion_date: Optional[datetime] = None

    number: int = field(init=False)

    def __post_init__(self):
        self.number = int("".join([x for x in self.name if x.isdigit()]))

    @property
    def day_start_date(self):
        return self.start_date.date()

    @property
    def listed_goals(self):
        return "\n#".join(self.goals)


@deserializer
def from_sprint(content: dict) -> Sprint:
    return Sprint(
        id=content["id"],
        name=content["name"],
        project_id=content["originBoardId"],
        state=content["state"],
        start_date=datetime.strptime(content["startDate"], "%Y-%m-%dT%H:%M:%S.%fZ"),
        completion_date=datetime.strptime(
            content["completeDate"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        if content["completeDate"]
        else None,
        goals=[x for x in content["goal"].splitlines() if x] if content["goal"] else [],
    )


@dataclass
class Issue:
    key: str
    summary: str
    project: str
    reporter: str
    type: str
    priority: str

    status: str

    creation_date: datetime
    update_date: Optional[datetime] = None
    resolution_date: Optional[datetime] = None

    assignee: Optional[str] = None
    sprint: Optional[str] = None
    description: Optional[str] = None
    resolution: Optional[str] = None
    color_label: Optional[str] = None
    labels: list[str] = field(default_factory=list)

    story_points: Optional[int] = None

    affect_versions: list[str] = field(default_factory=list)
    fix_versions: list[str] = field(default_factory=list)

    comments: list[str] = field(default_factory=list)
    notes_to_dev: list[str] = field(default_factory=list)
    comment_summary: list[str] = field(default_factory=list)
    comment_public_api_changes: list[str] = field(default_factory=list)
    comment_internal_api_changes: list[str] = field(default_factory=list)
    comment_configuration_changes: list[str] = field(default_factory=list)
    comment_details: list[str] = field(default_factory=list)

    url: str = field(default="", init=False)

    def __post_init__(self):
        self.url = "https://jira.outscale.internal/browse/" + self.key


def get_versions(content: list[dict]) -> list[str]:
    return [x["name"] for x in content] if content else []


@deserializer
def from_issue(content: dict) -> Issue:
    sprint = (content.get("sprint") or content.get("closedSprint") or {}).get("name")
    issue = Issue(
        key=content["key"],
        summary=content["fields"]["summary"],
        project=content["fields"]["project"]["key"],
        reporter=content["fields"]["reporter"]["displayName"],
        type=content["fields"]["issuetype"]["name"],
        priority=content["fields"]["priority"]["name"],
        status=content["fields"]["status"]["name"],
        creation_date=content["fields"]["created"],
        update_date=content["fields"]["updated"],
        resolution_date=content["fields"]["resolutiondate"],
        assignee=content["fields"]["assignee"]["displayName"]
        if content["fields"]["assignee"]
        else None,
        sprint=sprint,
        description=content["fields"]["description"],
        resolution=content["fields"]["resolution"]["name"]
        if content["fields"]["resolution"]
        else None,
        color_label=content["fields"]["epic"]["name"]
        if content["fields"].get("epic")
        else None,
        labels=content["fields"]["labels"],
        story_points=content["fields"].get("customfield_10003"),
        affect_versions=get_versions(content["fields"]["versions"]),
        fix_versions=get_versions(content["fields"]["fixVersions"]),
    )
    return issue
