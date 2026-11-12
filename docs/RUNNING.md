# Running

The short path is in the [README](../README.md): a virtual environment, `pip install -e ".[dev]"`, then `make run`. The commands below are the rest. They assume the virtual environment is active, so `python`, `pytest`, and `uvicorn` are the ones just installed.

`make run` does not read `.env`. The API key is `local-dev-key` unless you export `RO_API_KEY`. Docker Compose does read `.env`.

The page opens with the report date set to 21 October 2026. The API, if you omit `as_of`, uses the server's current date. On this file the open count and the dollar total stay 70 and $207,447.95 for any report date on or after 21 October 2026. Ages and buckets move. The screenshot and [RESULTS.md](RESULTS.md) are the 21 October 2026 buckets.

## Tests and lint

```bash
make test
make lint
```

`make test` is pytest. `make lint` is `ruff check` and `ruff format --check`.

## Call the API

```bash
curl -H "X-API-Key: local-dev-key" \
  "http://127.0.0.1:8000/api/v1/ro-aging?branch=Indianapolis&as_of=2026-10-21"
```

Indianapolis on that date is six bucket rows: 2, 3, 2, 1, 2, and 4 orders, totaling 14 orders and $35,097.92. The 0-7 row is 2 orders and $3,619.28.

## Regenerate the sample

```bash
python scripts/generate_sample_data.py
```

The seed is fixed at 21. Running it again reproduces `data/sample/repair_orders.csv`. Restart the API to load the file.

## Static snapshot

```bash
make demo
```

This writes `dist/ro-aging-snapshot.html`, one file with the stylesheet, the script, the fonts, and the API payloads for 21 October 2026. `dist/` is gitignored. Open the file directly. The date field is fixed, and the API-reference link is hidden, because the snapshot has no server.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Set `RO_API_KEY` in `.env` before starting. Compose passes that file into the container, and the key you set there is the one the page will ask for. The image is `python:3.12-slim`, listens on port 8000, and loads `data/sample/repair_orders.csv`. The compose file mounts `./data` read-only over that path.

## SQL Server

Run the scripts in order against the reporting database. Details and the one difference in date parsing are in [METHODOLOGY.md](METHODOLOGY.md).

```text
sql/01_staging.sql
sql/02_views.sql
sql/03_procedures.sql
```

```sql
EXEC dbo.usp_GetOpenROAging
    @Branch = 'Indianapolis',
    @AsOf = '2026-10-21';
```

The API in this repo will not pick up that database on its own. It reads the CSV through SQLite.
