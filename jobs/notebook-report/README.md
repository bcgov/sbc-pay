# Pay Notebook Report

Generate notebook report

## Development Environment

Follow the instructions of the [Development Readme](https://github.com/bcgov/entity/blob/master/docs/development.md)
to setup your local development environment.

## Development Setup

1. Follow the [instructions](https://github.com/bcgov/entity/blob/master/docs/setup-forking-workflow.md) to checkout the project from GitHub.
2. Open the notebook-report directory in VS Code to treat it as a project (or WSL projec). To prevent version clashes, set up a virtual environment to install the Python packages used by this project.
3. Run `make setup` to set up the virtual environment and install libraries.

## Running Pay Notebook Report

1. Run `poetry env activate`
2. Run notebook with `python notebookreport.py`

### Important: Please remember to do "git update-index --add --chmod=+x run.sh" before run.sh is commit to github on first time. 
### Build API - can be done in VS Code

This hosted on GCP.
