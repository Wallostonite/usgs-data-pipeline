# Execution Guide

Complete walkthrough for setting up and running the USGS Seismic Data Pipeline from scratch.

---

## Table of Contents

1. [System Prerequisites](#1-system-prerequisites)
2. [Project Setup](#2-project-setup)
3. [Environment Configuration](#3-environment-configuration)
4. [Option A — Run with Docker (Recommended)](#4-option-a--run-with-docker-recommended)
5. [Option B — Run Locally Without Docker](#5-option-b--run-locally-without-docker)
6. [Run the Test Suite](#6-run-the-test-suite)
7. [Verify Data in PostgreSQL](#7-verify-data-in-postgresql)
8. [Use the Metabase Dashboard](#8-use-the-metabase-dashboard)
9. [Cron Schedule & Manual Triggers](#9-cron-schedule--manual-triggers)
10. [Slack Alert Setup](#10-slack-alert-setup)
11. [Stopping & Cleaning Up](#11-stopping--cleaning-up)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. System Prerequisites

Check that each tool is installed before continuing.

### Python 3.11+

```bash
python3 --version
# Expected: Python 3.11.x or higher
```

If not installed → https://www.python.org/downloads/

### Docker Engine

```bash
docker --version
# Expected: Docker version 24.x.x or higher
```

If not installed → https://docs.docker.com/get-docker/

### Docker Compose (V2)

```bash
docker compose version
# Expected: Docker Compose version v2.x.x
```

> Docker Compose V2 ships with Docker Desktop. If you see `docker-compose` (with a hyphen) only, you have V1 — upgrade Docker Desktop to get V2.

### Git

```bash
git --version
# Expected: git version 2.x.x
```

---

## 2. Project Setup

### Step 1 — Navigate to the project folder

```bash
cd ~/usgs-data-pipeline
```

### Step 2 — Confirm the directory structure looks correct

```bash
find . -not -path './.git/*' -not -path './__pycache__/*' | sort
```

You should see:

```
.
├── .dockerignore
├── .env.example
├── .gitignore
├── README.md
├── EXECUTION_GUIDE.md
├── docker/
│   ├── Dockerfile
│   └── crontab
├── docker-compose.yml
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── src/
│   └── pipeline/
│       ├── __init__.py
│       ├── alerts.py
│       ├── config.py
│       ├── interfaces.py
│       └── stages/
│           ├── __init__.py
│           ├── extract.py
│           ├── load.py
│           └── transform.py
└── tests/
    ├── test_extract.py
    ├── test_load.py
    └── test_transform.py
```

---

## 3. Environment Configuration

The pipeline reads **all secrets from a `.env` file**. Nothing is hardcoded.

### Step 1 — Copy the template

```bash
cp .env.example .env
```

### Step 2 — Edit `.env` with your values

Open `.env` in any text editor:

```bash
nano .env        # or: code .env / vim .env
```

Fill in every line:

```dotenv
# PostgreSQL credentials
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=your_strong_password_here   # <-- change this
POSTGRES_DB=seismic_db

# Must match the credentials above.
# Use 'postgres_db' as the hostname (Docker service name, not localhost).
DATABASE_URL=postgresql://postgres_user:your_strong_password_here@postgres_db:5432/seismic_db

# Pipeline tunables (defaults are fine for a first run)
MIN_MAGNITUDE=2.5
LOOKBACK_DAYS=1

# Leave blank to disable Slack alerts (fill in Section 10 when ready)
SLACK_WEBHOOK_URL=
```

Save and close the file.

### Step 3 — Verify `.env` is gitignored

```bash
git status
# .env must NOT appear in the output.
# If it does, run: echo ".env" >> .gitignore
```

---

## 4. Option A — Run with Docker (Recommended)

This spins up **PostgreSQL + the pipeline + Metabase** as three isolated containers.

### Step 1 — Build the Docker image

```bash
docker compose build
```

Expected output ends with:

```
=> => writing image sha256:...
=> => naming to docker.io/library/usgs-data-pipeline-data_pipeline
```

### Step 2 — Start all services

```bash
docker compose up -d
```

The `-d` flag runs everything in the background.

### Step 3 — Confirm all containers are running

```bash
docker compose ps
```

Expected:

```
NAME                        STATUS          PORTS
usgs_postgres_container     Up (healthy)    127.0.0.1:5432->5432/tcp
usgs_pipeline_runner        Up              -
usgs_metabase_dashboard     Up              0.0.0.0:3000->3000/tcp
```

> The pipeline container status will show **Up** (the cron daemon is running). The pipeline script itself fires on schedule, not continuously.

### Step 4 — Trigger the first pipeline run manually

The cron job fires at 00:00, 06:00, 12:00, and 18:00 UTC. Don't wait — run it now:

```bash
docker exec usgs_pipeline_runner python /app/main.py
```

### Step 5 — Watch the live logs

```bash
docker logs -f usgs_pipeline_runner
```

A successful run looks like this:

```
2024-01-15 10:00:01 - USGSPipeline.Orchestrator - INFO - === PIPELINE BATCH EXECUTION STARTED ===
2024-01-15 10:00:01 - USGSPipeline.Loader      - INFO - Database schema verified.
2024-01-15 10:00:02 - USGSPipeline.Extractor   - INFO - Extracting USGS data from 2024-01-14T... to 2024-01-15T...
2024-01-15 10:00:03 - USGSPipeline.Extractor   - INFO - Extraction successful — 87 records retrieved.
2024-01-15 10:00:03 - USGSPipeline.Transformer - INFO - Transforming 87 raw records...
2024-01-15 10:00:03 - USGSPipeline.Transformer - INFO - Transformation complete — 87 valid records ready.
2024-01-15 10:00:03 - USGSPipeline.Loader      - INFO - Opening transaction for 87 records...
2024-01-15 10:00:03 - USGSPipeline.Loader      - INFO - Transaction committed successfully.
2024-01-15 10:00:03 - USGSPipeline.Orchestrator- INFO - === PIPELINE BATCH EXECUTION COMPLETED SUCCESSFULLY ===
2024-01-15 10:00:03 - USGSPipeline.Orchestrator- INFO - Total elapsed: 1.84s
```

Press `Ctrl + C` to stop following logs (containers keep running).

---

## 5. Option B — Run Locally Without Docker

Use this path for rapid development or debugging without containers.

### Step 1 — Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### Step 2 — Install runtime dependencies

```bash
pip install -r requirements.txt
```

### Step 3 — Set environment variables in your shell

```bash
export DATABASE_URL="postgresql://postgres_user:your_password@localhost:5432/seismic_db"
export MIN_MAGNITUDE=2.5
export LOOKBACK_DAYS=1
export SLACK_WEBHOOK_URL=""       # leave empty to skip Slack alerts
```

> If you don't have a local PostgreSQL running, start just the DB container:
> ```bash
> docker compose up -d postgres_db
> ```
> Then use `@localhost:5432` in your `DATABASE_URL` since port 5432 is bound to localhost.

### Step 4 — Run the pipeline

```bash
PYTHONPATH=src python main.py
```

Logs print directly to your terminal. You will see the same output as in Step 5 of Option A.

---

## 6. Run the Test Suite

### Step 1 — Install dev dependencies (includes pytest + mocking libraries)

```bash
pip install -r requirements-dev.txt
```

### Step 2 — Run all tests with coverage

```bash
PYTHONPATH=src pytest tests/ -v --cov=src/pipeline --cov-report=term-missing
```

Expected output:

```
tests/test_extract.py::test_execute_returns_features       PASSED
tests/test_extract.py::test_execute_retries_on_failure     PASSED
tests/test_extract.py::test_execute_raises_after_max_retries PASSED
tests/test_transform.py::test_valid_record_is_transformed  PASSED
tests/test_transform.py::test_record_missing_time_is_skipped PASSED
tests/test_transform.py::test_record_with_short_coords_is_skipped PASSED
tests/test_transform.py::test_none_input_returns_empty_list PASSED
tests/test_transform.py::test_empty_input_returns_empty_list PASSED
tests/test_load.py::test_execute_skips_empty_data         PASSED
tests/test_load.py::test_execute_merges_records            PASSED
tests/test_load.py::test_execute_rolls_back_on_error       PASSED

---------- coverage: src/pipeline ----------
Name                              Stmts   Miss  Cover
-----------------------------------------------------
src/pipeline/stages/extract.py      38      2    95%
src/pipeline/stages/transform.py    32      0   100%
src/pipeline/stages/load.py         35      3    91%
-----------------------------------------------------
TOTAL                              105      5    95%

11 passed in 2.34s
```

### Step 3 — Run a single test file (optional)

```bash
PYTHONPATH=src pytest tests/test_transform.py -v
```

---

## 7. Verify Data in PostgreSQL

### Option A — Using psql inside the container

```bash
docker exec -it usgs_postgres_container psql \
  -U postgres_user \
  -d seismic_db
```

Once inside the psql shell:

```sql
-- Count total records loaded
SELECT COUNT(*) FROM earthquake_events;

-- Preview the 5 most recent earthquakes
SELECT id, magnitude, location, timestamp_utc
FROM earthquake_events
ORDER BY timestamp_utc DESC
LIMIT 5;

-- Filter by magnitude
SELECT id, magnitude, location
FROM earthquake_events
WHERE magnitude >= 4.0
ORDER BY magnitude DESC;

-- Exit
\q
```

### Option B — Using a GUI tool (DBeaver, pgAdmin, TablePlus)

Use these connection details:

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `seismic_db` (or your `POSTGRES_DB` value) |
| Username | `postgres_user` (or your `POSTGRES_USER` value) |
| Password | Your `POSTGRES_PASSWORD` value |

---

## 8. Use the Metabase Dashboard

### Step 1 — Open Metabase

Go to **http://localhost:3000** in your browser.

> Metabase can take 60–90 seconds to start on first boot. If you see "loading", wait and refresh.

### Step 2 — Complete the onboarding wizard

- Set an admin email and password (store these — you'll need them to log back in)
- When asked **"Add your data"**, click **"I'll add my data later"** — you'll connect manually in the next step

### Step 3 — Connect to PostgreSQL

1. Click the gear icon (top-right) → **Admin settings** → **Databases** → **Add a database**
2. Fill in:

| Field | Value |
|---|---|
| Database type | PostgreSQL |
| Display name | USGS Seismic Data |
| Host | `postgres_db` |
| Port | `5432` |
| Database name | `seismic_db` |
| Username | `postgres_user` |
| Password | Your `POSTGRES_PASSWORD` |

3. Click **Save** — Metabase will sync the schema (takes ~10 seconds)

### Step 4 — Build an earthquake map

1. Click **+ New** → **Question**
2. Select **USGS Seismic Data** → **Earthquake Events**
3. Click the chart icon (bottom-left) and switch to **Map**
4. Click **Map options**:
   - Latitude field → `Coordinates → Latitude`
   - Longitude field → `Coordinates → Longitude`
5. Click **Visualize**

You will see all ingested earthquakes plotted on a world map with magnitude represented as dot size.

### Step 5 — Save and add to a dashboard

1. Click **Save** → name it "Earthquake Map"
2. Click **+ New** → **Dashboard** → **My Seismic Dashboard**
3. Click **Add a question** → select "Earthquake Map"
4. Drag to resize, then click **Save**

---

## 9. Cron Schedule & Manual Triggers

### Automatic schedule

The pipeline runs automatically inside the container at these UTC times every day:

| UTC Time | Local equivalent (GMT+1) |
|---|---|
| 00:00 | 01:00 AM |
| 06:00 | 07:00 AM |
| 12:00 | 01:00 PM |
| 18:00 | 07:00 PM |

### Trigger a run immediately

```bash
docker exec usgs_pipeline_runner python /app/main.py
```

### Change the cron frequency

Edit `docker/crontab`:

```bash
# Every hour
0 * * * *  . /etc/environment; /usr/local/bin/python /app/main.py >> /var/log/cron.log 2>&1

# Every 30 minutes
*/30 * * * *  . /etc/environment; /usr/local/bin/python /app/main.py >> /var/log/cron.log 2>&1

# Once a day at 3 AM UTC
0 3 * * *  . /etc/environment; /usr/local/bin/python /app/main.py >> /var/log/cron.log 2>&1
```

After editing, rebuild and restart:

```bash
docker compose build data_pipeline
docker compose up -d data_pipeline
```

### View cron execution history

```bash
docker exec usgs_pipeline_runner cat /var/log/cron.log
```

---

## 10. Slack Alert Setup

### Step 1 — Create a Slack Incoming Webhook

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Name it `USGS Pipeline Alerts`, select your workspace
3. In the left sidebar click **Incoming Webhooks** → toggle **Activate Incoming Webhooks** ON
4. Click **Add New Webhook to Workspace** → select your `#alerts` or `#engineering` channel
5. Copy the webhook URL — it looks like:
   ```
  https://slack.com
   ```

### Step 2 — Add the webhook to `.env`

```dotenv
  https://slack.com
```

### Step 3 — Restart the pipeline container to pick up the new value

```bash
docker compose up -d data_pipeline
```

### Step 4 — Test the alert

Temporarily break the database password to force a failure:

```bash
# In .env, change DATABASE_URL to use a wrong password
DATABASE_URL=postgresql://postgres_user:wrong_password@postgres_db:5432/seismic_db
```

Restart and run:

```bash
docker compose up -d data_pipeline
docker exec usgs_pipeline_runner python /app/main.py
```

You should receive a red alert in your Slack channel within seconds. Restore the correct password when done.

---

## 11. Stopping & Cleaning Up

### Stop all containers (keep data)

```bash
docker compose down
```

Volumes (`pgdata`, `metabase_data`) persist. Your earthquake data survives.

### Stop and delete all data volumes

```bash
docker compose down -v
```

This wipes the PostgreSQL database and Metabase configuration. Use only when you want a completely clean start.

### Remove built images

```bash
docker compose down --rmi local
```

### Deactivate the local virtual environment (Option B only)

```bash
deactivate
```

---

## 12. Troubleshooting

### Pipeline container exits immediately

**Symptom:** `docker compose ps` shows `data_pipeline` as `Exited`.

**Check the logs:**
```bash
docker logs usgs_pipeline_runner
```

Common causes:
- `DATABASE_URL` not set or wrong password — check `.env`
- PostgreSQL not yet healthy — wait 10 seconds and re-run `docker compose up -d`

---

### `DATABASE_URL environment variable must be set` error

**Symptom:** Error on pipeline startup before any ETL stage runs.

**Fix:** Ensure `.env` has a `DATABASE_URL` line and `docker compose` has picked it up:

```bash
docker compose config | grep DATABASE_URL
```

If it's missing, check that `env_file: .env` is present in `docker-compose.yml` and `.env` exists.

---

### `could not connect to server` from the pipeline

**Symptom:** Extraction or Schema Setup stage fails with a connection refused error.

**Fix:** The PostgreSQL container may still be initializing:

```bash
docker compose ps postgres_db
# Wait until STATUS shows: Up (healthy)
```

Then re-run manually:

```bash
docker exec usgs_pipeline_runner python /app/main.py
```

---

### Metabase shows `Connection refused` when adding the database

**Symptom:** Metabase cannot reach PostgreSQL.

**Cause:** You used `localhost` instead of `postgres_db` as the host.

**Fix:** Use the Docker service name `postgres_db` as the host — `localhost` refers to the Metabase container itself, not the database container.

---

### `ModuleNotFoundError: No module named 'pipeline'` (local run)

**Symptom:** Running `python main.py` locally fails with an import error.

**Fix:** Always prefix with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python main.py
```

---

### USGS API returns 0 records

**Symptom:** Pipeline completes but no data is loaded.

**Likely cause:** `MIN_MAGNITUDE` is set too high (e.g., `7.0`) or `LOOKBACK_DAYS=0`.

**Fix:** Lower the threshold and extend the lookback window:

```dotenv
MIN_MAGNITUDE=2.5
LOOKBACK_DAYS=7
```

Restart and re-run.

---

### Port 5432 already in use

**Symptom:** `docker compose up` fails with `bind: address already in use`.

**Cause:** A local PostgreSQL instance is already running on port 5432.

**Fix:** Stop the local PostgreSQL service:

```bash
# macOS (Homebrew)
brew services stop postgresql

# Linux (systemd)
sudo systemctl stop postgresql
```

Then retry `docker compose up -d`.

---

### Port 3000 already in use

**Symptom:** Metabase container fails to start.

**Fix:** Change the host port in `docker-compose.yml`:

```yaml
ports:
  - "3001:3000"   # Access Metabase at http://localhost:3001 instead
```

---

*For anything not covered here, run `docker logs <container_name>` — the structured log output will identify exactly which stage and line failed.*
