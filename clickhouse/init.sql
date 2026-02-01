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
TTL timestamp + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;