# CityScape-simulation-platform
Career Building Simulation Platform

**Cinis** is the permanent reference implementation: a late-19th-century-style
economic, demographic, and spatial simulation engine. This repo is the
system of record for its source code, database schema, and documentation.

## Stack

- **SQL Server** (SSMS) — authoritative persistent store
- **Python 3.11+** — simulation/application logic
- SQLAlchemy / pyodbc for persistence, pandas / openpyxl for analysis

## Repository layout

```
docs/            Architecture documents, ADRs, diagrams
excel/           Excel prototyping artifacts (design source of truth pre-SQL)
src/cinis/       Python package: config, database, models, repositories,
                 services, simulation, rules, events, analysis
database/        SQL Server schemas, migrations, procedures, seed data, tests
tests/           unit / integration / simulation / regression test suites
data/            reference and sample data (git-ignored where sensitive)
scripts/         one-off / dev-only utility scripts
notebooks/       exploratory analysis notebooks
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env              # then fill in your local SQL Server details
pytest
```

`.env` is git-ignored — never commit real connection details or credentials.
See `.env.example` for the required variables (Windows or SQL Server auth).

## Status

Milestone 1 — Cinis Data Foundation (in progress). See
`docs/architecture/08-roadmap` for the full milestone sequence.
