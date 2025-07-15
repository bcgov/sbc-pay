.PHONY: license
.PHONY: setup
.PHONY: ci cd
.PHONY: run

MKFILE_PATH:=$(abspath $(lastword $(MAKEFILE_LIST)))
CURRENT_ABS_DIR:=$(patsubst %/,%,$(dir $(MKFILE_PATH)))

PROJECT_NAME:=pay_api
DOCKER_NAME:=pay-api

#################################################################################
# COMMANDS -- Setup                                                             #
#################################################################################
setup: install ## Setup the project

clean: clean-build clean-pyc clean-test ## Clean the project
	rm -rf venv/

clean-build: ## Clean build files
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -fr {} +

clean-pyc: ## Clean cache files
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## clean test files
	find . -name '.pytest_cache' -exec rm -fr {} +
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/

install: clean
	pip install poetry==2.1.3;\
	poetry install

#################################################################################
# COMMANDS - CI                                                                 #
#################################################################################
ci: isort-ci black-ci lint flake8 test ## CI flow

isort: 
	poetry run isort .

isort-ci:
	poetry run isort --check .

black: ## Linting with black
	poetry run black .

black-ci:
	poetry run black --check .

pylint: ## Linting with pylint
	poetry run pylint src/$(PROJECT_NAME)

flake8: ## Linting with flake8
	poetry run flake8 src/$(PROJECT_NAME) tests

lint: isort black pylint flake8 ## run all lint type scripts

test: ## Unit testing
	poetry run pytest

mac-cov: test ## Run the coverage report and display in a browser window (mac)
	@open -a "Google Chrome" htmlcov/index.html

#################################################################################
# COMMANDS - CD
#################################################################################
build: ## Build the docker container
	docker build . -t $(DOCKER_NAME) \
		--build-arg VCS_REF=$(shell git rev-parse --short HEAD) \
		--build-arg BUILD_DATE=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ") \

build-nc: ## Build the docker container without caching
	docker build --no-cache -t $(DOCKER_NAME) .
#################################################################################
# COMMANDS - Local                                                              #
#################################################################################
run: ## Run the project in local
	poetry run flask run -p 5000

#################################################################################
# Self Documenting Commands                                                     #
#################################################################################
.PHONY: help

.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
