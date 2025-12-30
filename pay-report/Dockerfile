FROM python:3.12-bullseye AS builder

ARG VCS_REF="missing"
ARG BUILD_DATE="missing"

ENV VCS_REF=${VCS_REF}
ENV BUILD_DATE=${BUILD_DATE}
ENV PORT=8080

WORKDIR /code

LABEL org.label-schema.vcs-ref=${VCS_REF} \
  org.label-schema.build-date=${BUILD_DATE}

LABEL vendor="BCROS"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INPUT=1 \
    PATH="/root/.local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    # Cleaning cache:
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv --version \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && chmod +x /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./

RUN --mount=type=cache,target="/root/.cache/uv" \
  uv sync --no-default-groups --frozen

COPY . .

FROM python:3.12-slim-bullseye AS production

USER root

ARG UID=1000
ARG GID=1000

ENV PORT=8080 \
    PYTHONPATH="/code/src" \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    git \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

RUN groupadd -g "${GID}" -r web \
    && useradd -d '/code' -g web -l -r -u "${UID}" web \
    && mkdir -p /code \
    && chown web:web -R '/code'

WORKDIR /code

COPY --from=builder --chown=web:web /code /code

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

USER web

EXPOSE 8080

ENTRYPOINT ["uv", "run", "streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
