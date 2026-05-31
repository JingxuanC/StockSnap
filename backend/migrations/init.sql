-- StockSnap 数据库初始化

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    openid VARCHAR(100) UNIQUE NOT NULL,
    nickname VARCHAR(100),
    avatar_url VARCHAR(500),
    is_subscribed BOOLEAN DEFAULT FALSE,
    subscription_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_openid ON users(openid);

CREATE TABLE IF NOT EXISTS analysis_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    market VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    company_name VARCHAR(200),
    report_json JSONB,
    report_markdown TEXT,
    score INTEGER,
    rating VARCHAR(20),
    model VARCHAR(50) DEFAULT 'deepseek',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_analysis_user_id ON analysis_records(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_created_at ON analysis_records(created_at DESC);

CREATE TABLE IF NOT EXISTS user_quota (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    period_start DATE NOT NULL,
    analysis_used INTEGER DEFAULT 0,
    analysis_limit INTEGER DEFAULT 20,
    backtest_used INTEGER DEFAULT 0,
    backtest_limit INTEGER DEFAULT 20,
    UNIQUE(user_id, period_start)
);
CREATE INDEX IF NOT EXISTS idx_quota_user_period ON user_quota(user_id, period_start);

CREATE TABLE IF NOT EXISTS backtest_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    market VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(100),
    params_json JSONB,
    result_json JSONB,
    equity_curve_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_backtest_user_id ON backtest_records(user_id);

CREATE TABLE IF NOT EXISTS subscription_orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    order_type VARCHAR(20) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'paid',
    paid_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
