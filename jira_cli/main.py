import json
import logging
from pathlib import Path
from typing import Optional

import atlassian
import click

CONFIGURATION_FILE = Path.home() / ".config" / "jira-cli" / "config.json"


@click.command()
@click.option("--action", default="read", help="Action to query")
@click.option(
    "--issue_number", prompt="Issue number requested", help="the ticket you need"
)
def main(
    action: str, issue_number: Optional[str] = None, project: Optional[str] = None
) -> str:
    """Simple program that greets NAME for a total of COUNT times."""

    logging.basicConfig(level=logging.DEBUG)
    if action not in {"read"}:
        raise RuntimeError(f"Unsupported action {action}")

    config = json.loads(CONFIGURATION_FILE.read_text())

    jira = atlassian.Jira(
        url=config["url"],
        username=config["user"],
        password=config["password"],
        verify_ssl=False,
    )

    return jira.issue(issue_number)


if __name__ == "__main__":
    main()
