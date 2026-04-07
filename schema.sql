CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    avg_buy_price NUMERIC NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, symbol)
);

CREATE TABLE IF NOT EXISTS investment_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    risk_tolerance INTEGER NOT NULL CHECK (risk_tolerance BETWEEN 1 AND 10),
    investment_horizon TEXT NOT NULL CHECK (investment_horizon IN ('corto', 'mediano', 'largo')),
    max_position_pct NUMERIC NOT NULL CHECK (max_position_pct > 0 AND max_position_pct <= 100),
    max_country_pct NUMERIC NOT NULL CHECK (max_country_pct > 0 AND max_country_pct <= 100),
    max_sector_pct NUMERIC NOT NULL CHECK (max_sector_pct > 0 AND max_sector_pct <= 100),
    max_drawdown_pct NUMERIC NOT NULL CHECK (max_drawdown_pct >= 0 AND max_drawdown_pct <= 100),
    preferred_strategy TEXT NOT NULL CHECK (preferred_strategy IN ('growth', 'dividendos', 'valor', 'mixta')),
    cash_buffer_pct NUMERIC NOT NULL CHECK (cash_buffer_pct >= 0 AND cash_buffer_pct <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_investment_profiles_updated_at ON investment_profiles(updated_at);

RESET ROLE;