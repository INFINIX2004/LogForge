# PROCESSOR

import redis
import clickhouse_connect
import json
import time
import os
from datetime import datetime

# Connections
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# Wait for ClickHouse to be ready
def wait_for_clickhouse(max_retries=30):
    for i in range(max_retries):
        try:
            print(f"Attempting to connect to ClickHouse (attempt {i+1}/{max_retries})...")
            client = clickhouse_connect.get_client(
                host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
                port=int(os.getenv('CLICKHOUSE_PORT', 8123)),
                database='logs'
            )
            # Verify the table actually exists before proceeding
            client.command("SELECT 1 FROM logs LIMIT 1")
            print("✓ Connected to ClickHouse and table verified!")
            return client
        except Exception as e:
            print(f"  Not ready yet: {e}")
            time.sleep(2)
    raise Exception("Could not connect to ClickHouse after 30 retries")
    
# Initialize with retry
ch_client = wait_for_clickhouse()

BATCH_SIZE = 1000
BATCH_TIMEOUT = 5  # seconds

def process_logs():
    batch = []
    last_flush = time.time()
    last_id = '0-0'
    
    print("Processor started, waiting for logs...")
    
    while True:
        try:
            # Read from Redis Stream
            messages = redis_client.xread(
                {'logs_stream': last_id},
                count=100,
                block=1000  # Wait 1 second for new messages
            )
            
            if not messages:
                # No new messages, check if we should flush
                if batch and (time.time() - last_flush) > BATCH_TIMEOUT:
                    flush_batch(batch)
                    batch = []
                    last_flush = time.time()
                continue
            
            for stream_name, stream_messages in messages:
                for msg_id, msg_data in stream_messages:
                    last_id = msg_id
                    
                    # Parse log
                    try:
                        log = json.loads(msg_data[b'data'].decode('utf-8'))
                        batch.append(prepare_row(log))
                    except Exception as e:
                        print(f"Error parsing log: {e}")
                        continue
                    
                    # Flush if batch is full
                    if len(batch) >= BATCH_SIZE:
                        flush_batch(batch)
                        batch = []
                        last_flush = time.time()
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)

def prepare_row(log):
    # --- Timestamp handling ---
    ts = log.get('timestamp')
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except Exception:
            ts = datetime.utcnow()
    elif ts is None:
        ts = datetime.utcnow()

    # --- String sanitization ---
    def safe_str(value, default=''):
        if value is None:
            return default
        return str(value)

    return (
        ts,
        safe_str(log.get('level'), 'INFO'),
        safe_str(log.get('service'), 'unknown'),
        safe_str(log.get('host'), 'unknown'),
        safe_str(log.get('environment'), 'dev'),
        safe_str(log.get('message'), ''),
        safe_str(log.get('trace_id'), ''),   # 🔥 FIX
        safe_str(log.get('user_id'), '')     # 🔥 FIX
    )

def flush_batch(batch):

    try:
        ch_client.insert(
            'logs',
            batch,
            column_names=['timestamp', 'level', 'service', 'host', 
                         'environment', 'message', 'trace_id', 'user_id']
        )
        print(f"✓ Flushed {len(batch)} logs to ClickHouse")
    except Exception as e:
        print(f"✗ Error writing to ClickHouse: {e}")

if __name__ == '__main__':
    process_logs()
