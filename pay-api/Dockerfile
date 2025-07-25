FROM python:3.12.2-slim-bullseye AS development_build

ARG VCS_REF="missing"
ARG BUILD_DATE="missing"

ENV VCS_REF=${VCS_REF}
ENV BUILD_DATE=${BUILD_DATE}
ENV PORT=8080

LABEL org.label-schema.vcs-ref=${VCS_REF} \
    org.label-schema.build-date=${BUILD_DATE}

USER root

LABEL maintainer="travissemple"
LABEL vendor="BCROS"

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
  POETRY_VERSION=2.1.3 \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/var/cache/pypoetry' \
  POETRY_HOME='/usr/local' \
  REQUESTS_CA_BUNDLE='/etc/ssl/certs/ca-certificates.crt'

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

RUN apt-get update && apt-get upgrade -y \
  && apt-get install --no-install-recommends -y \
    bash \
    brotli \
    build-essential \
    curl \
    gettext \
    git \
    libpq-dev \
    wait-for-it \
    ca-certificates \
    openssl \
  && curl -sSL 'https://install.python-poetry.org' | python - \
  && poetry --version

# Install SSL certificates for paybc.gov.bc.ca
COPY ./certs/root.cer /usr/local/share/ca-certificates/root.crt
COPY ./certs/inter.cer /usr/local/share/ca-certificates/inter.crt

RUN update-ca-certificates \
  && for cert in /usr/local/share/ca-certificates/root.crt /usr/local/share/ca-certificates/inter.crt; do \
      echo "Checking certificate: $cert"; \
      echo -n "Certificate expiration date: "; \
      openssl x509 -in "$cert" -noout -enddate | cut -d= -f2; \
      if ! openssl x509 -in "$cert" -noout -checkend 0 > /dev/null; then \
        echo "Certificate expired: $cert"; \
        exit 1; \
      fi; \
    done \
  # Cleaning cache:
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && apt-get clean -y && rm -rf /var/lib/apt/lists/*

WORKDIR /code

RUN groupadd -g "${GID}" -r web \
  && useradd -d '/code' -g web -l -r -u "${UID}" web \
  && chown web:web -R '/code'

# Copy only requirements, to cache them in docker layer
COPY --chown=web:web ./poetry.lock ./pyproject.toml /code/

COPY --chown=web:web ./src /code/src
COPY --chown=web:web ./README.md /code

# Project initialization:
RUN --mount=type=cache,target="$POETRY_CACHE_DIR" \
    --mount=type=cache,target=/root/.cache/pip \
  echo "$APP_ENV" \
  && poetry version \
  # Install deps:
  && poetry run pip install -U pip \
  && poetry install \
    $(if [ -z ${APP_ENV+x} ] | [ "$APP_ENV" = 'production' ]; then echo '--only main'; fi) \
    --no-interaction --no-ansi
  
# Running as non-root user:
USER web

# The following stage is only for production:
FROM development_build AS production_build
COPY --chown=web:web . /code

CMD gunicorn --bind 0.0.0.0:${PORT} --config /code/gunicorn_config.py wsgi:app
