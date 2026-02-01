import clickhouse_connect
import time
from collections import defaultdict
import os

ch_client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
    port=8123,
    database='logs'
)

# Store baseline (mean error count per service)
baselines = defaultdict(list)
MAX_HISTORY = 60  # Keep last 60 minutes

def detect_anomalies():
    print("Anomaly detector started...")
    
    while True:
        try:
            # Get error counts per service for last minute
            result = ch_client.query("""
                SELECT service, count() as error_count
                FROM logs
                WHERE level = 'ERROR'
                  AND timestamp >= now() - INTERVAL 1 MINUTE
                GROUP BY service
            """)
            
            for row in result.result_rows:
                service, current_count = row
                
                # Update baseline
                baselines[service].append(current_count)
                if len(baselines[service]) > MAX_HISTORY:
                    baselines[service].pop(0)
                
                # Need at least 10 data points
                if len(baselines[service]) < 10:
                    continue
                
                # Calculate z-score
                mean = sum(baselines[service]) / len(baselines[service])
                variance = sum((x - mean) ** 2 for x in baselines[service]) / len(baselines[service])
                std_dev = variance ** 0.5
                
                if std_dev == 0:
                    continue
                
                z_score = (current_count - mean) / std_dev
                
                # Alert if z-score > 3 (3 standard deviations)
                if z_score > 3:
                    alert(service, current_count, mean, z_score)
            
        except Exception as e:
            print(f"Error in anomaly detection: {e}")
        
        time.sleep(60)  # Check every minute

def alert(service, current, baseline, z_score):
    """Simple alert (just print for MVP)"""
    print(f"""
    ⚠️  ANOMALY DETECTED ⚠️
    Service: {service}
    Current error count: {current}/min
    Baseline: {baseline:.1f}/min
    Z-score: {z_score:.2f}
    """)
    
    # TODO: Send to Slack, email, etc.

if __name__ == '__main__':
    detect_anomalies()

"""
Run as separate container or background process

---

# 4. DATA FLOW & PROCESSING

## Complete Flow with Timings
```
1. Application generates log
   ↓ (immediate)

2. POST to Collector API
   ↓ (1-2ms - add metadata)

3. Push to Redis Stream
   ↓ (buffered, <1ms)

4. Processor reads (100 msgs at a time)
   ↓ (batch accumulates over 1-5 seconds)

5. Batch write to ClickHouse
   ↓ (100-500ms for 1000 rows)

6. Data available for queries
   Total latency: 2-7 seconds
```

## Why Redis Streams?

**Alternative 1: Direct to ClickHouse**
```
[Collector] → [ClickHouse]
```
**Problem**: ClickHouse slower with small writes; no buffering during spikes

**Alternative 2: Kafka**
```
[Collector] → [Kafka] → [Processor] → [ClickHouse]
```
**Better**: But complex setup (Zookeeper + brokers)

**Choice: Redis Streams**
```
[Collector] → [Redis] → [Processor] → [ClickHouse]

"""