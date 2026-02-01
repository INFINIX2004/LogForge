import requests
import random
import time
from datetime import datetime

SERVICES = ['payment-api', 'auth-service', 'inventory', 'notification']
LEVELS = ['INFO', 'WARN', 'ERROR']
MESSAGES = {
    'ERROR': ['Connection timeout', 'Database error', 'Invalid request', 'Payment failed'],
    'WARN': ['High latency detected', 'Retry attempt', 'Cache miss', 'Rate limit approaching'],
    'INFO': ['Request processed', 'User logged in', 'Cache hit', 'Task completed']
}

print("Sending 100 logs/sec...")
for i in range(1000):
    level = random.choices(LEVELS, weights=[70, 20, 10])[0]
    service = random.choice(SERVICES)
    message = random.choice(MESSAGES[level])
    
    log = {
        'level': level,
        'service': service,
        'message': f"{message} - {i}",
        'trace_id': f"trace_{random.randint(10000, 99999)}",
        'user_id': f"user_{random.randint(100, 999)}"
    }
    
    try:
        requests.post('http://localhost:8080/logs', json=log, timeout=1)
    except:
        pass
    
    if i % 100 == 0:
        print(f"Sent {i} logs")
    
    time.sleep(0.01)  # 100 logs/sec

print("Done! Check http://localhost:3000")
