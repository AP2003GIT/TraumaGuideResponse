# Emotional Support Platform

A portfolio-oriented microservices application using:

- React + TypeScript + Vite
- FastAPI
- Gemini API
- HTTPX
- Docker and Docker Compose

## Architecture

```text
React browser client
        |
        v
Gateway Service :8000
   |             |
   v             v
Safety :8001   Chat :8002
   |             |
   +---- Gemini--+
```

The browser communicates only with the gateway.

The gateway always calls the safety service first. High or immediate-risk
messages bypass open-ended chat generation and receive a controlled response.
Standard and elevated messages are forwarded to the chat service.

## Preserve your existing project

This is a separate project. Do not delete your current working PyCharm project.
Keep its `main.py` as the monolithic prototype and open this folder in a new
PyCharm window.

## Prerequisites

### Docker route

- Docker Desktop
- A Gemini API key

### Manual route

- Python 3.11 or 3.12
- Node.js 20.19+ or 22.12+
- npm
- A Gemini API key

## Fastest start: Docker Compose

1. Copy `.env.example` to `.env`.

PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Put your real Gemini key in `.env`.

```env
GEMINI_API_KEY=your_real_key
```

3. Start the complete platform:

```powershell
docker compose up --build
```

4. Open:

- Frontend: http://localhost:5173
- Gateway Swagger: http://localhost:8000/docs
- Safety Swagger: http://localhost:8001/docs
- Chat Swagger: http://localhost:8002/docs

Stop everything:

```powershell
docker compose down
```

## Test each service independently

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
  "message": "I had a stressful day. Help me calm down.",
  "history": []
}
```

## Manual PyCharm development

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

### 3. Gateway service

Open a third terminal:

```powershell
cd gateway-service
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

### 4. React frontend

Open a fourth terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

## Run tests

Run these from each service folder:

```powershell
pytest
```

## Important limitations

This is a development and portfolio project, not an emergency service or
medical device.

Before real-world deployment, add:

- clinician-reviewed crisis copy and escalation rules;
- verified country-specific emergency resources;
- comprehensive multilingual safety evaluation;
- authentication and authorization for internal endpoints;
- rate limiting;
- secrets management;
- encrypted storage and explicit retention controls;
- observability without logging sensitive message bodies;
- independent security and privacy review;
- reviewed RAG sources and citation validation.
