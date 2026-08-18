-- Stocks Dashboard schema
-- Apply: psql -U stocks_app -d stocks -f schema.sql

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    sector VARCHAR(128),
    subsector VARCHAR(128),
    listing_date DATE,
    website TEXT,
    yahoo_symbol VARCHAR(32),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS daily_prices (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    open NUMERIC(18,2),
    high NUMERIC(18,2),
    low NUMERIC(18,2),
    close NUMERIC(18,2),
    previous_close NUMERIC(18,2),
    volume BIGINT,
    value NUMERIC(20,2),
    frequency BIGINT,
    UNIQUE (company_id, date)
);
CREATE INDEX IF NOT EXISTS idx_daily_prices_company_date ON daily_prices (company_id, date DESC);

CREATE TABLE IF NOT EXISTS intraday_prices (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    price NUMERIC(18,2),
    open NUMERIC(18,2),
    high NUMERIC(18,2),
    low NUMERIC(18,2),
    volume BIGINT,
    bid NUMERIC(18,2),
    offer NUMERIC(18,2),
    bid_volume BIGINT,
    offer_volume BIGINT,
    source VARCHAR(32) NOT NULL DEFAULT 'yahoo',
    UNIQUE (company_id, timestamp, source)
);
CREATE INDEX IF NOT EXISTS idx_intraday_company_ts ON intraday_prices (company_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS financial_statements (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    period DATE NOT NULL,
    period_type VARCHAR(16) NOT NULL CHECK (period_type IN ('quarterly', 'annual')),
    revenue NUMERIC(20,2),
    gross_profit NUMERIC(20,2),
    operating_profit NUMERIC(20,2),
    net_income NUMERIC(20,2),
    total_assets NUMERIC(20,2),
    total_liabilities NUMERIC(20,2),
    total_equity NUMERIC(20,2),
    cash NUMERIC(20,2),
    operating_cashflow NUMERIC(20,2),
    investing_cashflow NUMERIC(20,2),
    financing_cashflow NUMERIC(20,2),
    capex NUMERIC(20,2),
    eps NUMERIC(18,4),
    shares_outstanding NUMERIC(20,0),
    dividend_per_share NUMERIC(18,4),
    source VARCHAR(32) NOT NULL DEFAULT 'yahoo',
    UNIQUE (company_id, period, period_type, source)
);

CREATE TABLE IF NOT EXISTS financial_ratios (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    period DATE NOT NULL,
    period_type VARCHAR(16) NOT NULL CHECK (period_type IN ('quarterly', 'annual')),
    eps NUMERIC(18,4),
    per NUMERIC(18,4),
    pbv NUMERIC(18,4),
    roe NUMERIC(18,4),
    roa NUMERIC(18,4),
    der NUMERIC(18,4),
    npm NUMERIC(18,4),
    gross_margin NUMERIC(18,4),
    operating_margin NUMERIC(18,4),
    dividend_yield NUMERIC(18,4),
    revenue_growth NUMERIC(18,4),
    net_income_growth NUMERIC(18,4),
    source VARCHAR(32) NOT NULL DEFAULT 'yahoo',
    UNIQUE (company_id, period, period_type, source)
);

CREATE TABLE IF NOT EXISTS corporate_actions (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    action_type VARCHAR(64) NOT NULL,
    description TEXT,
    dividend NUMERIC(20,2),
    split_ratio NUMERIC(12,6),
    rights_issue TEXT,
    source VARCHAR(32) NOT NULL DEFAULT 'idx',
    UNIQUE (company_id, date, action_type, source)
);

CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT,
    source VARCHAR(64),
    published_at TIMESTAMPTZ,
    summary TEXT,
    content TEXT,
    UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_news_company_pub ON news (company_id, published_at DESC);

CREATE TABLE IF NOT EXISTS watchlists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL DEFAULT 'default',
    symbol VARCHAR(16) NOT NULL,
    note TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, symbol)
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(16),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    model VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_messages_conv ON ai_messages (conversation_id, id);

CREATE TABLE IF NOT EXISTS ai_analyses (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    symbol VARCHAR(16),
    model VARCHAR(128),
    provider VARCHAR(64),
    is_local BOOLEAN DEFAULT FALSE,
    request_type VARCHAR(32) NOT NULL,
    request_context JSONB,
    response TEXT,
    latency_ms INTEGER,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_request_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    model VARCHAR(128),
    provider VARCHAR(64),
    is_local BOOLEAN,
    request_type VARCHAR(32),
    symbol VARCHAR(16),
    latency_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ai_logs_ts ON ai_request_logs (timestamp DESC);

CREATE TABLE IF NOT EXISTS collector_logs (
    id BIGSERIAL PRIMARY KEY,
    collector VARCHAR(64) NOT NULL,
    level VARCHAR(16) NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_collector_logs_ts ON collector_logs (created_at DESC);
