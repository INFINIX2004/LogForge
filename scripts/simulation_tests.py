import requests
import random
import time
import json
import os
import math
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
COLLECTOR_URL  = "http://localhost:8080/logs"
API_URL        = "http://localhost:8000/api"
REPORT_DIR     = "./test_results"

CYCLE_DELAY    = 6      # seconds per cycle (slightly more than detector's 5s)
BASELINE_CYCLES = 45    # cycles of normal traffic before each scenario
SCENARIO_CYCLES = 12    # cycles of anomalous traffic per scenario
POLL_WAIT       = 12     # seconds to wait after scenario before checking API

LEVELS = ['INFO', 'WARN', 'ERROR']

# ─────────────────────────────────────────────
# REALISTIC SERVICE PROFILES
# Each service has natural variance built in
# ─────────────────────────────────────────────
SERVICE_PROFILES = {
    'payment-api': {
        'base_volume':     15,
        'volume_jitter':   0.20,   # ±20% volume variance each cycle
        'level_weights':   [80, 15, 5],
        'hosts':           ['pay-01', 'pay-02', 'pay-03'],
        'host_weights':    [50, 35, 15],   # pay-01 handles most traffic
        'messages': {
            'INFO':  [
                ('Payment processed successfully', 40),
                ('Transaction validated', 30),
                ('Refund issued', 15),
                ('Card tokenized', 10),
                ('3DS check passed', 5),
            ],
            'WARN':  [
                ('Payment retry attempt', 45),
                ('High transaction volume', 30),
                ('Slow DB response >200ms', 25),
            ],
            'ERROR': [
                ('Payment gateway timeout', 50),
                ('Card declined', 30),
                ('DB connection lost', 20),
            ],
        }
    },
    'auth-service': {
        'base_volume':     25,
        'volume_jitter':   0.15,
        'level_weights':   [90, 8, 2],
        'hosts':           ['auth-01', 'auth-02'],
        'host_weights':    [60, 40],
        'messages': {
            'INFO':  [
                ('User logged in', 50),
                ('Token issued', 25),
                ('Session refreshed', 15),
                ('Password verified', 10),
            ],
            'WARN':  [
                ('Invalid token attempt', 50),
                ('Session nearing expiry', 30),
                ('Rate limit warning', 20),
            ],
            'ERROR': [
                ('Auth DB unreachable', 40),
                ('Token validation failed', 40),
                ('Max retries exceeded', 20),
            ],
        }
    },
    'inventory': {
        'base_volume':     10,
        'volume_jitter':   0.25,   # inventory has higher natural variance
        'level_weights':   [85, 12, 3],
        'hosts':           ['inv-01'],
        'host_weights':    [100],
        'messages': {
            'INFO':  [
                ('Stock updated', 40),
                ('Product fetched', 35),
                ('Warehouse sync complete', 15),
                ('Price updated', 10),
            ],
            'WARN':  [
                ('Low stock warning', 50),
                ('Sync delay >5s', 30),
                ('Cache invalidated', 20),
            ],
            'ERROR': [
                ('Stock update failed', 40),
                ('Warehouse API timeout', 40),
                ('Duplicate SKU detected', 20),
            ],
        }
    },
    'notification': {
        'base_volume':     8,
        'volume_jitter':   0.30,   # notifications are bursty by nature
        'level_weights':   [88, 10, 2],
        'hosts':           ['notif-01', 'notif-02'],
        'host_weights':    [70, 30],
        'messages': {
            'INFO':  [
                ('Email sent', 45),
                ('SMS delivered', 25),
                ('Push notification sent', 20),
                ('Webhook fired', 10),
            ],
            'WARN':  [
                ('Email bounce', 50),
                ('SMS delivery delayed', 30),
                ('Webhook retry #1', 20),
            ],
            'ERROR': [
                ('SMTP server unreachable', 40),
                ('SMS provider error', 35),
                ('Push token invalid', 25),
            ],
        }
    }
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def weighted_choice(options_with_weights: list) -> str:
    """Choose from [(option, weight), ...] with weighted probability."""
    options = [o for o, _ in options_with_weights]
    weights = [w for _, w in options_with_weights]
    return random.choices(options, weights=weights)[0]


def send_log(service: str, level: str, message: str, host: str):
    payload = {
        'level':    level,
        'service':  service,
        'message':  message,
        'trace_id': f"trace_{random.randint(10000, 99999)}",
        'user_id':  f"user_{random.randint(100, 999)}",
    }
    # Inject host via metadata (collector uses its own host field,
    # but message context carries the origin)
    payload['message'] = f"[{host}] {message}"
    try:
        requests.post(COLLECTOR_URL, json=payload, timeout=1)
    except Exception:
        pass


def send_normal_cycle(services: list, multiplier: float = 1.0):
    """
    Send one realistic cycle of normal traffic.
    Natural variance is applied per-service via volume_jitter.
    """
    for service in services:
        p       = SERVICE_PROFILES[service]
        jitter  = 1.0 + random.uniform(-p['volume_jitter'], p['volume_jitter'])
        count   = max(1, int(p['base_volume'] * multiplier * jitter))
        weights = p['level_weights']
        msgs    = p['messages']
        hosts   = p['hosts']
        hwts    = p['host_weights']

        for _ in range(count):
            level   = random.choices(LEVELS, weights=weights)[0]
            message = weighted_choice(msgs[level])
            host    = random.choices(hosts, weights=hwts)[0]
            # Add timestamp noise to messages occasionally
            if random.random() < 0.1:
                message += f" (latency={random.randint(50,500)}ms)"
            send_log(service, level, message, host)


def fetch_recent_anomalies(service: str, since_iso: str) -> list:
    """Poll the API for anomalies for a service since a given time."""
    try:
        res = requests.get(
            f"{API_URL}/anomalies",
            params={'service': service, 'hours': 1, 'limit': 200},
            timeout=5
        )
        all_anomalies = res.json().get('anomalies', [])
        # Filter to only those after since_iso
        return [
            a for a in all_anomalies
            if a['detected_at'] >= since_iso
        ]
    except Exception as e:
        print(f"    ⚠ Could not fetch anomalies: {e}")
        return []


def bar(value, max_value=100, width=20) -> str:
    filled = int((value / max_value) * width)
    return '█' * filled + '░' * (width - filled)


def section(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")


# ─────────────────────────────────────────────
# BASELINE
# ─────────────────────────────────────────────
def run_baseline(cycles: int, label: str = ""):
    tag = f" [{label}]" if label else ""
    print(f"\n  ⏳ Running {cycles}-cycle baseline{tag}...")
    all_services = list(SERVICE_PROFILES.keys())
    for i in range(cycles):
        send_normal_cycle(all_services)
        print(f"    Cycle {i+1:>3}/{cycles}", end='\r')
        time.sleep(CYCLE_DELAY)
    print(f"    ✓ Baseline complete{' '*20}")


# ─────────────────────────────────────────────
# SCENARIO RUNNER
# ─────────────────────────────────────────────
def run_scenario(scenario_fn, target_service, label, description):
    section(f"SCENARIO: {label}")
    print(f"  Target  : {target_service}")
    print(f"  What    : {description}\n")

    scenario_start_dt = datetime.now(timezone.utc)
    first_detection_cycle = None
    confidences = []

    for cycle in range(1, SCENARIO_CYCLES + 1):
        scenario_fn(cycle, SCENARIO_CYCLES)
        time.sleep(POLL_WAIT)

        # Check from 30 seconds before scenario start to catch
        # any detections that landed slightly early
        since = (scenario_start_dt).strftime('%Y-%m-%dT%H:%M:%S')
        detections = fetch_recent_anomalies(target_service, since)

        if detections and first_detection_cycle is None:
            first_detection_cycle = cycle
            print(f"  🚨 DETECTED on cycle {cycle}!")

        for d in detections:
            if d['confidence'] not in confidences:
                confidences.append(d['confidence'])
                print(f"     confidence={d['confidence']:.0f}%  "
                      f"errors={d['error_count']}  "
                      f"ratio={d['error_ratio']*100:.1f}%")

        if not detections:
            print(f"  Cycle {cycle:>2}/{SCENARIO_CYCLES} — no detection yet")

        time.sleep(max(0, CYCLE_DELAY - POLL_WAIT))
        detected       = first_detection_cycle is not None
    avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0

    result = {
        'scenario':         label,
        'target_service':   target_service,
        'description':      description,
        'detected':         detected,
        'cycles_to_detect': first_detection_cycle if detected else None,
        'total_cycles':     SCENARIO_CYCLES,
        'detection_count':  len(confidences),
        'avg_confidence':   avg_confidence,
        'max_confidence':   round(max(confidences), 1) if confidences else 0,
        'scenario_start':   scenario_start_dt.isoformat(),
    }

    status = "✅ PASS" if detected else "❌ MISS"
    print(f"\n  Result : {status}")
    if detected:
        print(f"  First detection: cycle {first_detection_cycle}/{SCENARIO_CYCLES}")
        print(f"  Avg confidence : {avg_confidence}%")

    return result

# ─────────────────────────────────────────────
# SCENARIO DEFINITIONS
# Each takes (cycle, total_cycles) and sends logs
# ─────────────────────────────────────────────
ALL_SERVICES = list(SERVICE_PROFILES.keys())

# ── 1. Error Spike ──
def scenario_error_spike(cycle, total):
    """
    Sudden surge in errors — ramps up over first 3 cycles then sustains.
    Simulates: database went down mid-operation.
    """
    ramp     = min(cycle / 3.0, 1.0)
    err_pct  = int(5 + 75 * ramp)     # 5% → 80%
    warn_pct = 10
    info_pct = max(1, 100 - err_pct - warn_pct)

    p = SERVICE_PROFILES['payment-api']
    jitter = 1.0 + random.uniform(-0.1, 0.1)
    count  = int(p['base_volume'] * 1.2 * jitter)

    for _ in range(count):
        level   = random.choices(LEVELS, weights=[info_pct, warn_pct, err_pct])[0]
        message = weighted_choice(p['messages'][level])
        host    = random.choices(p['hosts'], weights=p['host_weights'])[0]
        if level == 'ERROR':
            message += f" [attempt {random.randint(1,5)}]"
        send_log('payment-api', level, message, host)

    send_normal_cycle([s for s in ALL_SERVICES if s != 'payment-api'])


# ── 2. Service Silence ──
def scenario_silence(cycle, total):
    """
    auth-service goes completely silent.
    Simulates: service crashed, pod evicted, network partition.
    """
    # auth-service sends nothing — not even a heartbeat
    send_normal_cycle([s for s in ALL_SERVICES if s != 'auth-service'])


# ── 3. Error Ratio Explosion ──
def scenario_error_ratio(cycle, total):
    """
    50%+ of inventory requests start failing.
    Simulates: warehouse API is down, every stock check fails.
    """
    p = SERVICE_PROFILES['inventory']
    jitter = 1.0 + random.uniform(-0.15, 0.15)
    count  = int(p['base_volume'] * jitter)

    for _ in range(count):
        level   = random.choices(LEVELS, weights=[20, 30, 50])[0]
        message = weighted_choice(p['messages'][level])
        host    = random.choices(p['hosts'], weights=p['host_weights'])[0]
        send_log('inventory', level, message, host)

    send_normal_cycle([s for s in ALL_SERVICES if s != 'inventory'])


# ── 4. Volume Storm ──
def scenario_volume_storm(cycle, total):
    """
    notification floods with 10x normal volume.
    Simulates: infinite retry loop, webhook storm.
    Errors stay normal — it's purely a volume anomaly.
    """
    p = SERVICE_PROFILES['notification']
    jitter = 1.0 + random.uniform(-0.05, 0.15)
    count  = int(p['base_volume'] * 10 * jitter)  # 10x volume

    for _ in range(count):
        level   = random.choices(LEVELS, weights=[75, 20, 5])[0]
        message = weighted_choice(p['messages'][level])
        host    = random.choices(p['hosts'], weights=p['host_weights'])[0]
        retry   = random.randint(1, 500)
        send_log('notification', level, f"retry #{retry} — {message}", host)

    send_normal_cycle([s for s in ALL_SERVICES if s != 'notification'])


# ── 5. Slow Degradation ──
def scenario_slow_degradation(cycle, total):
    """
    Errors on payment-api creep up gradually — 5% → 40% over all cycles.
    Simulates: memory leak causing increasing failures, slow DB degradation.
    This is the hardest scenario for threshold-based systems to catch.
    """
    progress = cycle / total
    err_pct  = int(5 + 35 * progress)   # gradual: 5% → 40%
    warn_pct = int(10 + 10 * progress)  # warns also rise slowly
    info_pct = max(1, 100 - err_pct - warn_pct)

    p = SERVICE_PROFILES['payment-api']
    jitter = 1.0 + random.uniform(-0.20, 0.20)
    count  = int(p['base_volume'] * jitter)

    for _ in range(count):
        level   = random.choices(LEVELS, weights=[info_pct, warn_pct, err_pct])[0]
        message = weighted_choice(p['messages'][level])
        host    = random.choices(p['hosts'], weights=p['host_weights'])[0]
        if level == 'ERROR':
            # Repeated same error — entropy drops — model notices
            message = 'DB connection lost'
        send_log('payment-api', level, message, host)

    send_normal_cycle([s for s in ALL_SERVICES if s != 'payment-api'])


# ── 6. Cascading Failure ──
def scenario_cascading(cycle, total):
    """
    payment-api spikes first. 2 cycles later auth-service and
    inventory also start erroring — they depend on payment-api.
    Simulates: upstream failure causing downstream degradation.
    """
    p_pay  = SERVICE_PROFILES['payment-api']
    p_auth = SERVICE_PROFILES['auth-service']
    p_inv  = SERVICE_PROFILES['inventory']

    # payment-api fails immediately
    for _ in range(int(p_pay['base_volume'] * 1.5)):
        level   = random.choices(LEVELS, weights=[10, 20, 70])[0]
        message = weighted_choice(p_pay['messages'][level])
        host    = random.choices(p_pay['hosts'], weights=p_pay['host_weights'])[0]
        send_log('payment-api', level, message, host)

    # auth-service degrades after cycle 2
    if cycle >= 2:
        for _ in range(int(p_auth['base_volume'] * 1.2)):
            level   = random.choices(LEVELS, weights=[40, 30, 30])[0]
            message = weighted_choice(p_auth['messages'][level])
            if level == 'ERROR':
                message = 'Auth DB unreachable — payment dependency lost'
            host = random.choices(p_auth['hosts'], weights=p_auth['host_weights'])[0]
            send_log('auth-service', level, message, host)
    else:
        send_normal_cycle(['auth-service'])

    # inventory degrades after cycle 3
    if cycle >= 3:
        for _ in range(int(p_inv['base_volume'] * 1.1)):
            level   = random.choices(LEVELS, weights=[50, 30, 20])[0]
            message = weighted_choice(p_inv['messages'][level])
            if level == 'ERROR':
                message = 'Stock update failed — payment service unavailable'
            send_log('inventory', level, message, 'inv-01')
    else:
        send_normal_cycle(['inventory'])

    send_normal_cycle(['notification'])


# ─────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────
def save_report(results: list, baseline_cycles: int):
    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path      = os.path.join(REPORT_DIR, f"report_{timestamp}.json")

    results = [r for r in results if r is not None]
    passed     = sum(1 for r in results if r['detected'])
    total      = len(results)
    detection_rate = round(passed / total * 100, 1) if total else 0

    report = {
        'run_timestamp':    datetime.now(timezone.utc).isoformat(),
        'config': {
            'baseline_cycles':  baseline_cycles,
            'scenario_cycles':  SCENARIO_CYCLES,
            'cycle_delay_s':    CYCLE_DELAY,
            'collector_url':    COLLECTOR_URL,
            'api_url':          API_URL,
        },
        'summary': {
            'total_scenarios':  total,
            'passed':           passed,
            'missed':           total - passed,
            'detection_rate':   detection_rate,
        },
        'scenarios': results
    }

    with open(path, 'w') as f:
        json.dump(report, f, indent=2)

    return path, report


def print_summary(report: dict, report_path: str):
    section("TEST SUITE SUMMARY")
    s = report['summary']

    print(f"\n  Detection rate : {s['detection_rate']}%  "
          f"[{bar(s['detection_rate'])}]")
    print(f"  Passed : {s['passed']}/{s['total_scenarios']}")
    print(f"  Missed : {s['missed']}/{s['total_scenarios']}\n")

    print(f"  {'Scenario':<30} {'Result':<10} {'Cycles':<10} {'Avg Conf'}")
    print(f"  {'─'*30} {'─'*9} {'─'*9} {'─'*10}")

    for r in report['scenarios']:
        status = '✅ PASS' if r['detected'] else '❌ MISS'
        cycles = (f"{r['cycles_to_detect']}/{r['total_cycles']}"
                  if r['detected'] else f"—/{r['total_cycles']}")
        conf   = f"{r['avg_confidence']}%" if r['detected'] else '—'
        print(f"  {r['scenario']:<30} {status:<10} {cycles:<10} {conf}")

    print(f"\n  📄 Report saved → {report_path}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════╗
  Anomaly Detection Simulation Test Suite
  6 realistic failure scenarios with natural variance
  ────────────────────────────────────────────────────────
  Collector : http://localhost:8080/logs
  API       : http://localhost:8000/api
  Report    : ./test_results/report_<timestamp>.json
╚══════════════════════════════════════════════════════════╝

  RUNTIME ESTIMATE:
    Baseline × 6  : ~{:.0f} min
    Scenarios × 6 : ~{:.0f} min
    ──────────────────────────────────
    Total         : ~{:.0f} min

  Make sure docker-compose is running and the detector
  has trained models before starting.
    """.format(
        BASELINE_CYCLES * CYCLE_DELAY * 6 / 60,
        SCENARIO_CYCLES * CYCLE_DELAY * 6 / 60,
        (BASELINE_CYCLES + SCENARIO_CYCLES) * CYCLE_DELAY * 6 / 60,
    ))

    input("  Press ENTER to start...\n")

    results = []

    # ── Each scenario gets its own fresh baseline ──
    # so the model doesn't carry anomaly signal into the next test

    scenarios = [
        {
            'fn':          scenario_error_spike,
            'service':     'payment-api',
            'label':       'Error Spike',
            'description': 'Gradual ramp from 5% to 80% error rate — DB failure',
        },
        {
            'fn':          scenario_silence,
            'service':     'auth-service',
            'label':       'Service Silence',
            'description': 'auth-service goes completely silent — crash/partition',
        },
        {
            'fn':          scenario_error_ratio,
            'service':     'inventory',
            'label':       'Error Ratio Explosion',
            'description': '50% of inventory requests failing — warehouse API down',
        },
        {
            'fn':          scenario_volume_storm,
            'service':     'notification',
            'label':       'Volume Storm',
            'description': '10x normal volume, normal error rate — retry loop',
        },
        {
            'fn':          scenario_slow_degradation,
            'service':     'payment-api',
            'label':       'Slow Degradation',
            'description': 'Errors creep 5%→40% over time — memory leak pattern',
        },
        {
            'fn':          scenario_cascading,
            'service':     'payment-api',
            'label':       'Cascading Failure',
            'description': 'payment-api fails, auth + inventory degrade 2-3 cycles later',
        },
    ]

    for s in scenarios:
        # Fresh baseline before each scenario
        run_baseline(BASELINE_CYCLES, label=s['label'])

        result = run_scenario(
            scenario_fn  = s['fn'],
            target_service = s['service'],
            label        = s['label'],
            description  = s['description'],
        )
        results.append(result)

        # Cool-down: let normal traffic re-establish before next scenario
        print(f"\n  ⏸  Cool-down (10 cycles)...")
        run_baseline(10, label='cool-down')

    report_path, report = save_report(results, BASELINE_CYCLES)
    print_summary(report, report_path)
