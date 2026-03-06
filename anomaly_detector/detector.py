import clickhouse_connect
import time
import os
import json
import math
import numpy as np
from collections import defaultdict
from datetime import datetime, timezone
from sklearn.ensemble import IsolationForest
import joblib

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
CLICKHOUSE_HOST    = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT    = int(os.getenv('CLICKHOUSE_PORT', 8123))

CHECK_INTERVAL     = 5       # seconds (5 for testing, 60 for production)
MIN_DATAPOINTS     = 20      # minimum history before a model trains
MAX_HISTORY        = 1440    # rolling window: 1440 min = 24 hours
RETRAIN_EVERY      = 60      # retrain every N cycles
BOOTSTRAP_HOURS    = 24      # how many hours of history to load on startup

MODEL_DIR          = os.getenv('MODEL_DIR', '/app/models')

# Feature names — used in alerts so you know what each number means
FEATURE_NAMES = [
    'error_count',
    'warn_count',
    'total_logs',
    'error_ratio',
    'unique_hosts',
    'error_burst',      # NEW: max errors in any 10s sub-window
    'message_entropy',  # NEW: Shannon entropy of message variety
]

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
# history[service]         → flat list of feature vectors (all hours)
# seasonal_history[service][hour] → feature vectors for that hour bucket
# models[service]          → global IsolationForest
# seasonal_models[service][hour] → per-hour IsolationForest
history          = defaultdict(list)
seasonal_history = defaultdict(lambda: defaultdict(list))
models           = {}
seasonal_models  = defaultdict(dict)
cycle_count      = defaultdict(int)


# ─────────────────────────────────────────────
# CLICKHOUSE CLIENT
# ─────────────────────────────────────────────
def get_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database='logs'
    )


# ─────────────────────────────────────────────
# FEATURE EXTRACTION — current minute
# ─────────────────────────────────────────────
def extract_features(client) -> dict:
    """
    Features:
      error_count    — ERROR log count
      warn_count     — WARN log count
      total_logs     — total log volume
      error_ratio    — error_count / total_logs
      unique_hosts   — distinct hosts reporting
      error_burst    — max ERRORs in any 10s sub-window (spikiness)
      message_entropy— Shannon entropy of message distribution
                        low = repetitive (e.g. same error looping)
                        high = healthy variety
    """
    # ── Base features ──
    base = client.query("""
        SELECT
            service,
            countIf(level = 'ERROR')           AS error_count,
            countIf(level = 'WARN')            AS warn_count,
            count()                            AS total_logs,
            countIf(level = 'ERROR') / count() AS error_ratio,
            uniq(host)                         AS unique_hosts
        FROM logs
        WHERE timestamp >= now() - INTERVAL 1 MINUTE
        GROUP BY service
    """)

    features = {}
    for row in base.result_rows:
        service, error_count, warn_count, total_logs, error_ratio, unique_hosts = row
        features[service] = {
            'error_count':  float(error_count),
            'warn_count':   float(warn_count),
            'total_logs':   float(total_logs),
            'error_ratio':  float(error_ratio),
            'unique_hosts': float(unique_hosts),
        }

    if not features:
        return {}

    # ── Error burst: max errors in any 10s sub-window ──
    burst = client.query("""
        SELECT
            service,
            max(bucket_count) AS error_burst
        FROM (
            SELECT
                service,
                toStartOfInterval(timestamp, INTERVAL 10 SECOND) AS bucket,
                countIf(level = 'ERROR') AS bucket_count
            FROM logs
            WHERE timestamp >= now() - INTERVAL 1 MINUTE
            GROUP BY service, bucket
        )
        GROUP BY service
    """)
    for row in burst.result_rows:
        service, error_burst = row
        if service in features:
            features[service]['error_burst'] = float(error_burst)

    # ── Message entropy: Shannon entropy of message distribution ──
    entropy_q = client.query("""
        SELECT
            service,
            uniq(message)  AS unique_msgs,
            count()        AS total
        FROM logs
        WHERE timestamp >= now() - INTERVAL 1 MINUTE
        GROUP BY service
    """)
    for row in entropy_q.result_rows:
        service, unique_msgs, total = row
        if service in features and total > 0:
            # Approximate entropy from unique ratio
            # True entropy needs per-message counts — this is a fast approximation
            p = unique_msgs / total
            entropy = -p * math.log2(p + 1e-9) - (1 - p) * math.log2(1 - p + 1e-9)
            features[service]['message_entropy'] = round(entropy, 4)

    # ── Build final feature vectors (consistent order) ──
    result = {}
    for service, f in features.items():
        result[service] = [
            f.get('error_count',    0.0),
            f.get('warn_count',     0.0),
            f.get('total_logs',     0.0),
            f.get('error_ratio',    0.0),
            f.get('unique_hosts',   0.0),
            f.get('error_burst',    0.0),
            f.get('message_entropy',0.0),
        ]
    return result


# ─────────────────────────────────────────────
# HISTORICAL BOOTSTRAP
# ─────────────────────────────────────────────
def bootstrap_from_history(client):

    print(f"\n⏳ Bootstrapping from last {BOOTSTRAP_HOURS}h of historical data...")

    result = client.query(f"""
        SELECT
            service,
            toStartOfMinute(timestamp)         AS minute,
            countIf(level = 'ERROR')           AS error_count,
            countIf(level = 'WARN')            AS warn_count,
            count()                            AS total_logs,
            countIf(level = 'ERROR') / count() AS error_ratio,
            uniq(host)                         AS unique_hosts,
            uniq(message)                      AS unique_msgs
        FROM logs
        WHERE timestamp >= now() - INTERVAL {BOOTSTRAP_HOURS} HOUR
        GROUP BY service, minute
        ORDER BY service, minute ASC
    """)

    counts = defaultdict(int)
    for row in result.result_rows:
        service, minute, error_count, warn_count, total_logs, \
            error_ratio, unique_hosts, unique_msgs = row

        # Approximate entropy
        p = unique_msgs / max(total_logs, 1)
        entropy = -p * math.log2(p + 1e-9) - (1 - p) * math.log2(1 - p + 1e-9)

        vector = [
            float(error_count),
            float(warn_count),
            float(total_logs),
            float(error_ratio),
            float(unique_hosts),
            float(error_count),   # error_burst approx (no sub-window in history)
            round(entropy, 4),
        ]

        history[service].append(vector)

        # Also populate seasonal history by hour-of-day
        hour = minute.hour
        seasonal_history[service][hour].append(vector)

        counts[service] += 1

    if counts:
        for service, n in counts.items():
            print(f"  [{service}] bootstrapped {n} minutes of history")
        print(f"\n✓ Bootstrap complete — training models now...\n")

        # Train immediately after bootstrap
        for service in counts:
            trained = train_model(service, source='bootstrap')
            if trained:
                models[service] = trained
            # Train seasonal models for any hour that has enough data
            for hour, hvecs in seasonal_history[service].items():
                if len(hvecs) >= MIN_DATAPOINTS:
                    sm = train_seasonal_model(service, hour)
                    if sm:
                        seasonal_models[service][hour] = sm
    else:
        print("  No historical data found — will train from live data\n")


# ─────────────────────────────────────────────
# DYNAMIC CONTAMINATION
# ─────────────────────────────────────────────
def compute_contamination(service: str) -> float:

    data = history[service]
    if len(data) < MIN_DATAPOINTS:
        return 0.05  # default

    error_counts = [v[0] for v in data]  # feature[0] = error_count
    mean = np.mean(error_counts)
    std  = np.std(error_counts)

    if mean == 0:
        return 0.02  # very quiet service — be sensitive

    cv = std / mean  # coefficient of variation
    contamination = float(np.clip(cv * 0.1, 0.01, 0.15))
    return round(contamination, 4)


# ─────────────────────────────────────────────
# MODEL TRAINING
# ─────────────────────────────────────────────
def train_model(service: str, source: str = 'live') -> IsolationForest | None:
    data = history[service]
    if len(data) < MIN_DATAPOINTS:
        print(f"[{service}] Not enough data ({len(data)}/{MIN_DATAPOINTS})")
        return None

    contamination = compute_contamination(service)
    X = np.array(data)
    model = IsolationForest(
        n_estimators=150,           # more trees = more stable
        contamination=contamination,
        max_samples='auto',
        random_state=42
    )
    model.fit(X)
    print(f"[{service}] Global model trained — {len(data)} points, "
          f"contamination={contamination} [{source}] ✓")
    save_model(service, model)
    save_history(service)
    return model


def train_seasonal_model(service: str, hour: int) -> IsolationForest | None:
    data = seasonal_history[service][hour]
    if len(data) < MIN_DATAPOINTS:
        return None

    contamination = compute_contamination(service)
    X = np.array(data)
    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=42
    )
    model.fit(X)
    print(f"[{service}] Seasonal model hour={hour:02d} trained — {len(data)} points ✓")
    save_seasonal_model(service, hour, model)
    return model


# ─────────────────────────────────────────────
# ANOMALY SCORING
# ─────────────────────────────────────────────
def score_and_alert(service: str, feature_vector: list, client):
    current_hour = datetime.now(timezone.utc).hour

    # ── Prefer seasonal model for this hour if available ──
    seasonal = seasonal_models[service].get(current_hour)
    global_m  = models.get(service)

    if seasonal is None and global_m is None:
        return

    X          = np.array([feature_vector])
    scores     = []
    predictions = []

    if seasonal:
        scores.append(seasonal.decision_function(X)[0])
        predictions.append(seasonal.predict(X)[0])

    if global_m:
        scores.append(global_m.decision_function(X)[0])
        predictions.append(global_m.predict(X)[0])

    # Anomaly if ANY model flags it (OR logic — catches more)
    raw_score  = min(scores)        # most anomalous score wins
    prediction = -1 if -1 in predictions else 1

    confidence = round((abs(raw_score) / 0.1) * 100, 1)
    confidence = min(confidence, 100.0)

    model_used = 'seasonal' if (seasonal and raw_score == scores[0]) else 'global'

    if prediction == -1:
        alert(service, feature_vector, raw_score, confidence, model_used)
        write_anomaly_to_db(client, service, feature_vector, raw_score, confidence)


# ─────────────────────────────────────────────
# ALERT
# ─────────────────────────────────────────────
def alert(service, features, raw_score, confidence, model_used='global'):
    error_count, warn_count, total_logs, error_ratio, \
        unique_hosts, error_burst, message_entropy = features

    print(f"""
╔══════════════════════════════════════════════╗
  ⚠️  ANOMALY DETECTED  [{model_used} model]
  Service        : {service}
  Confidence     : {confidence}%
  ────────────────────────────────────────────
  Error count    : {int(error_count)}/min
  Warn count     : {int(warn_count)}/min
  Total logs     : {int(total_logs)}/min
  Error ratio    : {error_ratio:.1%}
  Unique hosts   : {int(unique_hosts)}
  Error burst    : {int(error_burst)} (max in 10s)
  Msg entropy    : {message_entropy:.3f}
  Raw score      : {raw_score:.4f}
╚══════════════════════════════════════════════╝
    """)


def write_anomaly_to_db(client, service, features, raw_score, confidence):
    error_count, warn_count, total_logs, error_ratio, \
        unique_hosts, error_burst, message_entropy = features
    try:
        client.insert(
            'anomalies',
            [(
                datetime.now(timezone.utc),
                service,
                float(confidence),
                float(raw_score),
                int(error_count),
                int(warn_count),
                int(total_logs),
                float(error_ratio),
                int(unique_hosts),
            )],
            column_names=[
                'detected_at', 'service', 'confidence', 'raw_score',
                'error_count', 'warn_count', 'total_logs',
                'error_ratio', 'unique_hosts'
            ]
        )
    except Exception as e:
        print(f"❌ Failed to write anomaly to DB: {e}")


# ─────────────────────────────────────────────
# PERSISTENCE
# ─────────────────────────────────────────────
def save_model(service, model):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(MODEL_DIR, f"{service}_model.joblib"))

def save_seasonal_model(service, hour, model):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(MODEL_DIR, f"{service}_h{hour:02d}_model.joblib"))

def save_history(service):
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, f"{service}_history.json"), 'w') as f:
        json.dump(history[service], f)

def load_persisted_state():
    if not os.path.exists(MODEL_DIR):
        print("No persisted state — will bootstrap from ClickHouse.")
        return

    loaded_m, loaded_sm, loaded_h = 0, 0, 0

    for filename in os.listdir(MODEL_DIR):
        path = os.path.join(MODEL_DIR, filename)

        # Global model: payment-api_model.joblib
        if filename.endswith('_model.joblib') and '_h' not in filename:
            service = filename.replace('_model.joblib', '')
            try:
                models[service] = joblib.load(path)
                loaded_m += 1
                print(f"  [{service}] global model loaded ✓")
            except Exception as e:
                print(f"  [{service}] failed to load model: {e}")

        # Seasonal model: payment-api_h09_model.joblib
        elif filename.endswith('_model.joblib') and '_h' in filename:
            parts   = filename.replace('_model.joblib', '').rsplit('_h', 1)
            service = parts[0]
            hour    = int(parts[1])
            try:
                seasonal_models[service][hour] = joblib.load(path)
                loaded_sm += 1
            except Exception as e:
                print(f"  [{service}] h{hour:02d} seasonal model failed: {e}")

        # History
        elif filename.endswith('_history.json'):
            service = filename.replace('_history.json', '')
            try:
                with open(path) as f:
                    history[service] = json.load(f)
                loaded_h += 1
                print(f"  [{service}] history loaded ({len(history[service])} points) ✓")
            except Exception as e:
                print(f"  [{service}] failed to load history: {e}")

    print(f"\n📂 Loaded {loaded_m} global, {loaded_sm} seasonal models, "
          f"{loaded_h} histories\n")
    return loaded_m > 0   # True = skip bootstrap


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────
def detect_anomalies():
    print("🚀 AI Anomaly Detector v3 (Isolation Forest + Seasonality + Bootstrap)")
    print(f"   Check interval  : {CHECK_INTERVAL}s")
    print(f"   Min datapoints  : {MIN_DATAPOINTS}")
    print(f"   Retrain every   : {RETRAIN_EVERY} cycles")
    print(f"   Bootstrap hours : {BOOTSTRAP_HOURS}h")
    print(f"   Model dir       : {MODEL_DIR}\n")

    client = get_client()

    # ── 1. Try loading persisted state ──
    has_persisted = load_persisted_state()

    # ── 2. If no persisted models, bootstrap from ClickHouse history ──
    if not has_persisted:
        bootstrap_from_history(client)
    else:
        print("✓ Using persisted models — skipping bootstrap\n")

    print("🔍 Starting detection loop...\n")

    while True:
        try:
            service_features = extract_features(client)

            if not service_features:
                print("No logs in last minute — waiting...")
                time.sleep(CHECK_INTERVAL)
                continue

            current_hour = datetime.now(timezone.utc).hour

            for service, feature_vector in service_features.items():

                # Update rolling history
                history[service].append(feature_vector)
                if len(history[service]) > MAX_HISTORY:
                    history[service].pop(0)

                # Update seasonal history for this hour
                seasonal_history[service][current_hour].append(feature_vector)
                if len(seasonal_history[service][current_hour]) > MAX_HISTORY // 24:
                    seasonal_history[service][current_hour].pop(0)

                cycle_count[service] += 1

                # Retrain global model
                if (service not in models or
                        cycle_count[service] % RETRAIN_EVERY == 0):
                    trained = train_model(service)
                    if trained:
                        models[service] = trained

                # Retrain seasonal model for current hour
                if cycle_count[service] % RETRAIN_EVERY == 0:
                    sm = train_seasonal_model(service, current_hour)
                    if sm:
                        seasonal_models[service][current_hour] = sm

                score_and_alert(service, feature_vector, client)

            print(f"✓ Cycle {cycle_count.get(list(service_features.keys())[0], 0)} "
                  f"— monitoring {len(service_features)} services "
                  f"[hour={current_hour:02d}]")

        except Exception as e:
            print(f"❌ Error: {e}")
            try:
                client = get_client()
            except Exception:
                pass

        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    detect_anomalies()