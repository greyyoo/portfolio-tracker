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
    usd_krw_rate NUMERIC(10, 4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_indices_date ON market_indices(snapshot_date);

COMMENT ON TABLE market_indices IS 'Daily market indices (S&P 500, NASDAQ 100, KOSPI)';

-- ============================================
-- 6. CASH TRANSACTIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS cash_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('DEPOSIT', 'WITHDRAWAL', 'RP_INTEREST', 'ADJUSTMENT_INCREASE', 'ADJUSTMENT_DECREASE')),
    currency TEXT NOT NULL CHECK (currency IN ('KRW', 'USD')),
    amount NUMERIC(20, 2) NOT NULL CHECK (amount > 0),
    transaction_date DATE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cash_transactions_account ON cash_transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_cash_transactions_date ON cash_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_cash_transactions_currency ON cash_transactions(currency);
CREATE INDEX IF NOT EXISTS idx_cash_transactions_type ON cash_transactions(transaction_type);

COMMENT ON TABLE cash_transactions IS 'Cash deposits, withdrawals, RP interest, and balance adjustments';
COMMENT ON COLUMN cash_transactions.transaction_type IS 'DEPOSIT (입금), WITHDRAWAL (출금), RP_INTEREST (RP 이자), ADJUSTMENT_INCREASE (예수금 증가 조정), ADJUSTMENT_DECREASE (예수금 감소 조정)';
COMMENT ON COLUMN cash_transactions.amount IS 'Always positive - transaction type determines direction';

-- Currency restriction trigger for cash_transactions
CREATE OR REPLACE FUNCTION check_cash_transaction_currency()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM accounts
        WHERE id = NEW.account_id
        AND NEW.currency = ANY(allowed_currencies)
    ) THEN
        RAISE EXCEPTION 'Currency % is not allowed for this account', NEW.currency;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS validate_cash_transaction_currency ON cash_transactions;
CREATE TRIGGER validate_cash_transaction_currency
    BEFORE INSERT OR UPDATE ON cash_transactions
    FOR EACH ROW
    EXECUTE FUNCTION check_cash_transaction_currency();

-- ============================================
-- 7. DATABASE FUNCTIONS
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
    v_account_number INTEGER;
BEGIN
    v_total_value := p_stock_value + p_cash_balance;

    -- Get account number
    SELECT account_number INTO v_account_number
    FROM accounts
    WHERE id = p_account_id;

    -- Determine baseline value using FIXED values per account
    CASE v_account_number
        WHEN 1 THEN v_baseline := 20000;           -- USD
        WHEN 2 THEN v_baseline := 10000000;        -- KRW
        WHEN 3 THEN v_baseline := 4000;            -- USD
        WHEN 4 THEN v_baseline := 4000;            -- KRW or USD (모두 4000)
        WHEN 5 THEN v_baseline := 4000;            -- USD or KRW (모두 4000)
        ELSE v_baseline := v_total_value;          -- fallback
    END CASE;

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
        exchange_rate = COALESCE(EXCLUDED.exchange_rate, portfolio_snapshots.exchange_rate)
    RETURNING id INTO v_snapshot_id;

    RETURN v_snapshot_id;
END;
$$ LANGUAGE plpgsql;

-- Upsert market indices
CREATE OR REPLACE FUNCTION upsert_market_indices(
    p_snapshot_date DATE,
    p_spx_close NUMERIC DEFAULT NULL,
    p_ndx_close NUMERIC DEFAULT NULL,
    p_kospi_close NUMERIC DEFAULT NULL,
    p_usd_krw_rate NUMERIC DEFAULT NULL
)
RETURNS DATE AS $$
DECLARE
    v_date DATE;
BEGIN
    INSERT INTO market_indices (snapshot_date, spx_close, ndx_close, kospi_close, usd_krw_rate)
    VALUES (p_snapshot_date, p_spx_close, p_ndx_close, p_kospi_close, p_usd_krw_rate)
    ON CONFLICT (snapshot_date)
    DO UPDATE SET
        spx_close = COALESCE(EXCLUDED.spx_close, market_indices.spx_close),
        ndx_close = COALESCE(EXCLUDED.ndx_close, market_indices.ndx_close),
        kospi_close = COALESCE(EXCLUDED.kospi_close, market_indices.kospi_close),
        usd_krw_rate = COALESCE(EXCLUDED.usd_krw_rate, market_indices.usd_krw_rate),
        updated_at = NOW()
    RETURNING snapshot_date INTO v_date;

    RETURN v_date;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Calculate cash balance for a specific account, currency, and date
CREATE OR REPLACE FUNCTION calculate_cash_balance(
    p_account_id UUID,
    p_currency TEXT,
    p_date DATE
)
RETURNS NUMERIC AS $$
DECLARE
    v_initial_seed NUMERIC;
    v_cash_balance NUMERIC;
BEGIN
    -- Get initial seed money
    IF p_currency = 'KRW' THEN
        SELECT initial_seed_money_krw INTO v_initial_seed
        FROM accounts WHERE id = p_account_id;
    ELSE
        SELECT initial_seed_money_usd INTO v_initial_seed
        FROM accounts WHERE id = p_account_id;
    END IF;

    -- Calculate cash balance
    v_cash_balance := COALESCE(v_initial_seed, 0)
        + COALESCE((SELECT SUM(amount) FROM cash_transactions WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'DEPOSIT' AND transaction_date <= p_date), 0)
        + COALESCE((SELECT SUM(amount) FROM cash_transactions WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'RP_INTEREST' AND transaction_date <= p_date), 0)
        + COALESCE((SELECT SUM(amount) FROM cash_transactions WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'ADJUSTMENT_INCREASE' AND transaction_date <= p_date), 0)
        - COALESCE((SELECT SUM(amount) FROM cash_transactions WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'WITHDRAWAL' AND transaction_date <= p_date), 0)
        - COALESCE((SELECT SUM(amount) FROM cash_transactions WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'ADJUSTMENT_DECREASE' AND transaction_date <= p_date), 0)
        - COALESCE((SELECT SUM((trade_price * quantity) + COALESCE(fee, 0)) FROM transactions WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'BUY' AND transaction_date <= p_date), 0)
        + COALESCE((SELECT SUM((trade_price * quantity) - COALESCE(fee, 0)) FROM transactions WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'SELL' AND transaction_date <= p_date), 0);

    RETURN v_cash_balance;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_cash_balance(UUID, TEXT, DATE) IS 'Calculates cash balance = initial seed + deposits + RP interest + adjustments(+) - withdrawals - adjustments(-) - stock invested + stock sold';

-- 2-param overload of calculate_cash_balance (uses CURRENT_DATE)
CREATE OR REPLACE FUNCTION calculate_cash_balance(
    p_account_id UUID,
    p_currency TEXT
)
RETURNS NUMERIC AS $$
BEGIN
    RETURN calculate_cash_balance(p_account_id, p_currency, CURRENT_DATE);
END;
$$ LANGUAGE plpgsql;

-- Get cash transaction summary for an account
CREATE OR REPLACE FUNCTION get_cash_transaction_summary(
    p_account_id UUID,
    p_currency TEXT
)
RETURNS TABLE (
    initial_seed NUMERIC,
    total_deposits NUMERIC,
    total_withdrawals NUMERIC,
    total_rp_interest NUMERIC,
    total_adjustments_increase NUMERIC,
    total_adjustments_decrease NUMERIC,
    stock_invested NUMERIC,
    current_cash_balance NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN p_currency = 'KRW' THEN a.initial_seed_money_krw
            ELSE a.initial_seed_money_usd
        END as initial_seed,
        COALESCE(
            (SELECT SUM(amount) FROM cash_transactions
             WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'DEPOSIT'),
            0
        ) as total_deposits,
        COALESCE(
            (SELECT SUM(amount) FROM cash_transactions
             WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'WITHDRAWAL'),
            0
        ) as total_withdrawals,
        COALESCE(
            (SELECT SUM(amount) FROM cash_transactions
             WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'RP_INTEREST'),
            0
        ) as total_rp_interest,
        COALESCE(
            (SELECT SUM(amount) FROM cash_transactions
             WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'ADJUSTMENT_INCREASE'),
            0
        ) as total_adjustments_increase,
        COALESCE(
            (SELECT SUM(amount) FROM cash_transactions
             WHERE account_id = p_account_id AND currency = p_currency AND transaction_type = 'ADJUSTMENT_DECREASE'),
            0
        ) as total_adjustments_decrease,
        COALESCE(
            (SELECT SUM(CASE
                WHEN transaction_type = 'BUY' THEN (trade_price * quantity) + COALESCE(fee, 0)
                WHEN transaction_type = 'SELL' THEN -((trade_price * quantity) - COALESCE(fee, 0))
             END)
             FROM transactions
             WHERE account_id = p_account_id AND currency = p_currency),
            0
        )::NUMERIC as stock_invested,
        calculate_cash_balance(p_account_id, p_currency) as current_cash_balance
    FROM accounts a
    WHERE a.id = p_account_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_cash_transaction_summary(UUID, TEXT) IS 'Returns comprehensive cash transaction summary including adjustment types';

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
    p_end_date DATE DEFAULT NULL
)
RETURNS TABLE(snapshot_id UUID, account_name TEXT, snapshot_date DATE, currency TEXT) AS $$
DECLARE
    v_end_date DATE;
    v_date DATE;
    v_account RECORD;
    v_snapshot_id UUID;
    v_stock_value NUMERIC;
    v_cash_balance NUMERIC;
    v_exchange_rate NUMERIC;
BEGIN
    -- Default end date to start date if not provided
    v_end_date := COALESCE(p_end_date, p_start_date);

    -- Loop through each date in range
    v_date := p_start_date;
    WHILE v_date <= v_end_date LOOP
        -- Get exchange rate for this specific date from market_indices
        -- Priority: 1) Existing snapshot, 2) market_indices for date, 3) Latest market_indices value
        SELECT ps.exchange_rate INTO v_exchange_rate
        FROM portfolio_snapshots ps
        WHERE ps.snapshot_date = v_date
          AND ps.exchange_rate IS NOT NULL
        LIMIT 1;

        -- If no saved exchange rate, get from market_indices for this date
        IF v_exchange_rate IS NULL THEN
            SELECT mi.usd_krw_rate INTO v_exchange_rate
            FROM market_indices mi
            WHERE mi.snapshot_date = v_date
              AND mi.usd_krw_rate IS NOT NULL
            LIMIT 1;
        END IF;

        -- If still no rate (market not open that day), get most recent available rate
        IF v_exchange_rate IS NULL THEN
            SELECT mi.usd_krw_rate INTO v_exchange_rate
            FROM market_indices mi
            WHERE mi.snapshot_date <= v_date
              AND mi.usd_krw_rate IS NOT NULL
            ORDER BY mi.snapshot_date DESC
            LIMIT 1;
        END IF;

        -- Final fallback if no historical data exists
        IF v_exchange_rate IS NULL THEN
            v_exchange_rate := 1420;
        END IF;
        -- Process each active account
        FOR v_account IN
            SELECT a.id, a.account_name, a.allowed_currencies
            FROM accounts a
            WHERE a.is_active = true
        LOOP
            -- Process KRW currency if allowed
            IF 'KRW' = ANY(v_account.allowed_currencies) THEN
                -- Calculate stock value for KRW holdings at this date
                SELECT COALESCE(SUM(
                    CASE
                        WHEN t.transaction_type = 'BUY' THEN sp.current_price * t.quantity
                        WHEN t.transaction_type = 'SELL' THEN -sp.current_price * t.quantity
                    END
                ), 0) INTO v_stock_value
                FROM transactions t
                LEFT JOIN stock_prices sp ON t.ticker = sp.ticker
                WHERE t.account_id = v_account.id
                  AND t.currency = 'KRW'
                  AND t.transaction_date <= v_date;

                -- Calculate cash balance (using database function)
                SELECT calculate_cash_balance(v_account.id, 'KRW', v_date) INTO v_cash_balance;

                -- Capture snapshot for KRW
                SELECT capture_portfolio_snapshot(
                    v_account.id,
                    v_date,
                    'KRW',
                    v_stock_value,
                    v_cash_balance,
                    NULL,  -- p_baseline_value (let function determine)
                    v_exchange_rate  -- p_exchange_rate
                ) INTO v_snapshot_id;

                snapshot_id := v_snapshot_id;
                account_name := v_account.account_name;
                snapshot_date := v_date;
                currency := 'KRW';
                RETURN NEXT;
            END IF;

            -- Process USD currency if allowed
            IF 'USD' = ANY(v_account.allowed_currencies) THEN
                -- Calculate stock value for USD holdings at this date
                SELECT COALESCE(SUM(
                    CASE
                        WHEN t.transaction_type = 'BUY' THEN sp.current_price * t.quantity
                        WHEN t.transaction_type = 'SELL' THEN -sp.current_price * t.quantity
                    END
                ), 0) INTO v_stock_value
                FROM transactions t
                LEFT JOIN stock_prices sp ON t.ticker = sp.ticker
                WHERE t.account_id = v_account.id
                  AND t.currency = 'USD'
                  AND t.transaction_date <= v_date;

                -- Calculate cash balance (using database function)
                SELECT calculate_cash_balance(v_account.id, 'USD', v_date) INTO v_cash_balance;

                -- Capture snapshot for USD
                SELECT capture_portfolio_snapshot(
                    v_account.id,
                    v_date,
                    'USD',
                    v_stock_value,
                    v_cash_balance,
                    NULL,  -- p_baseline_value (let function determine)
                    v_exchange_rate  -- p_exchange_rate (reference value)
                ) INTO v_snapshot_id;

                snapshot_id := v_snapshot_id;
                account_name := v_account.account_name;
                snapshot_date := v_date;
                currency := 'USD';
                RETURN NEXT;
            END IF;
        END LOOP;

        -- Move to next date
        v_date := v_date + INTERVAL '1 day';
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
