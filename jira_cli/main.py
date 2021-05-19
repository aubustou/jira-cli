import json
from pathlib import Path
from typing import Callable, Dict, List, Optional
from pprint import pprint

import atlassian
import click
import urllib3

urllib3.disable_warnings()

CONFIGURATION_FILE = Path.home() / ".config" / "jira-cli" / "config.json"
JIRA_CONN: Optional[atlassian.Jira] = None


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


@click.group()
def main():
    global JIRA_CONN
    config = json.loads(CONFIGURATION_FILE.read_text())

    JIRA_CONN = atlassian.Jira(
        url=config["url"],
        username=config["user"],
        password=config["password"],
        verify_ssl=False,
    )
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


@main.command()
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
def read(
    issue_number: Optional[str] = None,
    project: Optional[str] = None,
    sprint: Optional[str] = None,
    limit: int = 10,
    reduced: bool = False,
    comment_summary: bool = False,
):
    issues: List[Dict] = []
    if issue_number:
        issues = [JIRA_CONN.issue(issue_number)]
    elif sprint and project:

        board_id = next(
            (x for x in JIRA_CONN.get_all_agile_boards(project_key=project)["values"]),
            {},
        ).get("id")

        sprint_id = next(
            (
                x
                for y in paginate(JIRA_CONN.get_all_sprint, limit=50, board_id=board_id)
                for x in y
                if sprint in x["name"]
            )
        )["id"]
        for page in paginate(
            JIRA_CONN.get_sprint_issues, key="issues", sprint_id=sprint_id
        ):
            issues.extend(page)
    elif project:
        issues = JIRA_CONN.jql(f"project={project} ORDER BY key DESC", limit=limit)[
            "issues"
        ]
    else:
        raise RuntimeError("Missing argument")
    # from pprint import pprint
    # pprint(issues)

    display_issues(issues, reduced, comment_summary)


def display_issues(issues: List[Dict], reduced: bool = False, comment_summary: bool=False):
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
                    "comment_summary": next((x["body"] for x in issue["fields"]["comment"]["comments"] if "Summary" in x["body"]), "")
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
            click.echo(f"{Colors.GREEN}{key}:{Colors.END} \n\t{value}\n")


if __name__ == "__main__":
    main()
