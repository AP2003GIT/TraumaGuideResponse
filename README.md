# TraumaGuideResponse

TraumaGuideResponse is a safety-aware AI web application that provides
general emotional support and psychoeducation.

The application uses the Gemini API to generate supportive responses while a
separate safety service first evaluates every message for possible risk.
Messages classified as high or immediate risk bypass normal AI generation and
receive a controlled safety response instead.

> This project is not a therapist, diagnostic tool, medical service, or
> emergency service.

## Architecture

The project follows a microservices architecture:

```text
React browser client
        |
        v
Gateway Service :8000
   |             |           |
   v             v           v
Safety :8001   Chat :8002   Save :8003
   |             |           |
   +---- Gemini--+           v
                         PostgreSQL :5432
```

The browser communicates only with the gateway. The gateway always calls the
safety service first. High or immediate-risk messages receive a controlled
safety response, while standard and elevated-risk messages are forwarded to the
chat service. Completed exchanges are stored by the save service in PostgreSQL.
Saved chat sessions are tied to the signed-in user account. The database keeps
up to 10 saved chat sessions per user, and each session expires after 10 days
by default.

## Current Features

* AI-powered emotional-support chat
* Sign up, login, and logout
* Local development password reset-code flow
* User profile editing for display name, email, and password
* Remember me checkbox for persistent local autologin
* Optional local developer login shortcut
* User-scoped saved chat history
* Multi-turn conversation history
* Structured risk classification
* Controlled high-risk response routing
* PostgreSQL-backed saved chat sessions
* Maximum of 10 saved chat sessions per user
* 10-day saved-chat retention window
* Clear-chat action that also deletes the saved conversation
* Saved chats sidebar with search and active chat highlighting
* Message timestamps, copy, retry, and regenerate controls
* Account export with scope and date filters
* Account-data deletion controls
* Tabbed Settings panel with General, Account, Privacy, Safety, and Admin
  sections
* Role-protected admin dashboard for service health and storage metrics
* Gateway rate limits for auth, chat, and admin requests
* Light and dark display modes saved on the user's device
* Copy confirmation feedback for message actions
* Crisis-resource panel with 988 call, text, and chat actions
* Assistant message formatting for paragraphs, numbered lists, bullets, and
  bold text
* Separate gateway, safety, chat, and save services
* Dockerized development environment
* Health checks for backend services
* Responsive React interface

## Services

### Frontend

The React frontend provides sign up and login, password reset, profile editing,
the chat interface, saved-chat restoration, and recent conversation history
with every new message. The Settings panel includes General display mode
controls, account logout, filtered saved-chat export, account-data deletion,
safety resources, and an internal admin dashboard. The saved-chat sidebar lists
the currently retained conversations for the signed-in user, supports search,
shows preview and expiry details, and lets the user reopen or delete saved
chats.

### Gateway Service

The gateway is the public backend entry point. It:

* receives requests from the frontend;
* issues signed bearer tokens after account registration or login;
* supports local password reset and profile updates;
* includes the user's role in issued bearer tokens;
* rate-limits auth, chat, and admin request bursts;
* protects chat and saved-chat endpoints;
* restricts the admin dashboard to users with the `admin` role;
* sends every message to the safety service;
* forwards standard and elevated-risk messages to the chat service;
* saves completed exchanges through the save service under the authenticated
  user;
* returns one unified response to the frontend.

### Safety Service

The safety service:

* performs basic deterministic safety checks;
* uses structured Gemini output to classify risk;
* returns one of four risk levels:
  * `standard`
  * `elevated`
  * `high`
  * `immediate`
* provides controlled responses for high and immediate-risk messages.

### Chat Service

The chat service:

* receives only standard and elevated-risk requests;
* sends conversation history to Gemini;
* generates supportive and context-aware responses;
* follows strict instructions not to diagnose, prescribe medication, or replace
  professional care.

### Save Service

The save service stores accounts and local chat sessions in PostgreSQL.
It runs SQL migrations at startup and records applied versions in
`schema_migrations`. Passwords are stored as salted PBKDF2 hashes. Password
reset codes are stored as hashes and expire after 30 minutes. Saved chats are
scoped to a user, older sessions are pruned after `CHAT_MAX_SAVED_CHATS`,
which defaults to 10, and saved conversations expire after
`CHAT_RETENTION_DAYS`, which defaults to 10.

## Technology Stack

* React
* TypeScript
* Vite
* Python
* FastAPI
* Gemini API
* PostgreSQL
* Docker
* Docker Compose
* Nginx
* HTTPX
* Pydantic

## Running the Project

Create a `.env` file from the included example:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Add your Gemini API key:

```env
GEMINI_API_KEY=your_api_key
```

For local development, you can also set a gateway token secret:

```env
AUTH_TOKEN_SECRET=replace-this-with-a-long-random-development-secret
```

Docker Compose enables the frontend developer login shortcut by default. To
hide it, set:

```env
VITE_ENABLE_DEV_LOGIN=false
```

The local developer account is treated as an admin by default. Override admin
users with:

```env
ADMIN_EMAILS=["you@example.com"]
```

Gateway limits can be tuned with:

```env
AUTH_RATE_LIMIT_PER_MINUTE=12
CHAT_RATE_LIMIT_PER_MINUTE=20
ADMIN_RATE_LIMIT_PER_MINUTE=30
```

Start the complete application:

```bash
docker compose up --build
```

Open:

* Frontend: http://localhost:5173
* Gateway Swagger: http://localhost:8000/docs
* Safety Swagger: http://localhost:8001/docs
* Chat Swagger: http://localhost:8002/docs
* Save Swagger: http://localhost:8003/docs
* PostgreSQL: localhost:5432

Stop the application:

```bash
docker compose down
```

## pgAdmin4 Connection

pgAdmin4 is the database admin UI. The database itself runs as the `postgres`
service in Docker Compose.

Register a new server in pgAdmin4 with:

* Host: `localhost`
* Port: `5432`
* Maintenance database: `emotional_support`
* Username: `support_app`
* Password: `support_app_dev_password`

The main tables are `users`, `password_reset_tokens`, `conversations`,
`messages`, and `schema_migrations`.

## Render Deployment

The Render blueprint in `render.yaml` defines two public services:

* `trauma-guide-gateway`, the FastAPI gateway API.
* `trauma-guide-frontend`, the React static site.

The gateway URL is an API URL. Seeing a response like this at `/` means the
backend is running correctly:

```json
{"service":"gateway-service","status":"running","docs":"/docs"}
```

Open `/docs` on the gateway URL for Swagger, or `/health` for the Render health
check. The browser UI should be opened from the frontend static-site URL, not
from the gateway URL.

If creating the services manually in Render, use these settings:

Gateway web service:

* Build command: `pip install -r requirements.txt`
* Start command: `cd gateway-service && gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
* Health check path: `/health`
* Environment variables: `AUTH_TOKEN_SECRET`, `SAFETY_SERVICE_URL`,
  `CHAT_SERVICE_URL`, and `SAVE_SERVICE_URL`

Frontend static site:

* Root directory: `frontend`
* Build command: `npm install && npm run build`
* Publish directory: `dist`
* Rewrite rule: `/*` to `/index.html`
* Environment variables:
  * `VITE_API_BASE_URL=https://traumaguideresponse.onrender.com`
  * `VITE_ENABLE_DEV_LOGIN=true`

For the full production app, deploy the safety, chat, and save services too, or
point the gateway environment variables at already-running instances of those
services. The local Docker Compose setup starts all microservices together.

## Test Each Service Independently

### Safety service

Open http://localhost:8001/docs and test `POST /internal/classify`:

```json
{
  "message": "I have felt overwhelmed for weeks and can barely function.",
  "history": []
}
```

### Chat service

Open http://localhost:8002/docs and test `POST /internal/generate`:

```json
{
  "message": "I had a stressful day. Help me calm down.",
  "history": [],
  "risk_level": "standard",
  "needs_professional_support": false
}
```

The chat service intentionally rejects `high` and `immediate` risk levels.

### Gateway

Open http://localhost:8000/docs and test `POST /api/chat`.

First create an account with `POST /api/auth/register` or sign in with
`POST /api/auth/login`, then use the returned bearer token in the `Authorize`
button.

```json
{
  "session_id": "demo-session",
  "message": "I had a stressful day. Help me calm down.",
  "history": []
}
```

### Save service

Open http://localhost:8003/docs and test
`POST /internal/users/{user_id}/conversations/{session_id}/turns`.

Saved conversations are stored in PostgreSQL. Older sessions are pruned after
`CHAT_MAX_SAVED_CHATS`, which defaults to 10 per user, and each saved session
expires after `CHAT_RETENTION_DAYS`, which defaults to 10.

## Manual PyCharm Development

Each Python service is an independent FastAPI application.

### 1. Safety service

```powershell
cd safety-service
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8001
```

### 2. Chat service

Open a second terminal:

```powershell
cd chat-service
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8002
```

### 3. Save service

Open a third terminal:

First make sure PostgreSQL is running and set a database URL:

```powershell
$env:DATABASE_URL = "postgresql://support_app:support_app_dev_password@127.0.0.1:5432/emotional_support"
```

```powershell
cd save-service
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --port 8003
```

### 4. Gateway service

Open a fourth terminal:

```powershell
cd gateway-service
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

### 5. React frontend

Open a fifth terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

## Run Tests

Run these from each service folder:

```powershell
pytest
```

The GitHub Actions workflow in `.github/workflows/python-app.yml` runs:

* Python 3.12 compile and pytest checks for each backend service;
* PostgreSQL-backed save-service tests;
* frontend `npm run build`;
* Docker Compose image builds.

## Important Notice

TraumaGuideResponse is currently an MVP created for learning and portfolio
purposes.

It should not be used as a replacement for professional mental-health care,
emergency services, diagnosis, or treatment.

Before real-world deployment, add:

* clinician-reviewed crisis copy and escalation rules;
* verified country-specific emergency resources;
* comprehensive multilingual safety evaluation;
* secrets management;
* encrypted storage and explicit retention controls;
* observability without logging sensitive message bodies;
* independent security and privacy review;
* reviewed RAG sources and citation validation.
