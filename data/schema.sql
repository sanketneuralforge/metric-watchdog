-- data/schema.sql
-- Synthetic e-commerce schema for Metric Watchdog development

CREATE TABLE IF NOT EXISTS orders (
    order_id        SERIAL PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    customer_id     INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    category        VARCHAR(50) NOT NULL,
    channel         VARCHAR(30) NOT NULL,
    device_type     VARCHAR(20) NOT NULL,
    country         VARCHAR(30) NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      DECIMAL(10,2) NOT NULL,
    discount_pct    DECIMAL(5,2) NOT NULL DEFAULT 0,
    revenue         DECIMAL(10,2) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id      SERIAL PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    customer_id     INTEGER,
    device_type     VARCHAR(20) NOT NULL,
    channel         VARCHAR(30) NOT NULL,
    country         VARCHAR(30) NOT NULL,
    pages_viewed    INTEGER NOT NULL DEFAULT 1,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    converted       BOOLEAN NOT NULL DEFAULT FALSE,
    bounced         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id       SERIAL PRIMARY KEY,
    order_id        INTEGER REFERENCES orders(order_id),
    created_at      TIMESTAMP NOT NULL,
    reason          VARCHAR(50) NOT NULL,
    amount          DECIMAL(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_calendar (
    campaign_id     SERIAL PRIMARY KEY,
    campaign_name   VARCHAR(100) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    channel         VARCHAR(30),
    expected_uplift_pct DECIMAL(5,2)
);

CREATE TABLE IF NOT EXISTS metric_baselines (
    id              SERIAL PRIMARY KEY,
    metric_name     VARCHAR(100) NOT NULL,
    date            DATE NOT NULL,
    value           DECIMAL(12,4) NOT NULL,
    recorded_at     TIMESTAMP DEFAULT NOW(),
    UNIQUE(metric_name, date)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_category ON orders(category);
CREATE INDEX IF NOT EXISTS idx_orders_device ON orders(device_type);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_converted ON sessions(converted);
CREATE INDEX IF NOT EXISTS idx_refunds_created ON refunds(created_at);