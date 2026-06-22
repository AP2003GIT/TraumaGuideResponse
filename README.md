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
The database keeps up to 10 saved chat sessions, and each session expires after
10 days by default.

## Current Features

* AI-powered emotional-support chat
* Multi-turn conversation history
* Structured risk classification
* Controlled high-risk response routing
* PostgreSQL-backed saved chat sessions
* Maximum of 10 saved chat sessions
* 10-day saved-chat retention window
* Clear-chat action that also deletes the saved conversation
* Saved chats screen for reopening previous conversations
* Settings panel with General display mode controls
* Light and dark display modes saved on the user's device
* Assistant message formatting for paragraphs, numbered lists, bullets, and
  bold text
* Separate gateway, safety, chat, and save services
* Dockerized development environment
* Health checks for backend services
* Responsive React interface

## Services

### Frontend

The React frontend provides the chat interface, restores the saved chat session,
and sends recent conversation history with every new message. The Settings
panel includes a General display mode control for switching between light and
dark mode. The Saved chats screen lists the currently retained conversations,
shows preview and expiry details, and lets the user reopen or delete saved
chats.

### Gateway Service

The gateway is the public backend entry point. It:

* receives requests from the frontend;
* sends every message to the safety service;
* forwards standard and elevated-risk messages to the chat service;
* saves completed exchanges through the save service;
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

The save service stores local chat sessions in PostgreSQL. It prunes older
sessions after `CHAT_MAX_SAVED_CHATS`, which defaults to 10, and expires saved
conversations after `CHAT_RETENTION_DAYS`, which defaults to 10.

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

The main tables are `conversations` and `messages`.

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

Open http://localhost:8000/docs and test `POST /api/chat`:

```json
{
  "session_id": "demo-session",
  "message": "I had a stressful day. Help me calm down.",
  "history": []
}
```

### Save service

Open http://localhost:8003/docs and test
`POST /internal/conversations/{session_id}/turns`.

Saved conversations are stored in PostgreSQL. Older sessions are pruned after
`CHAT_MAX_SAVED_CHATS`, which defaults to 10, and each saved session expires
after `CHAT_RETENTION_DAYS`, which defaults to 10.

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

## Important Notice

TraumaGuideResponse is currently an MVP created for learning and portfolio
purposes.

It should not be used as a replacement for professional mental-health care,
emergency services, diagnosis, or treatment.

Before real-world deployment, add:

* clinician-reviewed crisis copy and escalation rules;
* verified country-specific emergency resources;
* comprehensive multilingual safety evaluation;
* authentication and authorization for internal endpoints;
* rate limiting;
* secrets management;
* encrypted storage and explicit retention controls;
* observability without logging sensitive message bodies;
* independent security and privacy review;
* reviewed RAG sources and citation validation.
