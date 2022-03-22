from setuptools import find_packages, setup

setup(
    name="jira-cli-top-moumoute",
    version="0.9.1",
    packages=find_packages(),
    author="aubustou",
    author_email="survivalfr@yahoo.fr",
    description="CLI to connect to JIRA",
    url="https://www.github.com/aubustou/jira-cli",
    entry_points={"console_scripts": ["jira-cli = jira_cli.main:main"]},
    install_requires=[
        "click==8.0.0",
        "atlassian-python-api==3.10.0",
        "apischema",
    ],
)
