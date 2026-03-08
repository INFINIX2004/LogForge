# 🔨 LogForge

A distributed log aggregation system with ML-powered anomaly detection. Built as a portfolio project to demonstrate real-world system design — async ingestion, batch processing, time-series storage, and unsupervised machine learning.

---

## Architecture

```
HTTP → Collector → Redis Streams → Processor → ClickHouse
                                                    ↓
                                          Anomaly Detector (Isolation Forest)
                                                    ↓
                                                Grafana
```

| Component | Role |
|-----------|------|
| Collector | FastAPI — validates and ingests logs via HTTP |
| Redis | Buffers logs using Streams (AOF persistence) |
| Processor | Batch-consumes from Redis, bulk-inserts to ClickHouse |
| ClickHouse | Columnar DB — fast analytics, 30-day TTL |
| Anomaly Detector | Isolation Forest — per-service, seasonal models |
| API | FastAPI — query logs, stats, anomalies |
| Grafana | Observability dashboard |

---

## Tech Stack

Python · FastAPI · Redis Streams · ClickHouse · scikit-learn · Grafana · Docker · Kubernetes (Kind)

---

## Getting Started

### Docker Compose
```bash
git clone https://github.com/INFINIX2004/LogForge.git
cd LogForge
docker-compose up --build
```

| Service | URL |
|---------|-----|
| Collector | http://localhost:8080 |
| API | http://localhost:8000 |
| Grafana | http://localhost:3001 (admin/admin) |

### Kubernetes
```bash
chmod +x k8s/deploy.sh
./k8s/deploy.sh
```

| Service | URL |
|---------|-----|
| Grafana | http://localhost/grafana |
| API | http://localhost/api |
| Collector | http://localhost/logs |

---

## Sending Logs

```bash
curl -X POST http://localhost:8080/logs \
  -H "Content-Type: application/json" \
  -d '{"level":"ERROR","service":"payment-api","message":"Payment failed"}'
```

---

## Anomaly Detection

The detector runs every 60 seconds, extracts 7 features per service (error count, error ratio, volume, burst score, message entropy, unique hosts, warn count), and uses Isolation Forest to flag anomalies. Models are persisted to disk and survive restarts.

**Simulation test results (6 scenarios, 100% detection rate):**

| Scenario | Detected | Cycles to Detect |
|----------|----------|-----------------|
| Error Spike | ✅ | 1 |
| Service Silence | ✅ | 2 |
| Error Ratio Explosion | ✅ | 1 |
| Volume Storm | ✅ | 1 |
| Slow Degradation | ✅ | 5 |
| Cascading Failure | ✅ | 1 |

```bash
# Run simulation tests
python scripts/simulation_tests.py
```

---

## Load Testing

```bash
python scripts/generate_logs.py
```

---

## 📚 Documentation

- **[Deployment Guide](DEPLOYMENT.md)** - Detailed deployment instructions for Docker Compose and Kubernetes
- **[Architecture Deep Dive](ARCHITECTURE.md)** - System design, component details, and design decisions
- **[API Documentation](API.md)** - Complete REST API reference with examples

---

## 🎓 What I Learned

- Designing event-driven pipelines with backpressure handling
- Unsupervised ML for anomaly detection without labeled data
- Why columnar databases (ClickHouse) outperform row-based DBs for analytics
- Kubernetes networking, persistent volumes, and health probes
- Debugging distributed systems across 7 containers
- Implementing batch processing for high-throughput systems
- Feature engineering for time-series anomaly detection
- Building production-ready observability pipelines

---


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙌 Author

Built by **[INFINIX2004](https://github.com/INFINIX2004)**

For learning, experimentation, and real-world system design practice.

---

## ⭐ Show Your Support

If you found this project helpful, please give it a star on GitHub!
