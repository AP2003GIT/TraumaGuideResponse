# Architecture decisions

## Why three services?

### Gateway service

Owns the public API, CORS, request IDs, service orchestration, and downstream
failure handling.

### Safety service

Owns deterministic emergency phrase checks, structured Gemini classification,
risk levels, and controlled high-risk responses.

### Chat service

Owns the support prompt, conversation history conversion, and normal Gemini
response generation. It rejects high and immediate-risk requests.

## Safety invariant

The chat service must never be called before safety classification succeeds.

## Failure behavior

If the safety service is unavailable, the gateway fails closed with HTTP 503.
It does not call the chat service.

## Communication

Services use synchronous request-response semantics over asynchronous HTTP.
This is sufficient for the current latency-sensitive chat workflow.

## Future services

A RAG service and audit/analytics pipeline may be added only after there is a
clear need. Do not split services solely to increase the service count.
