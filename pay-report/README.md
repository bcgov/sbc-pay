# Pay Team Report Dashboard

A Streamlit application with multiple pages that allows users to generate reports and download data as CSV files.

## Purpose

This application was created as a stopgap solution for PowerBI. It enables non-technical staff to generate and download reports independently, eliminating the need for developers to repeatedly run reports on demand.

## Features

- **Streamlit Native Authentication**: User authentication using Streamlit's built-in OIDC support with Keycloak
- **Multi-page navigation**: Main dashboard and Analytics page
- **PostgreSQL integration**: Connect to your PostgreSQL database
- **CSV download**: Export generated reports as CSV files

## Setup

### 1. Install UV (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or using pip:
```bash
pip install uv
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Configure Streamlit Secrets

Create a `.streamlit/secrets.toml` file from the example:

```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` with your actual configuration values. See `.streamlit/secrets.toml.example` for the required structure.

### 4. Run the Application

Using UV:
```bash
uv run streamlit run app.py
```

Or using standard Python:

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`.

## Running Tests

Install test dependencies:

```bash
uv sync --extra dev
```

Run the tests:

```bash
uv run pytest
```

The tests verify that:
- `enforce_auth()` correctly handles authentication and role checks
- All pages in pages/*.py import from src (which enforces auth)

## Linting

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and code formatting.

Install dev dependencies:
```bash
uv sync --extra dev
```

Run the linter:
```bash
uv run ruff check .
```

Format code:
```bash
uv run ruff format .
```

Check and format in one command:
```bash
uv run ruff check . --fix
uv run ruff format .
```

## Docker Setup

### Build the Docker Image

```bash
docker build -t pay-report .
```

### Run with Docker

Mount your `.streamlit/secrets.toml` file:

```bash
docker run -p 8501:8501 \
  -v $(pwd)/.streamlit/secrets.toml:/app/.streamlit/secrets.toml:ro \
  pay-report
```

**Note**: Make sure your `.streamlit/secrets.toml` file is configured with the correct values before running the container.

The application will be available at `http://localhost:8501`.

## Notes

- Make sure your PostgreSQL database is running and accessible
- Make sure your Keycloak server is running and accessible
- The application requires authentication before accessing any pages
- Authentication is handled automatically using Streamlit's native authentication
- Each page maintains its own session state for report data


