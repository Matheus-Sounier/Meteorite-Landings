# CI Configuration

The workflow reads PostgreSQL and Python settings from GitHub Actions repository variables. Add these under **Settings > Secrets and variables > Actions > Variables**:

- `CI_PYTHON_VERSION` (use `3.12`)
- `POSTGRES_IMAGE`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_CONTAINER_PORT`
- `POSTGRES_HEALTHCHECK_INTERVAL`
- `POSTGRES_HEALTHCHECK_TIMEOUT`
- `POSTGRES_HEALTHCHECK_RETRIES`

Add `POSTGRES_PASSWORD` under **Secrets**. The workflow uses it only for its temporary PostgreSQL service and test connection.

The workflow runs unit and PostgreSQL integration tests for pushes to `main` and pull requests targeting `main`.