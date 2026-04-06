from __future__ import annotations

import base64
import json
from collections.abc import Callable, Iterator
from functools import update_wrapper
from pathlib import Path

import atlassian
import click
import urllib3
from atlassian.confluence import Confluence
from atlassian.jira import Jira

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIGURATION_FILE = Path.home() / ".config" / "jira-cli" / "config.json"
JIRA_CONN: atlassian.Jira | None = None
CONFLUENCE_CONN: atlassian.Confluence | None = None


class Colors:
    """ANSI color codes"""

    BLACK = "\033[0;30m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    BROWN = "\033[0;33m"
    BLUE = "\033[0;34m"
    PURPLE = "\033[0;35m"
    CYAN = "\033[0;36m"
    LIGHT_GRAY = "\033[0;37m"
    DARK_GRAY = "\033[1;30m"
    LIGHT_RED = "\033[1;31m"
    LIGHT_GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    LIGHT_BLUE = "\033[1;34m"
    LIGHT_PURPLE = "\033[1;35m"
    LIGHT_CYAN = "\033[1;36m"
    LIGHT_WHITE = "\033[1;37m"
    BOLD = "\033[1m"
    FAINT = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    NEGATIVE = "\033[7m"
    CROSSED = "\033[9m"
    END = "\033[0m"


def get_jira_connection() -> Jira:
    global JIRA_CONN
    config = json.loads(CONFIGURATION_FILE.read_text())

    JIRA_CONN = atlassian.Jira(
        url=config["jira_url"],
        username=config["user"],
        password=config["password"],
        verify_ssl=False,
    )
    return JIRA_CONN


def get_confluence_connection() -> Confluence:
    global CONFLUENCE_CONN
    config = json.loads(CONFIGURATION_FILE.read_text())

    CONFLUENCE_CONN = atlassian.Confluence(
        url=config["confluence_url"],
        username=config["user"],
        password=config["password"],
        verify_ssl=False,
    )
    return CONFLUENCE_CONN


@click.group(chain=True)
def main():
    get_jira_connection()
    pass


def paginate(
    func: Callable, key: str = "values", start: int = 0, limit: int = 50, **kwargs
):
    results = []
    while start < 1_000_000:
        results = func(limit=limit, start=start, **kwargs).get(key)
        if not results:
            break
        yield results
        start += limit + 1


@main.result_callback()
def process_commands(processors):
    """This result callback is invoked with an iterable of all the chained
    subcommands.  As in this example each subcommand returns a function
    we can chain them together to feed one into the other, similar to how
    a pipe on unix works.
    """
    # Start with an empty iterable.
    stream = ()

    # Pipe it through all stream processors.
    for processor in processors:
        stream = processor(stream)

    # Evaluate the stream and throw away the items.
    for _ in stream:
        pass


def processor(f):
    """Helper decorator to rewrite a function so that it returns another
    function from it.
    """

    def new_func(*args, **kwargs):
        def processor(stream):
            return f(stream, *args, **kwargs)

        return processor

    return update_wrapper(new_func, f)


def generator(f):
    """Similar to the :func:`processor` but passes through old values
    unchanged and does not pass through the values as parameter.
    """

    @processor
    def new_func(stream, *args, **kwargs):
        yield from stream
        yield from f(*args, **kwargs)

    return update_wrapper(new_func, f)


COMMENT_TAGS = ["#Summary", "#Details", "#API changes", "#Configuration changes"]


def get_summary_from_comment(comment: str) -> str:
    comment = comment.replace("\xa0", "")
    is_summary = False
    summary = []
    for line in comment.splitlines():
        if "#Summary" in line:
            is_summary = True
            continue
        elif any(x in line for x in COMMENT_TAGS):
            break
        if is_summary and line:
            summary.append(line)
    return "\n".join(summary)


@main.command()
@click.option(
    "--filename",
    default="output.csv",
    type=click.Path(writable=True, path_type=Path),
    help="The format for the filename.",
    show_default=True,
)
@processor
def create_csv(issues: list[dict], filename: Path):
    with filename.open("w", newline="\r\n") as file_:
        file_.write(";".join(["ticket", "title", "summary", "\r\n"]))
        for issue in issues:
            comment = next(
                (
                    x["body"]
                    for x in issue["fields"]["comment"]["comments"]
                    if "Summary" in x["body"]
                ),
                None,
            )
            file_.write(
                ";".join(
                    [
                        issue["key"],
                        issue["fields"]["summary"],
                        get_summary_from_comment(comment) if comment else "",
                        "\r\n",
                    ]
                )
            )
    # print(len(list(issues)))
    yield issues


def get_sprint(jira_conn: Jira, sprint: str, project: str) -> dict:
    board_id = next(
        (x for x in jira_conn.get_all_agile_boards(project_key=project)["values"]),
        {},
    ).get("id")

    return next(
        x
        for y in paginate(jira_conn.get_all_sprint, limit=50, board_id=board_id)
        for x in y
        if sprint in x["name"]
    )


@main.command("read")
@click.option("--issue-number", help="Ticket number", required=False)
@click.option("--project", help="Name of the project", required=False)
@click.option("--sprint", help="Sprint number", required=False)
@click.option("--limit", type=int, default=10, help="Max number of issues returned")
@click.option(
    "--reduced", is_flag=True, flag_value=True, help="Return only number and summary"
)
@click.option(
    "--comment-summary",
    is_flag=True,
    flag_value=True,
    help="Return only Summary Comments",
)
@click.option("--status", help="Status of the ticket")
@click.option("--resolution", help="Resolution level of the ticket")
@generator
def command_read(
    reduced: bool = False, comment_summary: bool = False, *args, **kwargs
) -> Iterator:
    issues = read(JIRA_CONN, *args, **kwargs)
    display_issues(issues, reduced, comment_summary)
    yield from issues


def read(
    jira_conn: Jira,
    issue_number: str | None = None,
    project: str | None = None,
    sprint: str | None = None,
    limit: int = 10,
    status: str | None = None,
    resolution: str | None = None,
) -> list[dict]:
    issues: list[dict] = []
    if issue_number:
        issues = [jira_conn.issue(issue_number)]
    elif sprint and project:
        sprint_id = get_sprint(jira_conn, sprint, project)["id"]
        for page in paginate(
            jira_conn.get_sprint_issues, key="issues", sprint_id=sprint_id
        ):
            issues.extend(page)
    elif project:
        issues = jira_conn.jql(f"project={project} ORDER BY key DESC", limit=limit)[
            "issues"
        ]
    else:
        raise RuntimeError("Missing argument")
    if status:
        issues = [
            x
            for x in issues
            if x["fields"]["status"]
            and x["fields"]["status"]["name"].lower() == status.lower()
        ]
    if resolution:
        issues = [
            x
            for x in issues
            if x["fields"]["resolution"]
            and x["fields"]["resolution"].get("name", "").lower() == resolution
        ]

    return issues


def create_issue_fields(
    json_str: str | None,
    json_file: Path | None,
    project: str | None,
    summary: str | None,
    description: str | None,
    issuetype: str,
    priority: str | None,
    assignee: str | None,
    labels: tuple[str, ...],
    components: tuple[str, ...],
    extra_fields: str | None,
    is_base64: bool,
) -> dict:
    arg_based = project is not None or summary is not None
    json_based = json_str is not None or json_file is not None

    if json_based and arg_based:
        raise click.UsageError(
            "Cannot combine --json/--json-file with --project/--summary"
        )

    if json_based:
        raw = json_str if json_str else Path(json_file).read_text()
        fields = json.loads(raw)
    elif arg_based:
        if not project or not summary:
            raise click.UsageError("--project and --summary are both required")
        fields = {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issuetype},
        }
        if description is not None:
            fields["description"] = description
        if priority:
            fields["priority"] = {"name": priority}
        if assignee:
            fields["assignee"] = {"name": assignee}
        if labels:
            fields["labels"] = list(labels)
        if components:
            fields["components"] = [{"name": c} for c in components]
    else:
        raise click.UsageError("Provide --json/--json-file or --project and --summary")

    if is_base64 and "description" in fields:
        fields["description"] = base64.b64decode(fields["description"]).decode("utf-8")

    if extra_fields:
        fields.update(json.loads(extra_fields))

    # Normalize shorthand forms from JSON input
    if isinstance(fields.get("project"), str):
        fields["project"] = {"key": fields["project"]}
    if isinstance(fields.get("issuetype"), str):
        fields["issuetype"] = {"name": fields["issuetype"]}

    return fields


@main.command("create")
@click.option("--json", "json_str", default=None, help="Inline JSON with issue fields")
@click.option(
    "--json-file",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Path to JSON file with issue fields",
)
@click.option("--project", default=None, help="Project key (e.g. FOO)")
@click.option("--summary", default=None, help="Issue summary/title")
@click.option("--description", default=None, help="Issue description body")
@click.option("--issuetype", default="Task", help="Issue type name", show_default=True)
@click.option("--priority", default=None, help="Priority name")
@click.option("--assignee", default=None, help="Assignee username")
@click.option("--labels", multiple=True, help="Labels (repeatable)")
@click.option("--components", multiple=True, help="Component names (repeatable)")
@click.option("--extra-fields", default=None, help="Additional fields as JSON string")
@click.option(
    "--base64",
    "is_base64",
    is_flag=True,
    help="Decode description from base64",
)
@generator
def command_create(
    json_str,
    json_file,
    project,
    summary,
    description,
    issuetype,
    priority,
    assignee,
    labels,
    components,
    extra_fields,
    is_base64,
):
    fields = create_issue_fields(
        json_str,
        json_file,
        project,
        summary,
        description,
        issuetype,
        priority,
        assignee,
        labels,
        components,
        extra_fields,
        is_base64,
    )
    result = JIRA_CONN.create_issue(fields=fields)
    issue_key = result.get("key", result)
    click.echo(f"Created issue: {issue_key}")
    full_issue = JIRA_CONN.issue(issue_key)
    yield full_issue


def display_issues(
    issues: list[dict], reduced: bool = False, comment_summary: bool = False
):
    first_issue = True
    for issue in reversed(issues):
        if not first_issue:
            click.echo(f"{Colors.GREEN}=============={Colors.END}")
        else:
            first_issue = False

        key = issue["key"]
        response = {
            "key": key,
            "summary": issue["fields"]["summary"],
        }

        if comment_summary:
            response.update(
                {
                    "comment_summary": next(
                        (
                            x["body"]
                            for x in issue["fields"]["comment"]["comments"]
                            if "Summary" in x["body"]
                        ),
                        "",
                    )
                }
            )

        if not reduced:
            response.update(
                {
                    "type": issue["fields"]["issuetype"]["name"],
                    "assignee": issue["fields"]["assignee"]["displayName"],
                    "creator": issue["fields"]["creator"]["displayName"],
                    "description": issue["fields"]["description"],
                    "url": "https://jira.outscale.internal/browse/" + key,
                }
            )
            epic_link_number = issue["fields"].get("customfield_10500")
            if epic_link_number:
                response["epic"] = JIRA_CONN.issue(epic_link_number)["fields"][
                    "summary"
                ]
        for key, value in response.items():
            click.echo(f"{Colors.GREEN}{key}:{Colors.END} \n\t{value}")


if __name__ == "__main__":
    main()
