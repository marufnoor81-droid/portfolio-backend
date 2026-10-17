# Portfolio API

Django REST Framework backend for the portfolio and blog. It provides public content endpoints and owner-only management endpoints. The Postman collection is included as `postman_collection.json`.

## Requirements

- Python 3.10 or newer
- pip

## Run locally on Windows

From this repository's root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000/api/`; Django admin is at `http://127.0.0.1:8000/admin/`. The superuser can sign in to the portfolio frontend at `/login`. There is no public registration endpoint.

## Configuration

Set these values in `.env` for local development. Use a unique secret and production-grade settings when deploying.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django signing key |
| `DEBUG` | Development mode; set to `False` in production |
| `ALLOWED_HOSTS` | Comma-separated API hostnames |
| `CORS_ALLOWED_ORIGINS` | Exact frontend origin(s), e.g. `http://localhost:5173` |
| `DB_NAME` | SQLite database filename or path |

Never commit `.env`, `db.sqlite3`, uploaded media, or credentials. Production deployment needs HTTPS, a persistent database, explicit allowed hosts and CORS origins, and persistent media storage.

## API overview

All endpoints are under `/api/`. Public reads include profile, skills, experience, education, projects, posts, categories, and tags. Visitors can submit contact messages and comments and toggle post likes. An authenticated Django superuser manages content, approves comments, views contact messages, and uses the dashboard stats endpoint.

Import `postman_collection.json` into Postman to explore example API requests. Check the backend with:

```powershell
python manage.py check
python manage.py test
```
