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

## 1. Clone the Repository

```bash
git clone https://github.com/pr0xiuss/StackSense.git
cd StackSense
```

---

## 2. Create the Virtual Environment

Create the project virtual environment:

```bash
python -m venv venv
```

Activate it.

### Linux / macOS

```bash
source venv/bin/activate
```

### Windows

```powershell
venv\Scripts\activate
```

---

## 3. Install Dependencies

With the virtual environment activated:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create your local environment file from the example:

```bash
cp .env.example .env
```

The `.env` file contains local development configuration and must not be committed.

Use the environment variable names and development configuration provided in `.env.example`.

---

## 5. Start PostgreSQL

Start the PostgreSQL container:

```bash
docker compose -f infra/docker/compose.yml up -d
```

Check the container status:

```bash
docker compose -f infra/docker/compose.yml ps
```

To view PostgreSQL logs:

```bash
docker compose -f infra/docker/compose.yml logs postgres
```

PostgreSQL is exposed locally on port `5434`.

The PostgreSQL container itself listens on port `5432`.

---

## 6. Run Database Migrations

Apply all Alembic migrations:

```bash
alembic upgrade head
```

Check the current migration:

```bash
alembic current
```

---

## 7. Run the FastAPI Application

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

# Development Checks

Run these checks before creating a pull request on your feature branch.

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

# Recommended Development Workflow

Activate the virtual environment:

```bash
source venv/bin/activate
```

Start PostgreSQL:

```bash
docker compose -f infra/docker/compose.yml up -d
```

Apply migrations:

```bash
alembic upgrade head
```

Run the application:

```bash
uvicorn backend.api.app:app --reload
```

Before committing changes:

```bash
black .
ruff check . --fix
mypy backend
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

# Git Branching

StackSense uses phase branches and feature branches.

The current phase branch is:

```text
p2-project-repository-platform
```

Create feature branches from the current phase branch:

```bash
git switch p2-project-repository-platform
git switch -c feature/<feature-name>
```

Feature branches are merged into the phase branch through pull requests.

The phase branch is merged into `main` only after the phase has been completed, verified, and frozen.

---

# Architecture

The authoritative architecture specification is:

```text
master.txt
```

Implementation decisions must follow the architecture specification.

The current ownership hierarchy is:

```text
User
  ↓
Project
  ↓
Repository
```

Project is the primary ownership, authorization, and isolation boundary.

---

# Project Status

Current phase:

**P2 — Project & Repository Platform**

Completed:

- P1 — Engineering Foundation
- P2 M1 — Project Domain Foundation
- P2 M2 — Project Access / Ownership Boundary

P2 M1 and M2 are frozen.

Development continues with the remaining P2 modules.