CREATE DATABASE IF NOT EXISTS logs;

CREATE TABLE IF NOT EXISTS logs.logs (
    timestamp DateTime64(3),
    level LowCardinality(String),
    service LowCardinality(String),
    host String,
    environment LowCardinality(String),
    message String,
    trace_id String,
    user_id String,
    
    INDEX idx_trace trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_user user_id TYPE bloom_filter GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (service, level, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS logs.anomalies (
    detected_at   DateTime64(3),
    service       LowCardinality(String),
    confidence    Float32,
    raw_score     Float32,
    error_count   Int32,
    warn_count    Int32,
    total_logs    Int32,
    error_ratio   Float32,
    unique_hosts  Int32
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(detected_at)
ORDER BY (service, detected_at)
TTL toDateTime(detected_at) + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;