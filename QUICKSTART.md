# ⚡ Quick Start Guide

Get your portfolio tracker up and running in **5 minutes**!

---

## 📋 Prerequisites

- **Python 3.9+** installed
- **Git** installed
- **Supabase account** (free tier works!)

---

## 🚀 Setup Steps

### 1️⃣ Clone Repository (1 min)

```bash
git clone https://github.com/greyyoo/portfolio-tracker.git
cd portfolio-tracker
```

### 2️⃣ Install Dependencies (1 min)

```bash
# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install packages
pip install -r requirements.txt
```

### 3️⃣ Setup Supabase (2 min)

1. Go to [Supabase](https://supabase.com) → Create new project
2. Copy `Project URL` and `anon key` from **Settings → API**
3. Open **SQL Editor** → Paste entire `complete_schema.sql` → Run
4. ✅ Confirm: "5 accounts created"

### 4️⃣ Configure Environment (30 sec)

```bash
# Copy template
cp .env.example .env

# Edit .env file with your Supabase credentials
nano .env  # or use your favorite editor
```

Paste your credentials:
```env
PUBLIC_SUPABASE_URL=https://[YOUR_PROJECT_REF].supabase.co
PUBLIC_SUPABASE_ANON_KEY=[YOUR_ANON_KEY]
```

### 5️⃣ Run App (30 sec)

```bash
streamlit run app.py
```

🎉 **Done!** Browser opens at `http://localhost:8501`

---

## 📊 Add Your First Transaction

### Option A: Supabase Console (Recommended for first time)

1. Go to Supabase Dashboard → **Table Editor** → `transactions`
2. Click **Insert** → **Insert row**
3. Fill in:
   - `account_id`: Copy UUID from `accounts` table (e.g., Account 1)
   - `transaction_type`: `BUY`
   - `country`: `USA`
   - `stock_name`: `Apple Inc.`
   - `ticker`: `AAPL`
   - `transaction_date`: `2024-01-15`
   - `trade_price`: `150.25`
   - `currency`: `USD`
   - `quantity`: `10`
4. Click **Save**

### Option B: CSV Import (Bulk transactions)

1. Edit `csv_import_templates/transactions_template.csv`
2. Replace `[REPLACE_WITH_YOUR_ACCOUNT_UUID]` with actual UUID
3. Supabase → **Table Editor** → `transactions` → **Insert** → **Import data from CSV**

---

## 🔄 Refresh Dashboard

Go back to Streamlit app (`http://localhost:8501`) and refresh → See your transaction!

---

## 🎯 Next Steps

- **Add more transactions** using CSV import
- **Configure accounts** (Edit account names, initial amounts in `accounts` table)
- **Enable auto-updates** (Optional: Deploy Edge Function - see README)
- **Add cash transactions** (RP interest, deposits, withdrawals)

---

## ❓ Troubleshooting

### Error: "Supabase credentials not found"
→ Check `.env` file exists and has correct values

### Error: "Currency not allowed for this account"
→ Check account's `allowed_currencies` in `accounts` table

### Korean stock prices not showing
→ Ensure ticker has `.KS` or `.KQ` suffix (e.g., `005930.KS`)

### App not loading
→ Make sure virtual environment is activated: `source venv/bin/activate`

---

## 📚 Need More Help?

- **Full Guide**: See [README.md](README.md)
- **Security**: See [SECURITY.md](SECURITY.md)
- **CSV Import**: See [csv_import_templates/README.md](csv_import_templates/README.md)
- **Issues**: [GitHub Issues](https://github.com/greyyoo/portfolio-tracker/issues)

---

**Happy Tracking!** 📈
