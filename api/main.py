# API
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import clickhouse_connect
import os
from contextlib import asynccontextmanager

app = FastAPI(title="Log System API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Create a new client for each request (thread-safe)
def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=int(os.getenv('CLICKHOUSE_PORT', 8123)),
        database='logs'
    )

@app.get("/api/logs")
def search_logs(
    service: str = None,
    level: str = None,
    start: str = None,
    end: str = None,
    limit: int = Query(100, le=1000),
    search: str = None
):
    # Create new client for this request
    ch_client = get_clickhouse_client()
    
    # Build WHERE clause
    conditions = []
    params = {}
    
    if service:
        conditions.append("service = %(service)s")
        params['service'] = service
    
    if level:
        conditions.append("level = %(level)s")
        params['level'] = level.upper()
    
    # Default to last 1 hour
    if not start:
        start = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    conditions.append("timestamp >= %(start)s")
    params['start'] = start
    
    if end:
        conditions.append("timestamp <= %(end)s")
        params['end'] = end
    
    if search:
        conditions.append("positionCaseInsensitive(message, %(search)s) > 0")
        params['search'] = search
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT 
            timestamp,
            level,
            service,
            host,
            message,
            trace_id,
            user_id
        FROM logs
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT {limit}
    """
    
    result = ch_client.query(query, parameters=params)
    
    # Convert to list of dicts
    logs = []
    for row in result.result_rows:
        logs.append({
            "timestamp": row[0].isoformat(),
            "level": row[1],
            "service": row[2],
            "host": row[3],
            "message": row[4],
            "trace_id": row[5],
            "user_id": row[6]
        })
    
    ch_client.close()
    return {
        "total": len(logs),
        "logs": logs
    }

@app.get("/api/stats")
def get_stats(
    service: str = None,
    hours: int = Query(24, le=168)
):
    # Create new client for this request
    ch_client = get_clickhouse_client()
    
    conditions = ["timestamp >= now() - INTERVAL %(hours)s HOUR"]
    params = {'hours': hours}
    
    if service:
        conditions.append("service = %(service)s")
        params['service'] = service
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
        SELECT
            toStartOfHour(timestamp) as hour,
            level,
            count() as count
        FROM logs
        WHERE {where_clause}
        GROUP BY hour, level
        ORDER BY hour DESC
    """
    
    result = ch_client.query(query, parameters=params)
    
    # Format for frontend
    stats = []
    for row in result.result_rows:
        stats.append({
            "hour": row[0].isoformat(),
            "level": row[1],
            "count": row[2]
        })
    
    ch_client.close()
    return {"stats": stats}

@app.get("/api/services")
def list_services():
    ch_client = get_clickhouse_client()
    result = ch_client.query("SELECT DISTINCT service FROM logs ORDER BY service")
    services = [row[0] for row in result.result_rows]
    ch_client.close()
    return {"services": services}

@app.get("/health")
def health():
    try:
        ch_client = get_clickhouse_client()
        ch_client.command("SELECT 1")
        ch_client.close()
        return {"status": "healthy", "clickhouse": "ok"}
    except:
        return {"status": "unhealthy", "clickhouse": "down"}

@app.get("/api/anomalies")
def get_anomalies(
    service: str = None,
    hours: int = Query(24, le=168),
    limit: int = Query(100, le=1000)
):
    ch_client = get_clickhouse_client()

    conditions = ["detected_at >= now() - INTERVAL %(hours)s HOUR"]
    params = {'hours': hours}

    if service:
        conditions.append("service = %(service)s")
        params['service'] = service

    where_clause = " AND ".join(conditions)

    result = ch_client.query(f"""
        SELECT
            detected_at, service, confidence, raw_score,
            error_count, warn_count, total_logs, error_ratio, unique_hosts
        FROM anomalies
        WHERE {where_clause}
        ORDER BY detected_at DESC
        LIMIT {limit}
    """, parameters=params)

    anomalies = []
    for row in result.result_rows:
        anomalies.append({
            "detected_at": row[0].isoformat(),
            "service":     row[1],
            "confidence":  row[2],
            "raw_score":   row[3],
            "error_count": row[4],
            "warn_count":  row[5],
            "total_logs":  row[6],
            "error_ratio": row[7],
            "unique_hosts":row[8]
        })

    ch_client.close()
    return {"total": len(anomalies), "anomalies": anomalies}


@app.get("/api/anomaly-stats")
def get_anomaly_stats(hours: int = Query(24, le=168)):

    ch_client = get_clickhouse_client()

    result = ch_client.query("""
        SELECT
            toStartOfHour(detected_at) AS hour,
            service,
            count()                    AS anomaly_count,
            avg(confidence)            AS avg_confidence
        FROM anomalies
        WHERE detected_at >= now() - INTERVAL %(hours)s HOUR
        GROUP BY hour, service
        ORDER BY hour DESC
    """, parameters={'hours': hours})

    stats = []
    for row in result.result_rows:
        stats.append({
            "hour":           row[0].isoformat(),
            "service":        row[1],
            "anomaly_count":  row[2],
            "avg_confidence": round(row[3], 1)
        })

    ch_client.close()
    return {"stats": stats}
