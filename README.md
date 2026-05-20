# USGS Seismic Data Pipeline

A production-ready, object-oriented ETL pipeline that ingests real-time earthquake data from the **USGS Earthquake API**, stores it in **PostgreSQL**, and visualises it through a self-hosted **Metabase** dashboard. Pipeline failures trigger instant **Slack** alerts.

---

## Project Structure

```
usgs-data-pipeline/
│
├── src/                          # Application source (on PYTHONPATH)
│   └── pipeline/
│       ├── __init__.py           # Package exports
│       ├── interfaces.py         # PipelineStage + Notifier ABCs
│       ├── config.py             # PipelineConfig dataclass (env-var backed)
│       ├── alerts.py             # SlackNotifier implementation
│       └── stages/
│           ├── __init__.py
│           ├── extract.py        # USGSExtractor — API fetch + retry logic
│           ├── transform.py      # SeismicTransformer — validation + normalization
│           └── load.py           # PostgreSQLLoader — ORM schema + upsert
│
├── tests/                        # Pytest test suite
│   ├── test_extract.py
│   ├── test_transform.py
│   └── test_load.py
│
├── docker/
│   ├── Dockerfile                # Python 3.11-slim, cron, non-root user
│   └── crontab                   # Runs pipeline at 00:00, 06:00, 12:00, 18:00 UTC
│
├── main.py                       # SeismicPipeline orchestrator (entrypoint)
├── docker-compose.yml            # PostgreSQL + pipeline + Metabase stack
├── requirements.txt              # Pinned runtime dependencies
├── requirements-dev.txt          # Runtime + test dependencies
├── .env.example                  # Secret template — copy to .env, never commit .env
├── .dockerignore                 # Keeps .env and .git out of the Docker image
├── .gitignore
└── README.md
```

---

## Architecture

The system uses a decoupled **ETL (Extract → Transform → Load)** design. Every stage inherits from the `PipelineStage` abstract base class in `interfaces.py`, making each component independently testable and swappable (e.g., replace `PostgreSQLLoader` with `SnowflakeLoader`) without touching any other stage.

```
[ USGS Earthquake REST API ]
           │
           ▼  GeoJSON (features[])
┌───────────────────────┐
│    USGSExtractor      │  Retry with exponential backoff; JSON decode guard
│  stages/extract.py    │
└───────────────────────┘
           │
           ▼  Raw dict list
┌───────────────────────┐
│  SeismicTransformer   │  Null guards, type normalization, UTC timestamps
│  stages/transform.py  │
└───────────────────────┘
           │
           ▼  Cleaned records
┌───────────────────────┐
│  PostgreSQLLoader     │  Connection pool, upsert by PK, rollback on error
│  stages/load.py       │
└───────────────────────┘
           │
           ▼  SQL transaction
[ PostgreSQL — earthquake_events table ]
           │
           ▼
[ Metabase — map + analytics dashboard ]


On any stage failure:
           │
           ▼
[ SlackNotifier → Incoming Webhook → Engineering channel ]
```

The `SeismicPipeline` orchestrator in `main.py` composes all stages. Any unhandled exception is caught, routed through `SlackNotifier`, and then re-raised so the process exits non-zero (important for cron and container health signals).

---

## Key Design Decisions

| Concern | Approach | Rationale |
|---|---|---|
| **Abstraction** | `PipelineStage` ABC (`interfaces.py`) | Swap any stage without touching others |
| **Notifier contract** | `Notifier` ABC (`interfaces.py`) | `SlackNotifier` is replaceable with PagerDuty, email, etc. |
| **Resilience** | Exponential backoff in `USGSExtractor` | Tolerates transient USGS API blips without crashing |
| **Idempotency** | `session.merge()` upsert | Re-running never creates duplicate rows |
| **Session safety** | SQLAlchemy context manager (`with Session()`) | Guarantees rollback for any exception, not just `SQLAlchemyError` |
| **Config validation** | `__post_init__` + typed env helpers | Fails fast with a clear message on bad or missing env var values |
| **Secret hygiene** | All secrets in `.env`, loaded via `env_file:` | No credentials in committed files; `.env` is gitignored |
| **Alert safety** | `_sanitize()` in `SlackNotifier` | Strips connection strings before posting to Slack |
| **Least privilege** | Non-root `appuser` in Dockerfile | Container does not execute as root |
| **Reproducible builds** | Pinned image tags + `.dockerignore` | No silent dependency drift; `.env` never enters the image |
| **DDL separation** | `loader.setup()` called in `run()`, not `__init__` | DB-unavailable errors are caught and alerted like any other stage failure |

---

## Database Schema

Table: `earthquake_events`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (PK) | USGS event ID — the upsert key |
| `magnitude` | FLOAT | Richter scale (nullable for unassigned recent events) |
| `location` | TEXT | Human-readable region (e.g., "12km S of Volcano, Hawaii") |
| `timestamp_utc` | DATETIME (indexed) | UTC event time — indexed for fast time-range queries |
| `coordinates` | JSON | `{"longitude": X, "latitude": Y, "depth_km": Z}` |
| `status` | TEXT | USGS review status: `automatic` or `reviewed` |

---

## Quickstart

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose installed

### 1. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and set real values — at minimum `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `DATABASE_URL`. Add your Slack webhook URL to enable failure alerts (leave blank to disable).

> **Never commit `.env` to version control.** It is already listed in `.gitignore`.

### 2. Build and launch the full stack

```bash
docker-compose up --build
```

Services start in dependency order:

1. `postgres_db` — waits until `pg_isready` passes its health check
2. `data_pipeline` — cron daemon starts; **first pipeline run fires at the next 6-hour UTC boundary** (00:00, 06:00, 12:00, or 18:00)
3. `metabase` — BI dashboard starts after the DB is healthy

**To run the pipeline immediately** without waiting for cron:

```bash
docker exec usgs_pipeline_runner python /app/main.py
```

### 3. View pipeline logs

```bash
# Live container logs
docker logs -f usgs_pipeline_runner

# Cron output stream inside the container
docker exec usgs_pipeline_runner tail -f /var/log/cron.log
```

### 4. Tear down

```bash
docker-compose down          # Stops containers; data volumes persist
docker-compose down -v       # Also deletes pgdata and metabase_data volumes
```

---

## Connecting Metabase

1. Open **http://localhost:3000** and complete the onboarding wizard
2. When prompted to add a database:

| Field | Value |
|---|---|
| Database type | PostgreSQL |
| Host | `postgres_db` (Docker service name — **not** `localhost`) |
| Port | `5432` |
| Database name | Value of `POSTGRES_DB` from your `.env` |
| Username | Value of `POSTGRES_USER` from your `.env` |
| Password | Value of `POSTGRES_PASSWORD` from your `.env` |

3. Build an earthquake map:
   - **New → Question → earthquake_events**
   - Switch visualization to **Map**
   - Latitude field → `coordinates → latitude`
   - Longitude field → `coordinates → longitude`

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=src/pipeline
```

Test files cover:

| File | Tests |
|---|---|
| `tests/test_extract.py` | Successful fetch, retry on 5xx, `ConnectionError` after max retries |
| `tests/test_transform.py` | Valid records, missing `time`, short coordinates, `None` input |
| `tests/test_load.py` | Empty input skip, merge called, rollback on `SQLAlchemyError` |

---

## Running Locally Without Docker

```bash
pip install -r requirements-dev.txt

export DATABASE_URL="postgresql://user:password@localhost:5432/seismic_db"
export MIN_MAGNITUDE=2.5
export LOOKBACK_DAYS=1

PYTHONPATH=src python main.py
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Full PostgreSQL connection URI |
| `POSTGRES_USER` | Yes | — | PostgreSQL username (used by the DB container) |
| `POSTGRES_PASSWORD` | Yes | — | PostgreSQL password |
| `POSTGRES_DB` | Yes | — | PostgreSQL database name |
| `MIN_MAGNITUDE` | No | `2.5` | Minimum earthquake magnitude to ingest |
| `LOOKBACK_DAYS` | No | `1` | Days of history to pull per pipeline run |
| `SLACK_WEBHOOK_URL` | No | *(unset)* | Slack Incoming Webhook URL for failure alerts |

---

## Cron Schedule

The pipeline runs four times daily at UTC:

```
0 */6 * * *   python /app/main.py
```

Edit `docker/crontab` and rebuild the image to change the frequency.

> **Production scaling note:** Cron inside Docker is suitable for single-host deployments. For multi-instance or distributed deployments consider replacing it with an external scheduler: AWS EventBridge + Lambda, Kubernetes CronJob, Apache Airflow, or Prefect.

---

## Slack Alerts

Any stage failure (Schema Setup, Extraction, Transformation, or Loading) triggers a Slack message with the stage name, error type, and a sanitized error detail (connection strings are stripped before sending).

To test it manually: set an invalid `DATABASE_URL` in `.env`, restart, then run:

```bash
docker exec usgs_pipeline_runner python /app/main.py
```

---

## Known Limitations

- **No horizontal scaling:** The cron-in-Docker pattern will produce duplicate runs if multiple containers start simultaneously. Use an external orchestrator for horizontal scale.
- **Metabase JSON field mapping** for `coordinates` requires PostgreSQL with JSONB support (enabled by default on Postgres 12+) and Metabase v0.43+.
