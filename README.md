# TraumaGuideResponse

TraumaGuideResponse is a safety-aware AI web application that provides general emotional support and psychoeducation.

The application uses the Gemini API to generate supportive responses while a separate safety service first evaluates every message for possible risk. Messages classified as high or immediate risk bypass normal AI generation and receive a controlled safety response instead.

> This project is not a therapist, diagnostic tool, medical service, or emergency service.

## Architecture

The project follows a microservices architecture:

```text
React Frontend
      |
      v
API Gateway
   |       |
   v       v
Safety   Chat
Service  Service
   \       /
    Gemini API
```

### Frontend

The React frontend provides the chat interface and automatically sends recent conversation history with every new message.

### Gateway Service

The gateway is the public backend entry point. It:

* receives requests from the frontend;
* sends every message to the safety service;
* forwards standard and elevated-risk messages to the chat service;
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
* follows strict instructions not to diagnose, prescribe medication, or replace professional care.

## Technology Stack

* React
* TypeScript
* Vite
* Python
* FastAPI
* Gemini API
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

Open the frontend:

```text
http://localhost:5173
```

Stop the application:

```bash
docker compose down
```

## Current Features

* AI-powered emotional-support chat
* Multi-turn conversation history
* Structured risk classification
* Controlled high-risk response routing
* Separate gateway, safety, and chat services
* Dockerized development environment
* Health checks for backend services
* Responsive React interface

## Important Notice

TraumaGuideResponse is currently an MVP created for learning and portfolio purposes.

It should not be used as a replacement for professional mental-health care, emergency services, diagnosis, or treatment.
