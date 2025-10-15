-- ============================================
-- Complete Database Schema for Trading Portfolio Tracker
-- 최종 통합 스키마 (2025-10-14)
-- ============================================

-- ============================================
-- 1. ACCOUNTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_number INTEGER UNIQUE NOT NULL CHECK (account_number BETWEEN 1 AND 5),
    account_name TEXT NOT NULL,
    strategy_description TEXT,
    allowed_currencies TEXT[] NOT NULL DEFAULT ARRAY['USD', 'KRW'],
    initial_seed_money_krw NUMERIC(15, 2) DEFAULT 0,
    initial_seed_money_usd NUMERIC(15, 2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_accounts_number ON accounts(account_number);
CREATE INDEX IF NOT EXISTS idx_accounts_active ON accounts(is_active);

COMMENT ON TABLE accounts IS 'Investment accounts with multi-currency support';
COMMENT ON COLUMN accounts.allowed_currencies IS 'Array of allowed currencies: KRW and/or USD';

-- ============================================
-- 2. TRANSACTIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    transaction_date DATE NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
    ticker TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    country TEXT NOT NULL CHECK (country IN ('Korea', 'USA')),
    currency TEXT NOT NULL CHECK (currency IN ('KRW', 'USD')),
    trade_price NUMERIC(15, 2) NOT NULL CHECK (trade_price > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    fee NUMERIC(15, 2) DEFAULT 0 CHECK (fee >= 0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_ticker ON transactions(ticker);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_currency ON transactions(currency);

COMMENT ON TABLE transactions IS 'Stock buy/sell transactions';
COMMENT ON COLUMN transactions.currency IS 'Auto-populated based on country: Korea → KRW, USA → USD';

-- Currency restriction trigger
CREATE OR REPLACE FUNCTION check_currency_restriction()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT (NEW.currency = ANY(
        SELECT allowed_currencies FROM accounts WHERE id = NEW.account_id
    )) THEN
        RAISE EXCEPTION 'Currency % is not allowed for this account', NEW.currency;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_currency_restriction ON transactions;
CREATE TRIGGER enforce_currency_restriction
    BEFORE INSERT OR UPDATE ON transactions
    FOR EACH ROW
    EXECUTE FUNCTION check_currency_restriction();

-- ============================================
-- 3. STOCK PRICES TABLE (Price Cache)
-- ============================================
CREATE TABLE IF NOT EXISTS stock_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL UNIQUE,
    current_price NUMERIC(15, 2) NOT NULL,
    currency TEXT NOT NULL CHECK (currency IN ('KRW', 'USD')),
    is_active BOOLEAN DEFAULT true,
    fetch_error TEXT,
    retry_count INTEGER DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker ON stock_prices(ticker);
CREATE INDEX IF NOT EXISTS idx_stock_prices_active ON stock_prices(is_active);
CREATE INDEX IF NOT EXISTS idx_stock_prices_updated ON stock_prices(last_updated);

COMMENT ON TABLE stock_prices IS 'Cached stock prices updated by Edge Function';

-- ============================================
-- 4. PORTFOLIO SNAPSHOTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    currency TEXT NOT NULL CHECK (currency IN ('KRW', 'USD')),
    stock_value NUMERIC(15, 2) DEFAULT 0,
    cash_balance NUMERIC(15, 2) DEFAULT 0,
    total_value NUMERIC(15, 2) DEFAULT 0,
    baseline_value NUMERIC(15, 2) DEFAULT 0,
    value_change NUMERIC(15, 2) DEFAULT 0,
    change_pct NUMERIC(10, 4) DEFAULT 0,
    exchange_rate NUMERIC(10, 4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(account_id, snapshot_date, currency)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_account ON portfolio_snapshots(account_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON portfolio_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_currency ON portfolio_snapshots(currency);

COMMENT ON TABLE portfolio_snapshots IS 'Daily portfolio valuation snapshots';
COMMENT ON COLUMN portfolio_snapshots.baseline_value IS 'Reference value for calculating change (typically from 2025-10-13)';

-- ============================================
-- 5. MARKET INDICES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS market_indices (
    snapshot_date DATE PRIMARY KEY,
    spx_close NUMERIC(10, 2),
    ndx_close NUMERIC(10, 2),
    kospi_close NUMERIC(10, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_indices_date ON market_indices(snapshot_date);

COMMENT ON TABLE market_indices IS 'Daily market indices (S&P 500, NASDAQ 100, KOSPI)';

-- ============================================
-- 6. DATABASE FUNCTIONS
-- ============================================

-- Get active tickers with holdings
CREATE OR REPLACE FUNCTION get_active_tickers()
RETURNS TABLE (
    account_id UUID,
    ticker TEXT,
    currency TEXT,
    net_quantity NUMERIC
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.account_id,
        t.ticker,
        t.currency,
        SUM(
            CASE
                WHEN t.transaction_type = 'BUY' THEN t.quantity
                WHEN t.transaction_type = 'SELL' THEN -t.quantity
            END
        )::NUMERIC as net_quantity
    FROM transactions t
    GROUP BY t.account_id, t.ticker, t.currency
    HAVING SUM(
        CASE
            WHEN t.transaction_type = 'BUY' THEN t.quantity
            WHEN t.transaction_type = 'SELL' THEN -t.quantity
        END
    ) > 0;
END;
$$;

-- Capture portfolio snapshot
CREATE OR REPLACE FUNCTION capture_portfolio_snapshot(
    p_account_id UUID,
    p_snapshot_date DATE,
    p_currency TEXT,
    p_stock_value NUMERIC,
    p_cash_balance NUMERIC,
    p_baseline_value NUMERIC DEFAULT NULL,
    p_exchange_rate NUMERIC DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_snapshot_id UUID;
    v_total_value NUMERIC;
    v_baseline NUMERIC;
    v_value_change NUMERIC;
    v_change_pct NUMERIC;
BEGIN
    v_total_value := p_stock_value + p_cash_balance;

    -- Use provided baseline or fetch from first snapshot
    IF p_baseline_value IS NOT NULL THEN
        v_baseline := p_baseline_value;
    ELSE
        SELECT baseline_value INTO v_baseline
        FROM portfolio_snapshots
        WHERE account_id = p_account_id
          AND currency = p_currency
        ORDER BY snapshot_date ASC
        LIMIT 1;

        IF v_baseline IS NULL THEN
            v_baseline := v_total_value;
        END IF;
    END IF;

    -- Calculate change
    v_value_change := v_total_value - v_baseline;
    v_change_pct := CASE
        WHEN v_baseline > 0 THEN (v_value_change / v_baseline) * 100
        ELSE 0
    END;

    -- Upsert snapshot
    INSERT INTO portfolio_snapshots (
        account_id, snapshot_date, currency,
        stock_value, cash_balance, total_value,
        baseline_value, value_change, change_pct,
        exchange_rate
    )
    VALUES (
        p_account_id, p_snapshot_date, p_currency,
        p_stock_value, p_cash_balance, v_total_value,
        v_baseline, v_value_change, v_change_pct,
        p_exchange_rate
    )
    ON CONFLICT (account_id, snapshot_date, currency)
    DO UPDATE SET
        stock_value = EXCLUDED.stock_value,
        cash_balance = EXCLUDED.cash_balance,
        total_value = EXCLUDED.total_value,
        baseline_value = EXCLUDED.baseline_value,
        value_change = EXCLUDED.value_change,
        change_pct = EXCLUDED.change_pct,
        exchange_rate = COALESCE(EXCLUDED.exchange_rate, portfolio_snapshots.exchange_rate),
        updated_at = NOW()
    RETURNING id INTO v_snapshot_id;

    RETURN v_snapshot_id;
END;
$$ LANGUAGE plpgsql;

-- Upsert market indices
CREATE OR REPLACE FUNCTION upsert_market_indices(
    p_snapshot_date DATE,
    p_spx_close NUMERIC DEFAULT NULL,
    p_ndx_close NUMERIC DEFAULT NULL,
    p_kospi_close NUMERIC DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO market_indices (snapshot_date, spx_close, ndx_close, kospi_close)
    VALUES (p_snapshot_date, p_spx_close, p_ndx_close, p_kospi_close)
    ON CONFLICT (snapshot_date)
    DO UPDATE SET
        spx_close = COALESCE(EXCLUDED.spx_close, market_indices.spx_close),
        ndx_close = COALESCE(EXCLUDED.ndx_close, market_indices.ndx_close),
        kospi_close = COALESCE(EXCLUDED.kospi_close, market_indices.kospi_close),
        updated_at = NOW()
    RETURNING snapshot_date INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Get portfolio history for specific account
CREATE OR REPLACE FUNCTION get_portfolio_history(
    p_account_id UUID,
    p_currency TEXT,
    p_days INTEGER DEFAULT 90
)
RETURNS TABLE (
    snapshot_date DATE,
    stock_value NUMERIC,
    cash_balance NUMERIC,
    total_value NUMERIC,
    baseline_value NUMERIC,
    value_change NUMERIC,
    change_pct NUMERIC,
    exchange_rate NUMERIC,
    account_id UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ps.snapshot_date,
        ps.stock_value,
        ps.cash_balance,
        ps.total_value,
        ps.baseline_value,
        ps.value_change,
        ps.change_pct,
        ps.exchange_rate,
        ps.account_id
    FROM portfolio_snapshots ps
    WHERE ps.account_id = p_account_id
      AND ps.currency = p_currency
      AND ps.snapshot_date >= CURRENT_DATE - p_days
    ORDER BY ps.snapshot_date ASC;
END;
$$ LANGUAGE plpgsql;

-- Get aggregate portfolio history across all accounts
CREATE OR REPLACE FUNCTION get_aggregate_portfolio_history(
    p_days INTEGER DEFAULT 90
)
RETURNS TABLE (
    snapshot_date DATE,
    total_value NUMERIC,
    total_value_change NUMERIC,
    avg_change_pct NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ps.snapshot_date,
        SUM(ps.total_value) as total_value,
        SUM(ps.value_change) as total_value_change,
        AVG(ps.change_pct) as avg_change_pct
    FROM portfolio_snapshots ps
    WHERE ps.snapshot_date >= CURRENT_DATE - p_days
    GROUP BY ps.snapshot_date
    ORDER BY ps.snapshot_date ASC;
END;
$$ LANGUAGE plpgsql;

-- Recalculate snapshots for a date range
CREATE OR REPLACE FUNCTION recalculate_snapshots(
    p_start_date DATE,
    p_end_date DATE DEFAULT CURRENT_DATE,
    p_account_id UUID DEFAULT NULL
)
RETURNS TABLE (
    recalculated_date DATE,
    result_account_id UUID,
    result_currency TEXT,
    result_snapshot_id UUID
) AS $$
DECLARE
    v_account RECORD;
    v_date DATE;
    v_stock_value NUMERIC;
    v_cash_balance NUMERIC;
    v_exchange_rate NUMERIC;
    v_snapshot_id UUID;
BEGIN
    -- Validate date range
    IF p_start_date > p_end_date THEN
        RAISE EXCEPTION 'Start date must be before or equal to end date';
    END IF;

    -- Get exchange rate (use latest available or 1300 as fallback)
    SELECT COALESCE(
        (SELECT current_price FROM stock_prices WHERE ticker = 'KRW=X' AND is_active = true LIMIT 1),
        1300
    ) INTO v_exchange_rate;

    -- Loop through each account (or specific account if provided)
    FOR v_account IN
        SELECT a.id, a.initial_seed_money_krw, a.initial_seed_money_usd, a.allowed_currencies
        FROM accounts a
        WHERE (p_account_id IS NULL OR a.id = p_account_id)
          AND a.is_active = true
    LOOP
        -- Loop through each date in range
        v_date := p_start_date;
        WHILE v_date <= p_end_date LOOP
            -- Process each currency for this account
            IF 'KRW' = ANY(v_account.allowed_currencies) THEN
                -- Calculate KRW stock value at this date
                SELECT COALESCE(SUM(
                    CASE
                        WHEN net_qty > 0 THEN net_qty * COALESCE(pc.current_price, 0)
                        ELSE 0
                    END
                ), 0)
                INTO v_stock_value
                FROM (
                    SELECT
                        t.ticker,
                        SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.quantity ELSE -t.quantity END) as net_qty
                    FROM transactions t
                    WHERE t.account_id = v_account.id
                      AND t.currency = 'KRW'
                      AND t.transaction_date <= v_date
                    GROUP BY t.ticker
                ) holdings
                LEFT JOIN stock_prices pc ON holdings.ticker = pc.ticker;

                -- Calculate KRW cash balance at this date
                v_cash_balance := v_account.initial_seed_money_krw
                    + COALESCE((
                        SELECT SUM(ct.amount)
                        FROM cash_transactions ct
                        WHERE ct.account_id = v_account.id
                          AND ct.currency = 'KRW'
                          AND ct.transaction_type = 'DEPOSIT'
                          AND ct.transaction_date <= v_date
                    ), 0)
                    + COALESCE((
                        SELECT SUM(ct.amount)
                        FROM cash_transactions ct
                        WHERE ct.account_id = v_account.id
                          AND ct.currency = 'KRW'
                          AND ct.transaction_type = 'RP_INTEREST'
                          AND ct.transaction_date <= v_date
                    ), 0)
                    - COALESCE((
                        SELECT SUM(ct.amount)
                        FROM cash_transactions ct
                        WHERE ct.account_id = v_account.id
                          AND ct.currency = 'KRW'
                          AND ct.transaction_type = 'WITHDRAWAL'
                          AND ct.transaction_date <= v_date
                    ), 0)
                    - COALESCE((
                        SELECT SUM((t.trade_price * t.quantity) + COALESCE(t.fee, 0))
                        FROM transactions t
                        WHERE t.account_id = v_account.id
                          AND t.currency = 'KRW'
                          AND t.transaction_type = 'BUY'
                          AND t.transaction_date <= v_date
                    ), 0)
                    + COALESCE((
                        SELECT SUM((t.trade_price * t.quantity) - COALESCE(t.fee, 0))
                        FROM transactions t
                        WHERE t.account_id = v_account.id
                          AND t.currency = 'KRW'
                          AND t.transaction_type = 'SELL'
                          AND t.transaction_date <= v_date
                    ), 0);

                -- Capture KRW snapshot
                SELECT capture_portfolio_snapshot(
                    v_account.id,
                    v_date,
                    'KRW',
                    v_stock_value,
                    v_cash_balance,
                    v_exchange_rate
                ) INTO v_snapshot_id;

                RETURN QUERY SELECT v_date AS recalculated_date, v_account.id AS result_account_id, 'KRW'::TEXT AS result_currency, v_snapshot_id AS result_snapshot_id;
            END IF;

            IF 'USD' = ANY(v_account.allowed_currencies) THEN
                -- Calculate USD stock value at this date
                SELECT COALESCE(SUM(
                    CASE
                        WHEN net_qty > 0 THEN net_qty * COALESCE(pc.current_price, 0)
                        ELSE 0
                    END
                ), 0)
                INTO v_stock_value
                FROM (
                    SELECT
                        t.ticker,
                        SUM(CASE WHEN t.transaction_type = 'BUY' THEN t.quantity ELSE -t.quantity END) as net_qty
                    FROM transactions t
                    WHERE t.account_id = v_account.id
                      AND t.currency = 'USD'
                      AND t.transaction_date <= v_date
                    GROUP BY t.ticker
                ) holdings
                LEFT JOIN stock_prices pc ON holdings.ticker = pc.ticker;

                -- Calculate USD cash balance at this date
                v_cash_balance := v_account.initial_seed_money_usd
                    + COALESCE((
                        SELECT SUM(ct.amount)
                        FROM cash_transactions ct
                        WHERE ct.account_id = v_account.id
                          AND ct.currency = 'USD'
                          AND ct.transaction_type = 'DEPOSIT'
                          AND ct.transaction_date <= v_date
                    ), 0)
                    + COALESCE((
                        SELECT SUM(ct.amount)
                        FROM cash_transactions ct
                        WHERE ct.account_id = v_account.id
                          AND ct.currency = 'USD'
                          AND ct.transaction_type = 'RP_INTEREST'
                          AND ct.transaction_date <= v_date
                    ), 0)
                    - COALESCE((
                        SELECT SUM(ct.amount)
                        FROM cash_transactions ct
                        WHERE ct.account_id = v_account.id
                          AND ct.currency = 'USD'
                          AND ct.transaction_type = 'WITHDRAWAL'
                          AND ct.transaction_date <= v_date
                    ), 0)
                    - COALESCE((
                        SELECT SUM((t.trade_price * t.quantity) + COALESCE(t.fee, 0))
                        FROM transactions t
                        WHERE t.account_id = v_account.id
                          AND t.currency = 'USD'
                          AND t.transaction_type = 'BUY'
                          AND t.transaction_date <= v_date
                    ), 0)
                    + COALESCE((
                        SELECT SUM((t.trade_price * t.quantity) - COALESCE(t.fee, 0))
                        FROM transactions t
                        WHERE t.account_id = v_account.id
                          AND t.currency = 'USD'
                          AND t.transaction_type = 'SELL'
                          AND t.transaction_date <= v_date
                    ), 0);

                -- Capture USD snapshot
                SELECT capture_portfolio_snapshot(
                    v_account.id,
                    v_date,
                    'USD',
                    v_stock_value,
                    v_cash_balance,
                    v_exchange_rate
                ) INTO v_snapshot_id;

                RETURN QUERY SELECT v_date AS recalculated_date, v_account.id AS result_account_id, 'USD'::TEXT AS result_currency, v_snapshot_id AS result_snapshot_id;
            END IF;

            v_date := v_date + INTERVAL '1 day';
        END LOOP;
    END LOOP;

    RETURN;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION recalculate_snapshots IS 'Recalculate portfolio snapshots for a date range. Useful when updating historical transactions or cash flows.';

-- ============================================
-- 7. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_indices ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_transactions ENABLE ROW LEVEL SECURITY;

-- Public read-only access policies
CREATE POLICY "Allow public read access to accounts"
    ON accounts FOR SELECT
    TO public
    USING (true);

CREATE POLICY "Allow public read access to transactions"
    ON transactions FOR SELECT
    TO public
    USING (true);

CREATE POLICY "Allow public read access to stock_prices"
    ON stock_prices FOR SELECT
    TO public
    USING (true);

CREATE POLICY "Allow public read access to cash_transactions"
    ON cash_transactions FOR SELECT
    TO public
    USING (true);

CREATE POLICY "Allow public read access to portfolio_snapshots"
    ON portfolio_snapshots FOR SELECT
    TO public
    USING (true);

CREATE POLICY "Allow public read access to market_indices"
    ON market_indices FOR SELECT
    TO public
    USING (true);

-- ============================================
-- 8. INITIAL DATA (Sample Data - Modify as Needed)
-- ============================================

-- Insert 5 sample accounts (if not exists)
-- NOTE: These are example accounts. Modify account names and initial amounts for your use case.
INSERT INTO accounts (account_number, account_name, allowed_currencies, initial_seed_money_krw, initial_seed_money_usd)
VALUES
    (1, 'Account 1 - US Stocks', ARRAY['USD'], 0, 10000),
    (2, 'Account 2 - KR Stocks', ARRAY['KRW'], 5000000, 0),
    (3, 'Account 3 - Growth Portfolio', ARRAY['USD'], 0, 5000),
    (4, 'Account 4 - Value Portfolio', ARRAY['USD'], 0, 5000),
    (5, 'Account 5 - Global Mix', ARRAY['USD', 'KRW'], 2000000, 3000)
ON CONFLICT (account_number) DO NOTHING;

-- Insert baseline market indices data (example date)
-- NOTE: Replace with your baseline date and actual market close values
-- This serves as the 1.0 baseline for normalized performance comparison
INSERT INTO market_indices (snapshot_date, spx_close, ndx_close, kospi_close)
VALUES (CURRENT_DATE, 6656.00, 24800.00, 3584.55)
ON CONFLICT (snapshot_date) DO UPDATE SET
    spx_close = EXCLUDED.spx_close,
    ndx_close = EXCLUDED.ndx_close,
    kospi_close = EXCLUDED.kospi_close;

-- ============================================
-- 9. VERIFICATION QUERIES
-- ============================================

-- Verify schema
SELECT 'Accounts' as table_name, COUNT(*) as count FROM accounts
UNION ALL
SELECT 'Transactions', COUNT(*) FROM transactions
UNION ALL
SELECT 'Stock Prices Cache', COUNT(*) FROM stock_prices
UNION ALL
SELECT 'Portfolio Snapshots', COUNT(*) FROM portfolio_snapshots
UNION ALL
SELECT 'Market Indices', COUNT(*) FROM market_indices;

-- Verify functions
SELECT routine_name
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_type = 'FUNCTION'
  AND routine_name IN (
    'get_active_tickers',
    'capture_portfolio_snapshot',
    'upsert_market_indices',
    'get_portfolio_history',
    'get_aggregate_portfolio_history',
    'check_currency_restriction'
  )
ORDER BY routine_name;

COMMENT ON SCHEMA public IS 'Trading Portfolio Tracker - Complete Schema v1.0 (2025-10-14)';
