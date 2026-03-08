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

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `level` | string | Yes | ERROR/WARN/INFO |
| `service` | string | Yes | Service name |
| `message` | string | Yes | Log message |
| `trace_id` | string | No | Trace identifier |
| `user_id` | string | No | User identifier |

### `GET /health`
Returns `{"status":"healthy","redis_connected":true}`

---

## Query API

### `GET /logs`
Query logs with filters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `service` | string | - | Filter by service name |
| `level` | string | - | Filter by log level |
| `start_time` | string | - | Start timestamp |
| `end_time` | string | - | End timestamp |
| `search` | string | - | Search in message |
| `limit` | integer | 100 | Max results |
| `offset` | integer | 0 | Pagination offset |

```bash
curl "http://localhost:8000/logs?service=payment-api&level=ERROR&limit=50"
```

### `GET /stats`
Aggregate statistics.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `service` | string | Filter by service name |
| `start_time` | string | Start timestamp |
| `end_time` | string | End timestamp |

### `GET /api/anomalies`
Recent anomalies.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `service` | string | - | Filter by service name |
| `hours` | integer | 1 | Look back hours |
| `limit` | integer | - | Max results |

### `GET /api/anomaly-stats`
Per-service anomaly counts and average confidence.

### `GET /health`
Returns `{"status":"healthy"}`

---

## Swagger UI

| Environment | URL |
|-------------|-----|
| Docker Compose | http://localhost:8000/docs |
| Kubernetes | http://localhost/api/docs |
