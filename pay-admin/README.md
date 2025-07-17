[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](../LICENSE)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=bcgov_sbc-pay&metric=alert_status)](https://sonarcloud.io/code?id=bcgov_sbc-pay&selected=bcgov_sbc-pay%3Apay-admin)
[![codecov](https://codecov.io/gh/bcgov/sbc-pay/branch/main/graph/badge.svg?flag=payapi)](https://codecov.io/gh/bcgov/sbc-pay/tree/main/pay-admin)

# PAY Admin

Flask Admin UI for managaing Pay/Fee codes and values.

## Development Environment

Follow the instructions of the [Development Readme](https://github.com/bcgov/entity/blob/master/docs/development.md)
to setup your local development environment.

## Development Setup

1. Follow the [instructions](https://github.com/bcgov/entity/blob/master/docs/setup-forking-workflow.md) to checkout the project from GitHub.
2. Open the pay-api directory in VS Code to treat it as a project (or WSL projec). To prevent version clashes, set up a
virtual environment to install the Python packages used by this project.
3. Run `make setup` to set up the virtual environment and install libraries.

You also need to set up the variables used for environment-specific settings:
1. Copy the [dotenv template file](./docs/dotenv_template) to somewhere above the source code and rename to `.env`. You will need to fill in missing values.

## Running the PAY Database on localhost

To prepare your local database:
1. In the [root project folder](../docker/docker-compose.yml): `docker-compose up -d`
2. In your `venv` environment: `python manage.py db upgrade`

## Running PAY Admin

1. Start the flask server with `python wsgi.py`
2. View the [Admin](http://127.0.0.1:5000/).

## CI

1. Run `make ci` for running all lint and tests.
