ARG SOURCE_REPO=BCDevOps
ARG GOCROND_VERSION=0.6.2
ARG VCS_REF="missing"
ARG BUILD_DATE="missing"

FROM golang:1.22-bookworm AS go-crond-builder

ARG SOURCE_REPO
ARG GOCROND_VERSION

WORKDIR /tmp

RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Build go-crond from source with cgo disabled so os/user uses the pure-Go
# lookup path instead of the glibc/cgo path that was crashing on bookworm.
# The upstream repo predates Go modules, so create a temporary go.mod in the
# builder stage to resolve its dependencies before compiling.
RUN git clone --branch "${GOCROND_VERSION}" --depth 1 "https://github.com/${SOURCE_REPO}/go-crond.git" \
    && cd go-crond \
    && go mod init "github.com/${SOURCE_REPO}/go-crond" \
    && go mod tidy \
    && CGO_ENABLED=0 go build -tags osusergo,netgo -o /usr/local/bin/go-crond .

FROM python:3.12.2-bookworm
# ========================================================================================================
# Install go-crond (from https://github.com/BCDevOps/go-crond)
#  - Adds some additional logging enhancements on top of the upstream project;
#    https://github.com/webdevops/go-crond
#
# CRON Jobs in OpenShift:
# - https://blog.danman.eu/cron-jobs-in-openshift/
#
# --------------------------------------------------------------------------------------------------------
ARG SOURCE_REPO
ARG GOCROND_VERSION
ARG VCS_REF
ARG BUILD_DATE

ENV VCS_REF=${VCS_REF}
ENV BUILD_DATE=${BUILD_DATE}

LABEL org.label-schema.vcs-ref=${VCS_REF} \
    org.label-schema.build-date=${BUILD_DATE}

COPY --from=go-crond-builder /usr/local/bin/go-crond /usr/local/bin/go-crond
RUN chmod ug+x /usr/local/bin/go-crond
# ========================================================================================================

# Add a job user
ARG uid=1001
ARG user=pay
RUN useradd -U -ms /bin/bash -u $uid $user \
    && usermod -a -G root $user

ENV HOME=/ftp-poller

RUN mkdir $HOME && chmod 755 $HOME

WORKDIR $HOME


ARG APP_ENV \
  # Needed for fixing permissions of files created by Docker:
  UID=1000 \
  GID=1000

ENV APP_ENV=${APP_ENV} \
  # python:
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PYTHONDONTWRITEBYTECODE=1 \
  # pip:
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_DEFAULT_TIMEOUT=100 \
  PIP_ROOT_USER_ACTION=ignore \
  # poetry:
  POETRY_VERSION=2.3.2 \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/var/cache/pypoetry' \
  POETRY_HOME='/usr/local'

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

RUN apt-get update \
  && apt-get install --no-install-recommends -y \
    bash \
    brotli \
    build-essential \
    curl \
    gettext \
    git \
    libpq-dev \
    wait-for-it \
  && curl -sSL 'https://install.python-poetry.org' | python - \
  && poetry --version \
  # Cleaning cache:
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Copy only requirements, to cache them in docker layer
COPY --chown=pay:pay ./poetry.lock ./pyproject.toml .

# Project initialization:
RUN --mount=type=cache,target="$POETRY_CACHE_DIR" \
  echo "$APP_ENV" \
  && poetry version \
  && poetry run pip install -U pip \
  && poetry install \
    $(if [ -z ${APP_ENV+x} ] | [ "$APP_ENV" = 'production' ]; then echo '--only main'; fi) \
    --no-interaction --no-ansi

COPY . .


# Set ownership and permissions
# Set scripts as executable (make files and python files do not have to be marked)
# Make /etc/passwd writable for the root group so an entry can be created for an OpenShift assigned user account.
RUN chown -R $user:root $HOME \
    && chmod -R ug+rw $HOME \
    && chmod ug+x $HOME/*.sh \
    && chmod g+rw /etc/passwd \
    && chmod g-w $HOME/cron/crontab

USER $user
ENTRYPOINT ["bash", "docker-entrypoint.sh"]
