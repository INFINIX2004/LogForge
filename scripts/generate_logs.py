import requests
import random
import time

COLLECTOR_URL = "http://localhost:8080/logs"

# ─────────────────────────────────────────────
# SERVICE PROFILES  (normal behaviour)
# Each service has its own realistic baseline
# ─────────────────────────────────────────────
SERVICE_PROFILES = {
    'payment-api': {
        'logs_per_batch': 15,           # ~15 logs per cycle (busy service)
        'level_weights': [80, 15, 5],   # 80% INFO, 15% WARN, 5% ERROR
        'messages': {
            'INFO':  ['Payment processed', 'Transaction validated', 'Refund issued', 'Card tokenized'],
            'WARN':  ['Payment retry attempt', 'High transaction volume', 'Slow DB response'],
            'ERROR': ['Payment gateway timeout', 'Card declined', 'DB connection lost']
        }
    },
    'auth-service': {
        'logs_per_batch': 25,           # High volume — every request hits auth
        'level_weights': [90, 8, 2],
        'messages': {
            'INFO':  ['User logged in', 'Token issued', 'Session refreshed', 'Password verified'],
            'WARN':  ['Invalid token attempt', 'Session nearing expiry', 'Rate limit warning'],
            'ERROR': ['Auth DB unreachable', 'Token validation failed', 'Max retries exceeded']
        }
    },
    'inventory': {
        'logs_per_batch': 10,           # Moderate volume
        'level_weights': [85, 12, 3],
        'messages': {
            'INFO':  ['Stock updated', 'Product fetched', 'Warehouse sync complete', 'Price updated'],
            'WARN':  ['Low stock warning', 'Sync delay', 'Cache invalidated'],
            'ERROR': ['Stock update failed', 'Warehouse API timeout', 'Duplicate SKU detected']
        }
    },
    'notification': {
        'logs_per_batch': 8,            # Low volume — not every action notifies
        'level_weights': [88, 10, 2],
        'messages': {
            'INFO':  ['Email sent', 'SMS delivered', 'Push notification sent', 'Webhook fired'],
            'WARN':  ['Email bounce', 'SMS delivery delayed', 'Webhook retry'],
            'ERROR': ['SMTP server unreachable', 'SMS provider error', 'Push token invalid']
        }
    }
}

LEVELS = ['INFO', 'WARN', 'ERROR']


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def send_log(service: str, level: str, message: str):
    payload = {
        'level': level,
        'service': service,
        'message': message,
        'trace_id': f"trace_{random.randint(10000, 99999)}",
        'user_id':  f"user_{random.randint(100, 999)}"
    }
    try:
        requests.post(COLLECTOR_URL, json=payload, timeout=1)
    except Exception:
        pass


def send_normal_batch(services: list):
    for service in services:
        profile = SERVICE_PROFILES[service]
        count   = profile['logs_per_batch']
        weights = profile['level_weights']
        msgs    = profile['messages']

        for _ in range(count):
            level   = random.choices(LEVELS, weights=weights)[0]
            message = random.choice(msgs[level])
            send_log(service, level, message)


def separator(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# ─────────────────────────────────────────────
# PHASE 1 — BASELINE
# Run for enough cycles so Isolation Forest
# has ≥20 data points to train on.
# Each cycle = 1 simulated "minute" of traffic.
# ─────────────────────────────────────────────
def phase_baseline(cycles: int = 40, delay: float = 5.0):
    separator(f"PHASE 1 — BASELINE  ({cycles} cycles × {delay}s = {cycles*delay/60:.1f} min)")
    print("  Building normal baseline for all services...")
    print("  Detector needs 20+ data points before it starts scoring.\n")

    all_services = list(SERVICE_PROFILES.keys())

    for i in range(1, cycles + 1):
        send_normal_batch(all_services)
        print(f"  Cycle {i:>3}/{cycles}  — normal traffic sent", end='\r')
        time.sleep(delay)

    print(f"\n  ✓ Baseline phase complete — {cycles} cycles sent")


# ─────────────────────────────────────────────
# PHASE 2 — ANOMALY INJECTION
# Each scenario runs for a few cycles so the
# detector has time to catch it.
# ─────────────────────────────────────────────
def phase_anomalies(cycles_per_scenario: int = 5, delay: float = 5.0):
    separator("PHASE 2 — ANOMALY INJECTION")
    print("  Watch your detector terminal for alerts!\n")

    # ── Scenario A: ERROR SPIKE on payment-api ──
    # Simulates: database went down, all payments failing
    separator("  [A] payment-api — ERROR SPIKE (DB down simulation)")
    for i in range(1, cycles_per_scenario + 1):
        # 80% of logs are now ERRORs instead of the normal 5%
        for _ in range(40):
            level = random.choices(LEVELS, weights=[10, 10, 80])[0]
            msg   = random.choice(SERVICE_PROFILES['payment-api']['messages'][level])
            send_log('payment-api', level, f"[INJECTED] {msg}")

        # Keep other services normal so detector can isolate the culprit
        send_normal_batch(['auth-service', 'inventory', 'notification'])
        print(f"  Cycle {i}/{cycles_per_scenario} — payment-api error spike active")
        time.sleep(delay)

    # ── Scenario B: SILENCE on auth-service ──
    # Simulates: service crashed, no logs coming in at all
    separator("  [B] auth-service — COMPLETE SILENCE (crash simulation)")
    for i in range(1, cycles_per_scenario + 1):
        # auth-service sends ZERO logs this cycle
        send_normal_batch(['payment-api', 'inventory', 'notification'])
        print(f"  Cycle {i}/{cycles_per_scenario} — auth-service is silent")
        time.sleep(delay)

    # ── Scenario C: ERROR RATIO EXPLOSION on inventory ──
    # Simulates: warehouse API went down, 50%+ of calls failing
    separator("  [C] inventory — ERROR RATIO EXPLOSION (warehouse API down)")
    for i in range(1, cycles_per_scenario + 1):
        for _ in range(12):
            level = random.choices(LEVELS, weights=[20, 30, 50])[0]  # 50% error
            msg   = random.choice(SERVICE_PROFILES['inventory']['messages'][level])
            send_log('inventory', level, f"[INJECTED] {msg}")

        send_normal_batch(['payment-api', 'auth-service', 'notification'])
        print(f"  Cycle {i}/{cycles_per_scenario} — inventory error ratio ~50%")
        time.sleep(delay)

    # ── Scenario D: LOG VOLUME STORM on notification ──
    # Simulates: retry loop gone infinite, flooding the system
    separator("  [D] notification — VOLUME STORM (infinite retry loop)")
    for i in range(1, cycles_per_scenario + 1):
        # 10x normal volume (normal = 8, storm = 80+)
        for _ in range(90):
            level = random.choices(LEVELS, weights=[60, 30, 10])[0]
            msg   = random.choice(SERVICE_PROFILES['notification']['messages'][level])
            send_log('notification', level, f"[INJECTED] retry #{random.randint(1,999)} {msg}")

        send_normal_batch(['payment-api', 'auth-service', 'inventory'])
        print(f"  Cycle {i}/{cycles_per_scenario} — notification volume storm active")
        time.sleep(delay)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════╗
  Log Generator — Anomaly Detection Test Suite
  Collector  : http://localhost:8080/logs
  Dashboard  : http://localhost:3000
╚══════════════════════════════════════════════════╝

  TOTAL RUNTIME:
    Phase 1 (Baseline)  : ~2 min  (40 cycles × 5s)
    Phase 2 (Anomalies) : ~1.5 min (4 scenarios × 5 cycles × 5s)
    ─────────────────────────────────────────────
    Total               : ~3.5 minutes

  TIP: Open a second terminal and run:
       docker logs -f <your_detector_container_name>
       to watch anomaly alerts in real time.
    """)

    input("  Press ENTER to start...\n")

    phase_baseline(cycles=40, delay=5.0)
    phase_anomalies(cycles_per_scenario=5, delay=5.0)

    print("""
╔══════════════════════════════════════════════════╗
  ✓ Test complete!
  Check your detector logs for anomaly alerts.
  4 scenarios were injected — did the model catch them?
╚══════════════════════════════════════════════════╝
    """)
