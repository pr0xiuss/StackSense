# StackSense

StackSense is an enterprise-oriented source-code intelligence platform for understanding software structure and architecture.

The project is developed incrementally according to the StackSense Architecture Specification.

---

## Development Setup

### Prerequisites

Make sure the following are installed:

- Git
- Python 3.14+
- Docker
- Docker Compose

Verify the installations:

```bash
git --version
python --version
docker --version
docker compose version
```

---

### Backend

## 1. Activate the Virtual Environment


### Linux / macOS

```bash
source venv/bin/activate
```

### Windows

```powershell
venv\Scripts\activate
```

---

## 2. Install Dependencies

With the virtual environment activated:

```bash
pip install -r requirements.txt
```

---

## 3. Configure Environment Variables

Create your local environment file from the example:

```bash
cp .env.example .env
```

The `.env` file contains local development configuration and must not be committed.

Use the environment variable names and development configuration provided in `.env.example`.

---

## 4. Start PostgreSQL

Start the PostgreSQL container:

```bash
cd infra/docker
docker compose up -d
```

PostgreSQL is exposed locally on port `5434`.

The PostgreSQL container itself listens on port `5432`.

---

## 5. Run Database Migrations

Apply all Alembic migrations:

```bash
alembic upgrade head
```

Check the current migration:

```bash
alembic current
```

---

## 6. Run the FastAPI Application

Start the development server:

```bash
uvicorn backend.api.app:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

---

### Frontend

## 1. Handle Node MODULES
Delete node modules if package json or package-lock json changed

### Linux / macOS
```bash
rm -rf node_modules
```

### windows powershell
```bash
Remove-Item -Recurse -Force node_modules
```

## 2. Install dependencies
```bash
npm install
```

## 3. Start the server
```bash
npm run dev
```

The server runs on http://localhost:3000/


# Development Checks

Run these checks before creating a pull request on your feature branch.

## Requirements.txt in backend if new dependencies installed

```bash
rm requirements.txt
pip freeze > requirementx.txt
```

## Formatting

Run Black:

```bash
black .
```

## Linting

Run Ruff with automatic fixes:

```bash
ruff check . --fix
```

## Type Checking

Run mypy against the backend:

```bash
mypy backend
```

## Tests

Run the complete test suite:

```bash
pytest
```

---


# Database

StackSense uses PostgreSQL for local development.

PostgreSQL is provided through Docker Compose.

The local PostgreSQL port is:

```text
5434
```

The PostgreSQL container uses:

```text
5432
```

Docker port mapping:

```text
5434:5432
```

Acess DB using docker
```bash
docker exec -it stacksense-postgres psql -U postgres -d stacksense
```

---

# Environment Variables

The repository contains:

```text
.env.example
```

as the template for local environment configuration.

Create the local configuration with:

```bash
cp .env.example .env
```

Never commit `.env`.

When adding a new environment variable:

1. Add it to `.env.example`.
2. Document its purpose.
3. Provide a safe development/example value.
4. Never commit credentials or other secrets.

---