# API Reference

## Base URLs

| Environment | Collector | Query API |
|-------------|-----------|-----------|
| Docker Compose | `http://localhost:8080` | `http://localhost:8000` |
| Kubernetes | `http://localhost/logs` | `http://localhost/api` |

---

## Collector

### `POST /logs`
Ingest a log entry.

```bash
curl -X POST http://localhost:8080/logs \
  -H "Content-Type: application/json" \
  -d '{"level":"ERROR","service":"payment-api","message":"Payment failed","trace_id":"abc123","user_id":"user-42"}'
```

**Fields:** `level` (ERROR/WARN/INFO), `service`, `message` — required. `trace_id`, `user_id` — optional.

### `GET /health`
Returns `{"status":"healthy","redis_connected":true}`

---

## Query API

### `GET /logs`
Query logs with filters.

**Params:** `service`, `level`, `start_time`, `end_time`, `search`, `limit` (default 100), `offset`

```bash
curl "http://localhost:8000/logs?service=payment-api&level=ERROR&limit=50"
```

### `GET /stats`
Aggregate statistics. **Params:** `service`, `start_time`, `end_time`

### `GET /api/anomalies`
Recent anomalies. **Params:** `service`, `hours` (default 1), `limit`

### `GET /api/anomaly-stats`
Per-service anomaly counts and average confidence.

### `GET /health`
Returns `{"status":"healthy"}`

---

## Swagger UI

- Docker Compose: http://localhost:8000/docs
- Kubernetes: http://localhost/api/docs
