# 🔨 LogForge

**LogForge** is a distributed log aggregation and analytics system built for high-throughput applications.  
It ingests logs via HTTP, buffers them safely using Redis Streams, processes them in batches, stores them efficiently in ClickHouse, and exposes real-time analytics through a web dashboard.

This project demonstrates real-world system design concepts such as asynchronous ingestion, batching, fault tolerance, and scalable analytics.

---

## ✨ Features

- 🚀 High-throughput log ingestion via HTTP
- 🧵 Redis Streams–based buffering (backpressure friendly)
- 📦 Batch processing for efficient storage
- 🏎️ ClickHouse for fast analytical queries
- 📊 Real-time dashboard with filtering & charts
- 🔍 Filter logs by service, level, message, and time range
- ⏱️ Automatic log retention using ClickHouse TTL
- 🐳 Fully Dockerized setup

---

## 🧠 Architecture Overview

```
Client / Services
|
v
HTTP Collector
|
v
Redis Streams
|
v
Processor
|
v
ClickHouse
|
v
API + Frontend
```

### Component Roles

| Component   | Responsibility |
|------------|----------------|
| Collector  | Receives logs over HTTP |
| Redis      | Buffers logs using streams |
| Processor  | Normalizes & batches logs |
| ClickHouse | Stores logs & runs analytics |
| API        | Queries logs & statistics |
| Frontend  | Displays logs and charts |

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI
- **Queue**: Redis Streams
- **Database**: ClickHouse
- **Frontend**: React (Vite)
- **Containerization**: Docker & Docker Compose

---

## 🚀 Getting Started

### Prerequisites
- Docker
- Docker Compose

### Clone the repository
```bash
git clone https://github.com/INFINIX2004/LogForge.git
cd LogForge
```

### Start the system

```bash
docker-compose up --build
```

Services will be available at:

* **Collector**: [http://localhost:8080](http://localhost:8080)
* **API**: [http://localhost:8000](http://localhost:8000)
* **Dashboard**: [http://localhost:3000](http://localhost:3000)

---

## 📤 Sending Logs

### Example log request

```bash
curl -X POST http://localhost:8080/logs \
  -H "Content-Type: application/json" \
  -d '{
    "level": "ERROR",
    "service": "payment-api",
    "message": "Payment failed",
    "trace_id": "trace-123",
    "user_id": "user-42"
  }'
```

---

## 🧪 Load Testing

A log generator is included to simulate real traffic.

```bash
python scripts/generate_logs.py
```

This can generate hundreds of logs per second and demonstrate system scalability.

---

## 📊 Dashboard Features

* Live log stream
* Error / Warning / Info charts
* Service-based filtering
* Full-text search on messages
* Time-range filtering

---

## 🗄️ Data Retention

Logs are automatically expired at the database level using ClickHouse TTL:

```sql
TTL toDateTime(timestamp) + INTERVAL 30 DAY
```

No cron jobs or manual cleanup required.

---

## 🔒 Design Decisions

* **Redis Streams** were chosen for durability and consumer control
* **Batch writes** reduce ClickHouse insert overhead
* **Strict schema** ensures data consistency
* **Processor normalization** prevents invalid data from reaching storage

---

## 📈 Performance Notes

* Handles 100+ logs/sec on a local setup
* Queries return in milliseconds for thousands of logs
* Designed to scale horizontally

---

## 🧩 Future Enhancements

* Alerting on error spikes
* Trace-ID based log correlation
* Authentication & multi-tenant support
* Grafana integration
* Horizontal processor scaling

---

## 🎓 Learning Outcomes

This project demonstrates:

* Distributed system design
* Event-driven architectures
* Data normalization & validation
* Debugging real production-style issues
* Observability pipelines

---

## 📄 License

MIT License

---

## 🙌 Author

Built by **INFINIX2004**
For learning, experimentation, and real-world system design practice.
