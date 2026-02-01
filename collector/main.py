from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import redis.asyncio as redis
import json
import os

app = FastAPI()

# Redis connection
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

class LogEntry(BaseModel):
    level: str
    service: str
    message: str
    trace_id: str = None
    user_id: str = None
    metadata: dict = {}

@app.post("/logs")
async def ingest_log(log: LogEntry):
    # Add timestamp and host
    enriched_log = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": log.level.upper(),
        "service": log.service,
        "message": log.message,
        "trace_id": log.trace_id,
        "user_id": log.user_id,
        "host": "collector-01",  # Could be dynamic
        "environment": os.getenv('ENVIRONMENT', 'dev'),
        "metadata": log.metadata
    }
    
    # Push to Redis Stream
    await redis_client.xadd(
        'logs_stream',
        {'data': json.dumps(enriched_log)},
        maxlen=100000  # Keep last 100K messages
    )
    
    return {"status": "ok"}

@app.get("/health")
async def health():
    try:
        await redis_client.ping()
        return {"status": "healthy", "redis": "ok"}
    except:
        return {"status": "unhealthy", "redis": "down"}