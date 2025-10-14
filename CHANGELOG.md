# Changelog

All notable changes to this project will be documented in this file.

---

## [0.1.1] - 2025-10-14

### 🔧 Fixed

- **Streamlit Cloud Deployment Support**: Added support for Streamlit Secrets (TOML format)
  - `config.py` now reads from Streamlit Secrets (`st.secrets`) for cloud deployment
  - Falls back to `.env` file for local development
  - Priority: Streamlit Secrets > Environment Variables
  - Enables seamless deployment on Streamlit Cloud

---

## [0.1.0] - 2025-10-14

### 🎉 Initial Public Release

First public release of the Trading Portfolio Tracker built with 99.9% AI-powered development (Vibe Coding with Claude Code).

### ✨ Added

#### Core Features
- **Multi-Account Management**: 5 independent investment accounts with separate strategies
- **Multi-Currency Support**: Full KRW and USD separation throughout the stack
- **Database-Level Currency Restrictions**: PostgreSQL trigger validation for account currency rules
- **Real-time Stock Prices**: Yahoo Finance API integration with 15-minute caching
- **USD/KRW Exchange Rate**: Automatic currency conversion for aggregate metrics
- **Portfolio Analytics**: Holdings, transactions, closed positions with P&L calculations
- **Daily Snapshots**: Automated portfolio valuation capture via Edge Function
- **Market Indices Tracking**: S&P 500, NASDAQ 100, KOSPI baseline comparison
- **Normalized Performance Charts**: Baseline tracking from 2025-10-13 = 1.0

#### Technical Implementation
- **Streamlit Dashboard**: Read-only public interface for portfolio visualization
- **Supabase Backend**: PostgreSQL database with Row Level Security (RLS)
- **Edge Functions**: Deno/TypeScript serverless functions for price updates
- **CSV Import**: Bulk transaction import via Supabase console
- **Cash Transactions**: RP interest, deposits, withdrawals tracking
- **Price Caching**: Database-cached prices updated twice daily

#### Database Schema
- `accounts`: 5 accounts with multi-currency support
- `transactions`: Stock buy/sell records with currency validation
- `cash_transactions`: Deposits, withdrawals, RP interest
- `stock_prices`: Cached prices from Yahoo Finance
- `portfolio_snapshots`: Daily valuation history
- `market_indices`: SPX, NDX, KOSPI tracking

#### Documentation
- **README.md**: Comprehensive setup guide with Quick Start section
- **QUICKSTART.md**: 5-minute setup guide for new users
- **SECURITY.md**: Security best practices and public repo guidelines
- **CSV Import Templates**: Sample CSV files with clear instructions
- **LICENSE**: MIT License for open-source distribution

#### Developer Experience
- **.env.example**: Template for environment variables
- **.gitignore**: Comprehensive exclusion rules
- **Type Hints**: Python type annotations throughout codebase
- **Code Comments**: Clear documentation of business logic
- **Error Handling**: Graceful degradation and user-friendly messages

### 🔒 Security
- Environment variables for credentials (never committed)
- Row Level Security (RLS) policies for public read-only access
- Database triggers for data validation
- Proper .gitignore configuration to exclude sensitive files

### 📊 Data Management
- Account-scoped calculations with currency separation
- Closed position detection (total_buy_qty == total_sell_qty)
- Average purchase price calculation with partial sell support
- Currency-specific formatting (₩0 decimals, $2 decimals)

### 🎨 UI/UX
- Overview page with aggregate metrics across all accounts
- Individual account pages with tabbed navigation
- Transaction history with currency indicators
- Closed positions with realized P&L
- Statistics page with normalized performance comparison
- Color-coded profit/loss indicators

### 🤖 Automation
- Supabase Edge Function for daily price updates
- pg_cron scheduled jobs (21:00 UTC / 06:00 KST)
- Automatic portfolio snapshot capture
- Market indices fetching

### 🌐 Deployment
- Streamlit Cloud deployment support
- Environment variable configuration via Streamlit Secrets
- Public read-only access with Supabase RLS
- Edge Function deployment via Supabase CLI

---

**Note**: This project is built with 99.9% AI-powered development using Claude Code and Vibe Coding methodology.
