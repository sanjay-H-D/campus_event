# Campus Event Ticketing Engine

A secure multi-college event management and ticket booking platform built with vanilla HTML/CSS/JavaScript, FastAPI, SQLAlchemy and SQLite.

## Windows installation

1. Install Python 3.11 or newer and open this folder in VS Code.
2. Create and activate a virtual environment in PowerShell:

   ```powershell
   py -m venv .venv
   Set-ExecutionPolicy -Scope Process Bypass
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   py -m pip install -r requirements.txt
   ```

4. Configure a secret. Copy `.env.example` to `.env` and replace `SECRET_KEY` with a long random value. The database defaults to `campus_event_engine.db`.
5. Start the application:

   ```powershell
   py -m uvicorn backend.main:app --reload
   ```

6. Open `http://127.0.0.1:8000`. The frontend is served by FastAPI, so no separate frontend server is required.

## User flows

The initial page shows only the four authentication options. Admin registration creates or reuses a college; the authenticated admin can then manage only that college's events. Participant registration stores the participant's college name separately and never creates an organizing college.

Participants can browse registered colleges, search/filter actual upcoming events, book once, receive a booking reference, and view booking history. Deleted events are soft-deleted so existing booking history remains available.

Bearer JWT tokens are stored in browser localStorage by the demo frontend. This is convenient for a mini-project but has XSS exposure; production deployments should use secure HttpOnly SameSite cookies with CSRF protection and HTTPS.

## API

- `POST /api/admin/register`, `POST /api/admin/login`
- `POST /api/participant/register`, `POST /api/participant/login`
- `GET /api/admin/profile`
- `POST`, `GET`, `GET/{id}`, `PUT/{id}`, `DELETE/{id}` under `/api/admin/events`
- `GET /api/admin/events/{id}/participants`
- `GET /api/colleges`, `GET /api/events`, `GET /api/colleges/{id}/events`, `GET /api/events/{id}`
- `POST /api/events/{id}/book`
- `GET /api/participant/profile`, `GET /api/participant/bookings`

Private routes require `Authorization: Bearer <token>`. Admin event ownership is taken from the verified JWT and checked on every operation.

## Tests

Tests use a separate SQLite database and do not touch the development database:

```powershell
py -m pytest -q
```

The test suite covers registration, duplicate accounts, authentication, role protection, college ownership, soft deletion, booking references, duplicate bookings and capacity limits.

## Docker

```powershell
docker build -t campus-events .
docker run --env-file .env -p 8000:8000 campus-events
```
