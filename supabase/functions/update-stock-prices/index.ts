// ============================================
// Supabase Edge Function: Update Stock Prices & Portfolio Snapshots
// ============================================
// Purpose: Fetch current prices for active holdings, cache in database, and capture daily portfolio snapshots
// Schedule: Runs twice daily via cron (after market close)
// API: Yahoo Finance API (free, no API key required)

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.4";

// Types
interface ActiveTicker {
  ticker: string;
  currency: string;
  net_quantity: number;
}

interface PriceResult {
  ticker: string;
  price: number | null;
  currency: string;
  error: string | null;
}

interface Account {
  id: string;
  account_number: number;
  account_name: string;
  initial_seed_money_krw: number;
  initial_seed_money_usd: number;
  allowed_currencies: string[];
}

// ============================================
// Yahoo Finance API Client
// ============================================
async function fetchYahooPrice(ticker: string): Promise<number | null> {
  try {
    // Yahoo Finance v8 API endpoint
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}`;
    const response = await fetch(url);

    if (!response.ok) {
      console.error(`Yahoo Finance API error for ${ticker}: ${response.status}`);
      return null;
    }

    const data = await response.json();

    // Extract current price from response
    const result = data?.chart?.result?.[0];
    if (!result) {
      console.error(`No data in Yahoo Finance response for ${ticker}`);
      return null;
    }

    // Get the latest close price
    const meta = result.meta;
    const currentPrice = meta?.regularMarketPrice || meta?.previousClose;

    if (currentPrice && currentPrice > 0) {
      return currentPrice;
    }

    console.error(`Invalid price data for ${ticker}: ${currentPrice}`);
    return null;
  } catch (error) {
    console.error(`Error fetching price for ${ticker}:`, error);
    return null;
  }
}

// Fetch USD/KRW exchange rate
async function fetchExchangeRate(): Promise<number> {
  try {
    const ticker = "KRW=X";
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}`;
    const response = await fetch(url);

    if (!response.ok) {
      console.error(`Exchange rate API error: ${response.status}`);
      return 1300; // Fallback rate
    }

    const data = await response.json();
    const result = data?.chart?.result?.[0];
    const meta = result?.meta;
    const rate = meta?.regularMarketPrice || meta?.previousClose;

    if (rate && rate > 0) {
      return rate;
    }

    return 1300; // Fallback rate
  } catch (error) {
    console.error("Error fetching exchange rate:", error);
    return 1300; // Fallback rate
  }
}

// Fetch market indices (SPX, NDX, KOSPI)
interface MarketIndices {
  spx: number | null;
  ndx: number | null;
  kospi: number | null;
}

async function fetchMarketIndices(): Promise<MarketIndices> {
  const indices = {
    spx: null as number | null,
    ndx: null as number | null,
    kospi: null as number | null,
  };

  // Fetch S&P 500 (^GSPC)
  try {
    const spxPrice = await fetchYahooPrice("^GSPC");
    if (spxPrice) indices.spx = spxPrice;
  } catch (error) {
    console.error("Error fetching SPX:", error);
  }

  // Fetch NASDAQ 100 (^NDX)
  try {
    const ndxPrice = await fetchYahooPrice("^NDX");
    if (ndxPrice) indices.ndx = ndxPrice;
  } catch (error) {
    console.error("Error fetching NDX:", error);
  }

  // Fetch KOSPI (^KS11)
  try {
    const kospiPrice = await fetchYahooPrice("^KS11");
    if (kospiPrice) indices.kospi = kospiPrice;
  } catch (error) {
    console.error("Error fetching KOSPI:", error);
  }

  console.log("Market indices fetched:", indices);
  return indices;
}

// ============================================
// Batch Price Fetcher
// ============================================
async function fetchPricesForTickers(
  tickers: ActiveTicker[]
): Promise<PriceResult[]> {
  const results: PriceResult[] = [];

  // Fetch prices with rate limiting (max 5 concurrent requests)
  const batchSize = 5;
  for (let i = 0; i < tickers.length; i += batchSize) {
    const batch = tickers.slice(i, i + batchSize);

    const batchPromises = batch.map(async (ticker) => {
      const price = await fetchYahooPrice(ticker.ticker);
      return {
        ticker: ticker.ticker,
        price,
        currency: ticker.currency,
        error: price === null ? "Failed to fetch price from Yahoo Finance" : null,
      };
    });

    const batchResults = await Promise.all(batchPromises);
    results.push(...batchResults);

    // Rate limiting: wait 200ms between batches
    if (i + batchSize < tickers.length) {
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
  }

  return results;
}

// ============================================
// Database Operations
// ============================================
async function getActiveTickers(supabase: any): Promise<ActiveTicker[]> {
  const { data, error } = await supabase.rpc("get_active_tickers");

  if (error) {
    console.error("Error fetching active tickers:", error);
    throw error;
  }

  return data || [];
}

async function updatePriceCache(
  supabase: any,
  results: PriceResult[]
): Promise<void> {
  for (const result of results) {
    if (result.price !== null) {
      // Successful price fetch
      const { error } = await supabase.rpc("upsert_stock_price", {
        p_ticker: result.ticker,
        p_price: result.price,
        p_currency: result.currency,
        p_error: null,
      });

      if (error) {
        console.error(`Error updating price for ${result.ticker}:`, error);
      }
    } else {
      // Failed price fetch - update with error
      const { error } = await supabase.rpc("upsert_stock_price", {
        p_ticker: result.ticker,
        p_price: 0.01, // Placeholder to satisfy NOT NULL constraint
        p_currency: result.currency,
        p_error: result.error,
      });

      if (error) {
        console.error(`Error updating error status for ${result.ticker}:`, error);
      }
    }
  }
}

async function markInactiveTickers(supabase: any): Promise<number> {
  const { data, error } = await supabase.rpc("mark_inactive_tickers");

  if (error) {
    console.error("Error marking inactive tickers:", error);
    return 0;
  }

  return data || 0;
}

// ============================================
// Portfolio Snapshot Operations
// ============================================
async function getAllAccounts(supabase: any): Promise<Account[]> {
  const { data, error } = await supabase
    .from("accounts")
    .select("*")
    .eq("is_active", true);

  if (error) {
    console.error("Error fetching accounts:", error);
    throw error;
  }

  return data || [];
}

async function capturePortfolioSnapshots(
  supabase: any,
  exchangeRate: number,
  marketIndices: MarketIndices
): Promise<{ captured: number; errors: number }> {
  const accounts = await getAllAccounts(supabase);
  let captured = 0;
  let errors = 0;

  // Get current date in UTC (for US markets) and KST (for Korean markets)
  const now = new Date();
  const utcDate = now.toISOString().split("T")[0]; // YYYY-MM-DD format

  // KST is UTC+9
  const kstDate = new Date(now.getTime() + (9 * 60 * 60 * 1000)).toISOString().split("T")[0];

  // Store market indices once (use UTC date for US indices consistency)
  try {
    const { error: indicesError } = await supabase.rpc("upsert_market_indices", {
      p_snapshot_date: utcDate,
      p_spx_close: marketIndices.spx,
      p_ndx_close: marketIndices.ndx,
      p_kospi_close: marketIndices.kospi,
      p_usd_krw_rate: exchangeRate,
    });

    if (indicesError) {
      console.error("Error storing market indices:", indicesError);
    } else {
      console.log(`Market indices stored for ${utcDate} (including exchange rate: ${exchangeRate})`);
    }
  } catch (error) {
    console.error("Exception storing market indices:", error);
  }

  for (const account of accounts) {
    // Process each allowed currency
    for (const currency of account.allowed_currencies) {
      try {
        // Use appropriate date based on currency
        // KRW markets close at 15:30 KST, so use KST date
        // USD markets close at 16:00 ET (21:00 UTC previous day), so use UTC date
        const snapshotDate = currency === "KRW" ? kstDate : utcDate;
        // Calculate cash balance using database function
        const { data: cashBalance, error: cashError } = await supabase.rpc(
          "calculate_cash_balance",
          {
            p_account_id: account.id,
            p_currency: currency,
          }
        );

        if (cashError) {
          console.error(
            `Error calculating cash balance for account ${account.account_number} (${currency}):`,
            cashError
          );
          errors++;
          continue;
        }

        // Calculate stock value (sum of current_price * quantity for active holdings)
        const { data: holdings, error: holdingsError } = await supabase.rpc(
          "get_active_tickers"
        );

        if (holdingsError) {
          console.error("Error fetching holdings:", holdingsError);
          errors++;
          continue;
        }

        // Filter holdings by account and currency
        const accountHoldings = holdings.filter(
          (h: any) =>
            h.account_id === account.id && h.currency === currency
        );

        // Get prices from cache
        let stockValue = 0;
        for (const holding of accountHoldings) {
          const { data: priceData, error: priceError } = await supabase
            .from("stock_prices")
            .select("current_price")
            .eq("ticker", holding.ticker)
            .eq("is_active", true)
            .is("fetch_error", null)
            .single();

          if (!priceError && priceData) {
            stockValue += priceData.current_price * holding.net_quantity;
          }
        }

        // Capture snapshot (baseline_value is calculated by DB function)
        // Market indices are stored separately in market_indices table
        const { error: snapshotError} = await supabase.rpc(
          "capture_portfolio_snapshot",
          {
            p_account_id: account.id,
            p_snapshot_date: snapshotDate,
            p_currency: currency,
            p_stock_value: stockValue,
            p_cash_balance: cashBalance,
            p_baseline_value: null,  // Let DB function determine baseline
            p_exchange_rate: exchangeRate,
          }
        );

        if (snapshotError) {
          console.error(
            `Error capturing snapshot for account ${account.account_number} (${currency}):`,
            snapshotError
          );
          errors++;
        } else {
          captured++;
          console.log(
            `Snapshot captured: Account ${account.account_number} (${currency}) - Date: ${snapshotDate} - Value: ${stockValue + cashBalance}`
          );
        }
      } catch (error) {
        console.error(
          `Exception capturing snapshot for account ${account.account_number} (${currency}):`,
          error
        );
        errors++;
      }
    }
  }

  return { captured, errors };
}

// ============================================
// Main Handler
// ============================================
serve(async (req: Request) => {
  try {
    // Initialize Supabase client with service role key
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Step 1: Get active tickers from database
    console.log("Fetching active tickers...");
    const activeTickers = await getActiveTickers(supabase);
    console.log(`Found ${activeTickers.length} active tickers`);

    if (activeTickers.length === 0) {
      return new Response(
        JSON.stringify({
          success: true,
          message: "No active tickers to update",
          updated: 0,
          failed: 0,
          snapshots_captured: 0,
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }
      );
    }

    // Step 2: Fetch current prices from Yahoo Finance
    console.log("Fetching prices from Yahoo Finance...");
    const priceResults = await fetchPricesForTickers(activeTickers);

    // Step 3: Update price cache in database
    console.log("Updating price cache...");
    await updatePriceCache(supabase, priceResults);

    // Step 4: Mark tickers as inactive if no longer in holdings
    console.log("Marking inactive tickers...");
    const inactiveCount = await markInactiveTickers(supabase);

    // Step 5: Fetch exchange rate
    console.log("Fetching USD/KRW exchange rate...");
    const exchangeRate = await fetchExchangeRate();
    console.log(`Exchange rate: ${exchangeRate}`);

    // Step 6: Fetch market indices
    console.log("Fetching market indices...");
    const marketIndices = await fetchMarketIndices();
    console.log("Market indices fetched:", marketIndices);

    // Step 7: Capture portfolio snapshots
    console.log("Capturing portfolio snapshots...");
    const snapshotResult = await capturePortfolioSnapshots(
      supabase,
      exchangeRate,
      marketIndices
    );
    console.log(
      `Snapshots: ${snapshotResult.captured} captured, ${snapshotResult.errors} errors`
    );

    // Calculate statistics
    const successCount = priceResults.filter((r) => r.price !== null).length;
    const failedCount = priceResults.filter((r) => r.price === null).length;

    const summary = {
      success: true,
      message: "Price update and snapshot capture completed",
      timestamp: new Date().toISOString(),
      statistics: {
        total_tickers: activeTickers.length,
        updated: successCount,
        failed: failedCount,
        marked_inactive: inactiveCount,
        snapshots_captured: snapshotResult.captured,
        snapshot_errors: snapshotResult.errors,
      },
      exchange_rate: exchangeRate,
      details: {
        krw_tickers: priceResults.filter((r) => r.currency === "KRW").length,
        usd_tickers: priceResults.filter((r) => r.currency === "USD").length,
      },
      failed_tickers: priceResults
        .filter((r) => r.price === null)
        .map((r) => r.ticker),
    };

    console.log("Update summary:", summary);

    return new Response(JSON.stringify(summary), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  } catch (error) {
    console.error("Edge Function error:", error);

    return new Response(
      JSON.stringify({
        success: false,
        error: error.message,
        timestamp: new Date().toISOString(),
      }),
      {
        headers: { "Content-Type": "application/json" },
        status: 500,
      }
    );
  }
});

// ============================================
// Deployment Instructions
// ============================================
/*
1. Deploy to Supabase:
   supabase functions deploy update-stock-prices

2. Set up cron job in Supabase Dashboard:
   - Navigate to Database → Cron Jobs
   - Create new job with schedule:
     * US market close: 0 21 * * 1-5  (06:00 KST next day, Mon-Fri)

3. Manual test:
   curl -X POST 'https://[PROJECT_REF].supabase.co/functions/v1/update-stock-prices' \
     -H 'Authorization: Bearer [ANON_KEY]'

4. Check logs:
   supabase functions logs update-stock-prices

5. Verify results:
   SELECT * FROM stock_prices WHERE last_updated > NOW() - INTERVAL '1 hour';
   SELECT * FROM portfolio_snapshots WHERE snapshot_date = CURRENT_DATE;
*/
