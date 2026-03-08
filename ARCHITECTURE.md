# Architecture

## System Overview

```
HTTP → Collector → Redis Streams → Processor → ClickHouse
                                                    ↓
                                          Anomaly Detector (Isolation Forest)
                                                    ↓
                                                Grafana
```

## Data Flow

```
1. Client sends HTTP POST → Collector validates schema
2. Collector writes to Redis Stream (XADD) — returns 200 immediately
3. Processor reads batches (XREADGROUP), bulk-inserts to ClickHouse, ACKs
4. Anomaly Detector queries ClickHouse every 60s, writes detections back
5. API serves queries from ClickHouse
6. Grafana reads directly from ClickHouse via native plugin
```

End-to-end latency: ~1–5 seconds. Anomaly detection latency: ~60–120 seconds.

---

## Key Design Decisions

**Redis Streams over Pub/Sub** — persistence and replay. If the processor crashes, messages aren't lost.

**Batch writes to ClickHouse** — 1000 logs or 5 seconds, whichever comes first. Reduces insert overhead significantly.

**Isolation Forest** — unsupervised ML, no labeled training data needed. Works out of the box on any service.

**Seasonal models** — separate Isolation Forest per service per hour-of-day (24 models per service). Prevents false positives at night when traffic is naturally low.

**Persistent models** — saved as `.joblib` files on a Docker volume / k8s PVC. Detector resumes without retraining on restart.

**ClickHouse TTL** — logs auto-expire after 30 days at the storage engine level. No cron jobs needed.

---

## Schema

```sql
-- logs table
timestamp DateTime64(3), level, service, host, environment,
message, trace_id, user_id
ORDER BY (service, level, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY

-- anomalies table  
detected_at DateTime64(3), service, confidence Float32,
raw_score Float32, error_count, warn_count, total_logs,
error_ratio Float32, unique_hosts
ORDER BY (service, detected_at)
TTL toDateTime(detected_at) + INTERVAL 30 DAY
```

---

## ML Pipeline

Features extracted per service per 5-minute window:

| Feature | Description |
|---------|-------------|
| `error_count` | Total ERROR level logs |
| `warn_count` | Total WARN level logs |
| `total_logs` | Total log volume |
| `error_ratio` | errors / total |
| `unique_hosts` | Number of distinct hosts |
| `error_burst` | Max errors in any 1-minute sub-window |
| `message_entropy` | Shannon entropy of log messages (drops when same error repeats) |

Contamination is dynamic: `clamp(cv * 0.05, 0.01, 0.05)` where cv = coefficient of variation of recent history.
