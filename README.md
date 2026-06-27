# Address Book API

A production-grade RESTful API built with **FastAPI** for managing addresses.
Supports full CRUD, coordinate-based distance search using the Haversine formula,
fuzzy entity type matching, and paginated search results.

Built as part of a Python/FastAPI assessment.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| **FastAPI** | Web framework |
| **SQLAlchemy 2.0 (async)** | ORM |
| **aiosqlite** | Async SQLite driver |
| **Alembic** | Database migrations |
| **Pydantic v2** | Request validation and response serialization |
| **pydantic-settings** | Environment variable management |
| **uv** | Package manager |
| **difflib** | Fuzzy entity type matching (stdlib, no extra dependency) |

---

## Project Structure

```
address_book/
├── app/
│   ├── main.py                   # app factory, middleware, routers
│   ├── api/
│   │   ├── deps.py               # dependency injection (db → repo → service)
│   │   └── v1/
│   │       └── routes/
│   │           ├── addresses.py  # address route handlers
│   │           └── entity_types.py # entity type route handlers
│   ├── core/
│   │   ├── config.py             # settings via pydantic-settings + .env
│   │   └── database.py           # async engine, session factory, get_db()
│   ├── models/
│   │   └── address.py            # SQLAlchemy ORM models
│   ├── schemas/
│   │   └── address.py            # Pydantic schemas (Create, Update, Out, Search)
│   ├── repositories/
│   │   └── address_repo.py       # all SQL queries
│   └── services/
│       └── address_service.py    # business logic + Haversine search
├── alembic/
│   ├── env.py                    # Alembic config
│   └── versions/
│       ├── d68ec6d60d0d_init.py          # Migration 1: creates tables
│       └── xxxx_seed_entity_types.py     # Migration 2: seeds default types
├── alembic.ini                   # Alembic settings
├── pyproject.toml                # project dependencies
├── .env.example                  # example environment variables
└── README.md
```

---

## Architecture

The project follows a strict **layered architecture**:

```
Request
   ↓
Routes        → HTTP only (status codes, request parsing, response_model)
   ↓
Service       → Business rules (validation, fuzzy matching, distance filter)
   ↓
Repository    → SQL queries only (no rules, no HTTP)
   ↓
Database      → SQLite via async SQLAlchemy
```

Each layer has exactly one responsibility. Routes never touch SQL.
Services never touch HTTP. Repositories never contain business rules.

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed

Install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/address-book-api.git
cd address-book-api
```

### 2. Install dependencies

```bash
uv sync
```

This creates a virtual environment and installs all dependencies from `pyproject.toml`.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` if needed (defaults work out of the box for local development):

```env
APP_NAME="Address Book API"
DEBUG=True
DATABASE_URL="sqlite+aiosqlite:///./address_book.db"
DEFAULT_DISTANCE_UNIT="km"
```

---

## Database Setup (Migrations)

This project uses **Alembic** for database migrations.
Never run `create_all()` manually — always use migrations.

### Run all migrations (first time setup)

```bash
uv run alembic upgrade head
```

This runs two migrations in order:
1. **`init`** — creates the `addresses` and `entity_types` tables
2. **`seed_entity_types`** — inserts the 4 default entity types:
   `home`, `work`, `business`, `other`

### Check current migration status

```bash
uv run alembic current
```

---

## Running the App

### Development (with auto-reload)

```bash
uv run uvicorn app.main:app --reload
```

### Development on a custom port

```bash
uv run uvicorn app.main:app --reload --port 8080
```

### Production

```bash
uv run gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000
```

> For production, set `DEBUG=False` in your `.env`
> and restrict `CORS` origins in `main.py`.

---

## API Documentation

Once the app is running, open your browser:

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | **Swagger UI** — interactive API docs |
| http://localhost:8000/redoc | ReDoc — alternative API docs |
| http://localhost:8000/ | Health check |

---

## API Endpoints

### Addresses

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/addresses` | List all addresses |
| `GET` | `/api/v1/addresses/search` | Search with filters + pagination |
| `GET` | `/api/v1/addresses/{id}` | Get a single address |
| `POST` | `/api/v1/addresses` | Create a new address |
| `PATCH` | `/api/v1/addresses/{id}` | Partially update an address |
| `DELETE` | `/api/v1/addresses/{id}` | Delete an address |

### Entity Types

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/entity-types` | List all entity types |
| `POST` | `/api/v1/entity-types` | Create a custom entity type |
| `DELETE` | `/api/v1/entity-types/{id}` | Delete a custom entity type |

---

## Search Endpoint

`GET /api/v1/addresses/search`

The search endpoint supports distance-based filtering with optional name and type filters.

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `latitude` | ✅ Yes | — | Your location latitude (-90 to 90) |
| `longitude` | ✅ Yes | — | Your location longitude (-180 to 180) |
| `radius` | No | `5.0` | Search radius in km (or miles if configured) |
| `entity_name` | No | — | Partial name match — `john` matches `John Doe` |
| `entity_type` | No | — | Fuzzy type match — `resto` matches `restaurant` |
| `page` | No | `1` | Page number |
| `page_size` | No | `10` | Results per page (max 100) |

### Fuzzy entity type matching

The `entity_type` param uses a three-stage matching strategy:

1. **Exact match** — `restaurant` → `restaurant`
2. **Partial match** — `rest` → `restaurant`
3. **Fuzzy/typo match** — `restrunt` → `restaurant` (via `difflib.SequenceMatcher`, ≥60% similarity)

### Example requests

```bash
# Everything within default 5km
GET /api/v1/addresses/search?latitude=52.37&longitude=4.89

# Everything within 10km
GET /api/v1/addresses/search?latitude=52.37&longitude=4.89&radius=10

# Restaurants within 5km (fuzzy — 'resto' also works)
GET /api/v1/addresses/search?latitude=52.37&longitude=4.89&entity_type=restaurant

# Johns within 20km
GET /api/v1/addresses/search?latitude=52.37&longitude=4.89&entity_name=john&radius=20

# McDonalds-like restaurants within 10km, page 2
GET /api/v1/addresses/search?latitude=52.37&longitude=4.89&entity_name=mc&entity_type=restaurant&radius=10&page=2
```

### Example response

```json
{
    "total": 24,
    "page": 1,
    "page_size": 10,
    "pages": 3,
    "results": [
        {
            "id": 1,
            "entity_name": "Pasta House",
            "entity_type": {
                "id": 5,
                "name": "restaurant",
                "is_default": false
            },
            "street": "Dam 1",
            "city": "Amsterdam",
            "country": "NL",
            "latitude": 52.373,
            "longitude": 4.893,
            "state": null,
            "postal_code": "1012JS",
            "secondary_address": null
        }
    ]
}
```

---

## Default Entity Types

These are seeded automatically by the migration and **cannot be deleted**:

| ID | Name | is_default |
|----|------|-----------|
| 1 | home | true |
| 2 | work | true |
| 3 | business | true |
| 4 | other | true |

To add custom types (e.g. `restaurant`, `gym`, `hotel`):

```bash
POST /api/v1/entity-types
{ "name": "restaurant" }
```

Use the returned `id` as `entity_type_id` when creating an address.

---

## Distance Calculation

This API uses the **Haversine formula** to calculate real-world distances between coordinates.

**Why Haversine and not straight-line distance?**

Earth is a sphere. Treating latitude/longitude as flat X/Y coordinates introduces
significant error at larger distances or near the poles.
Haversine accounts for Earth's curvature and gives accurate real-world distances.

**Why filter in Python and not SQL?**

SQLite has no native geospatial extension.
In a production setup with PostgreSQL + PostGIS, the distance filter
would be done directly in SQL using `ST_DWithin()` for better performance.

**Distance unit** is configured via `DEFAULT_DISTANCE_UNIT` in `.env`:
- `km` — kilometres (default)
- `miles` — miles

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `Address Book API` | Application name shown in Swagger |
| `DEBUG` | `False` | Enables SQL query logging and DEBUG log level |
| `DATABASE_URL` | `sqlite+aiosqlite:///./address_book.db` | Database connection string |
| `DEFAULT_DISTANCE_UNIT` | `km` | Distance unit for search (`km` or `miles`) |

---

## Complete Quick Start

```bash
# 1. clone
git clone https://github.com/your-username/address-book-api.git
cd address-book-api

# 2. install dependencies
uv sync

# 3. copy env file
cp .env.example .env

# 4. run migrations (creates tables + seeds default entity types)
uv run alembic upgrade head

# 5. start the app
uv run uvicorn app.main:app --reload

# 6. open Swagger UI
open http://localhost:8000/docs
```
