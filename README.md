# LogForge

A high-performance distributed logging system built with modern technologies for real-time log collection, processing, and analysis.

## Architecture

LogForge consists of 6 microservices working together:

- **Collector** - Receives and queues log entries via HTTP API
- **Processor** - Processes logs from queue and stores in ClickHouse
- **API** - FastAPI backend for querying and retrieving logs
- **Frontend** - React dashboard for log visualization and filtering
- **ClickHouse** - High-performance columnar database for log storage
- **Redis** - Message queue for reliable log processing

## Features

- Real-time log ingestion and processing
- High-performance analytics with ClickHouse
- Interactive web dashboard with filtering and charts
- Anomaly detection capabilities
- Docker containerized deployment
- Scalable microservices architecture

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.8+ (for development)

### Run with Docker

```bash
# Clone the repository
git clone https://github.com/INFINIX2004/LogForge.git
cd LogForge

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### Access Points

- **Frontend Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Log Collector**: http://localhost:8080
- **ClickHouse**: http://localhost:8123

## API Usage

### Send Logs
```bash
curl -X POST http://localhost:8080/logs \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2024-01-01T12:00:00Z",
    "level": "INFO",
    "message": "Application started",
    "service": "web-server"
  }'
```

### Query Logs
```bash
curl "http://localhost:8000/logs?limit=100&level=ERROR"
```

## Development

### Local Setup
```bash
# Install dependencies for each service
cd collector && pip install -r requirements.txt
cd ../processor && pip install -r requirements.txt
cd ../api && pip install -r requirements.txt
cd ../anomaly_detector && pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
npm run dev
```

### Generate Test Data
```bash
python scripts/generate_logs.py
```

## Services

### Collector (Port 8080)
- Receives HTTP POST requests with log data
- Validates and queues logs in Redis
- Built with Python/FastAPI

### Processor
- Consumes logs from Redis queue
- Processes and stores in ClickHouse
- Handles batch processing for performance

### API (Port 8000)
- FastAPI backend for log queries
- Supports filtering by time, level, service
- Provides aggregation endpoints

### Frontend (Port 3000)
- React dashboard with Vite
- Real-time log visualization
- Interactive filtering and charts
- Built with Recharts for analytics

## Configuration

Environment variables can be configured in `docker-compose.yml`:

- `REDIS_URL` - Redis connection string
- `CLICKHOUSE_HOST` - ClickHouse server host
- `CLICKHOUSE_PORT` - ClickHouse server port

## License

MIT License
