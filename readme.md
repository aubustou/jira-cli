# Jira CLI

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Getting Started

### Prerequisites

You will need [Python 3.7+](https://www.python.org/) or later. Earlier versions including Python 2 are not supported.

### Installing from package

You can get the package from [pypi](https://pypi.org/project/jira-cli/):
```
pip3 install jira-cli
```

### Installing from sources

It is a good practice to create a [dedicated virtualenv](https://virtualenv.pypa.io/en/latest/) first. Even if it usually won't harm to install Python libraries directly on the system, better to contain dependencies in a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Then install jira-cli in your virtual env:
```bash
pip install -e .
```
