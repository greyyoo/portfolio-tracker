# 📊 Multi-Account Stock Portfolio Tracker

> **⚡ 99.9% AI-Powered Development**
> 이 프로젝트는 [Claude Code](https://claude.ai/code)와 **Vibe Coding**으로 거의 전체가 구현되었습니다.
> 자연어 대화만으로 전문적인 풀스택 애플리케이션을 만들 수 있다는 것을 보여주는 실제 사례입니다.

---

한국(KRW)과 미국(USD) 주식 투자를 추적하는 **멀티 계좌 포트폴리오 관리 웹 애플리케이션**입니다.

Streamlit 기반의 대시보드로 5개의 독립된 투자 계좌를 관리하고, 실시간 가격 업데이트, 일일 성과 스냅샷, 통화별 손익 분석을 제공합니다.

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io)
[![Supabase](https://img.shields.io/badge/Supabase-181818?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Claude](https://img.shields.io/badge/Built_with-Claude_Code-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)](https://claude.ai/code)

---

## ✨ 주요 기능

### 🏦 멀티 계좌 관리
- **5개 독립 투자 계좌** - 각자 다른 전략 및 통화 제한
  - 계좌 1-3: USD 전용 (미국 주식)
  - 계좌 4: KRW 전용 (한국 주식)
  - 계좌 5: USD+KRW 혼합 (글로벌 포트폴리오)
- 계좌별 초기 투자금 및 성과 추적
- 데이터베이스 레벨 통화 제한 검증 (PostgreSQL trigger)

### 💰 현금 흐름 관리
- **RP 이자 수익** 일일 기록
- **입금/출금** 추적
- 현금 잔고 자동 계산: `초기 투자금 + 입출금 + RP 이자 - 주식 투자`
- CSV 일괄 입력 지원

### 📊 포트폴리오 분석
- **자동 가격 업데이트** (Supabase Edge Function, 매일 06:00 KST)
- 실시간 USD/KRW 환율 적용 (Yahoo Finance API)
- 통화별 포트폴리오 성과 분석 (KRW/USD 분리)
- 평균 단가 및 수익률 자동 계산
- 보유 주식 평가 손익 (미실현 손익)
- 청산 포지션 실현 손익

### 📈 일일 성과 스냅샷
- **자동 스냅샷 캡처** (매일 미국 장 마감 후)
- 계좌별/통화별 일별 평가액 기록
- 시장 지수 추적 (S&P 500, NASDAQ 100, KOSPI)
- 시계열 성과 그래프 (Baseline: 2025-10-13 = 1.0)

### 🎯 대시보드
- **Overview 페이지**: 전체 5개 계좌 통합 요약
- **개별 계좌 페이지**: 계좌별 상세 분석
  - 현재 보유 주식
  - 거래 내역
  - 청산 포지션
- 통화별 포맷팅 (₩ 소수점 0자리, $ 소수점 2자리)
- 손익 색상 표시 (양수 초록, 음수 빨강)

---

## 🚀 빠른 시작 (Quick Start)

> **⏱️ 5분 안에 시작하기**: 더 빠른 설정을 원하시면 **[QUICKSTART.md](QUICKSTART.md)**를 참고하세요!

### 1️⃣ Repository Clone

```bash
git clone https://github.com/[YOUR_USERNAME]/trading-portfolio-tracker.git
cd trading-portfolio-tracker
```

### 2️⃣ Python 가상환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 3️⃣ Supabase 프로젝트 생성

1. **[Supabase](https://supabase.com)** 계정 생성 (무료)
2. **새 프로젝트 생성**
   - Organization 선택
   - 프로젝트 이름 입력
   - 데이터베이스 비밀번호 설정
   - Region 선택 (Seoul 추천)
   - Free tier 선택

3. **데이터베이스 스키마 설정**
   - Supabase Dashboard → **SQL Editor**
   - `complete_schema.sql` 파일 내용 복사
   - SQL Editor에 붙여넣기 → **Run** 클릭
   - 성공 메시지 확인: `5 tables created, 6 functions created, 5 accounts inserted`

4. **API Keys 확인**
   - Dashboard → **Settings** → **API**
   - `Project URL` 복사
   - `anon/public` key 복사

### 4️⃣ 환경 변수 설정

```bash
# .env.example을 .env로 복사
cp .env.example .env

# .env 파일 편집
nano .env
# 또는
code .env
```

`.env` 파일에 Supabase credentials 입력:

```env
PUBLIC_SUPABASE_URL=https://[YOUR_PROJECT_REF].supabase.co
PUBLIC_SUPABASE_ANON_KEY=your_actual_anon_key_here
```

### 5️⃣ 애플리케이션 실행

```bash
streamlit run app.py
```

브라우저가 자동으로 열리며 `http://localhost:8501`에서 앱을 사용할 수 있습니다! 🎉

---

## 📁 프로젝트 구조

```
trading-portfolio-tracker/
├── 📄 app.py                          # Streamlit 메인 애플리케이션
├── ⚙️ config.py                       # 환경 변수 로딩
├── 🗄️ database.py                     # Supabase CRUD 함수
├── 🧮 calculations.py                 # 포트폴리오 계산 로직
├── 💱 exchange_rate.py                # USD/KRW 환율
├── 💰 currency_utils.py               # 통화 포맷팅
├── 📊 charts.py                       # 차트 생성
├── 📦 requirements.txt                # Python 의존성
├── 🔐 .env.example                    # 환경 변수 템플릿
├── 🚫 .gitignore                      # Git 제외 파일
│
├── 🗃️ complete_schema.sql             # 통합 데이터베이스 스키마
├── 📚 SECURITY.md                     # 보안 가이드
├── 📖 CLAUDE.md                       # 개발자 가이드 (Claude Code용)
│
├── 📂 csv_import_templates/           # CSV 템플릿
│   ├── transactions_template.csv
│   ├── cash_transactions_template.csv
│   └── README.md
│
├── 📂 supabase/
│   └── functions/
│       └── update-stock-prices/
│           └── index.ts               # 가격 업데이트 Edge Function
│
├── 📂 sql_archive/                    # 아카이브 SQL 파일
└── 📂 docs_archive/                   # 아카이브 문서
```

---

## 📝 사용 방법

### 데이터 입력 (Supabase Console)

이 앱은 **읽기 전용 대시보드**입니다. 모든 데이터 입력은 Supabase Console에서 진행합니다.

#### 1. 주식 거래 입력

**방법 A: 직접 입력**
1. Supabase Dashboard → **Table Editor** → `transactions`
2. **Insert** → **Insert row**
3. 필드 입력:
   - `account_id`: 계좌 UUID (accounts 테이블에서 조회)
   - `transaction_type`: `BUY` 또는 `SELL`
   - `country`: `Korea` 또는 `USA`
   - `ticker`: 티커 심볼 (예: `AAPL`, `005930.KS`)
   - `stock_name`: 주식명
   - `trade_price`: 거래 가격
   - `quantity`: 수량
   - `transaction_date`: 거래 날짜 (YYYY-MM-DD)
   - `currency`: `KRW` 또는 `USD` (country에 따라 자동 설정)

**방법 B: CSV 일괄 입력**
1. `csv_import_templates/transactions_template.csv` 다운로드
2. 엑셀/스프레드시트에서 데이터 입력
3. Table Editor → **Insert** → **Import data from CSV**
4. CSV 파일 업로드

#### 2. 현금 거래 입력 (RP 이자, 입출금)

1. Table Editor → `cash_transactions`
2. 거래 유형:
   - `RP_INTEREST`: RP 이자 수익
   - `DEPOSIT`: 추가 입금
   - `WITHDRAWAL`: 출금
3. CSV 템플릿: `cash_transactions_template.csv`

자세한 가이드: `csv_import_templates/README.md` 참조

#### 3. 계좌 설정 수정

1. Table Editor → `accounts`
2. 계좌 선택 → **Edit**
3. 수정 가능 항목:
   - `account_name`: 계좌 이름
   - `strategy_description`: 투자 전략 메모
   - `initial_seed_money_krw`: 초기 투자금 (KRW)
   - `initial_seed_money_usd`: 초기 투자금 (USD)

---

## 🤖 자동화 설정 (선택사항)

매일 자동으로 주식 가격을 업데이트하고 포트폴리오 스냅샷을 캡처하려면 Supabase Edge Function을 배포하세요.

### 1. Supabase CLI 설치

```bash
# macOS/Linux
brew install supabase/tap/supabase

# Windows (Scoop)
scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
scoop install supabase
```

### 2. Supabase 로그인 및 프로젝트 연결

```bash
# Supabase 로그인
supabase login

# 프로젝트 연결 (YOUR_PROJECT_REF를 실제 값으로 교체)
supabase link --project-ref [YOUR_PROJECT_REF]
```

### 3. Edge Function 배포

```bash
# Edge Function 배포
supabase functions deploy update-stock-prices

# 환경 변수는 자동으로 주입됨 (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
```

### 4. Cron Job 설정

Supabase Dashboard → **Database** → **Extensions** → **pg_cron** 활성화

SQL Editor에서 실행:

```sql
-- 매일 21:00 UTC (한국 시간 06:00 다음날) 실행
SELECT cron.schedule(
  'daily-stock-price-update',
  '0 21 * * 1-5',  -- 월-금 (주말 제외)
  $$
  SELECT net.http_post(
    url := 'https://[YOUR_PROJECT_REF].supabase.co/functions/v1/update-stock-prices',
    headers := jsonb_build_object('Authorization', 'Bearer ' || '[YOUR_ANON_KEY]')
  );
  $$
);
```

### 5. 수동 테스트

```bash
# 수동 실행 테스트
curl -X POST 'https://[YOUR_PROJECT_REF].supabase.co/functions/v1/update-stock-prices' \
  -H 'Authorization: Bearer [YOUR_ANON_KEY]'

# 로그 확인
supabase functions logs update-stock-prices --follow
```

---

## 🔧 기술 스택

| Category | Technology |
|----------|-----------|
| **Frontend** | Streamlit 1.28+ |
| **Backend** | Supabase (PostgreSQL) |
| **Serverless** | Supabase Edge Functions (Deno) |
| **Market Data** | Yahoo Finance API (yfinance) |
| **Visualization** | Plotly, Altair |
| **Automation** | pg_cron |
| **Language** | Python 3.9+, TypeScript |

---

## 🗄️ 데이터베이스 스키마

### 주요 테이블

1. **`accounts`** - 5개 투자 계좌
   - `account_number` (1-5)
   - `allowed_currencies` (KRW, USD)
   - `initial_seed_money_krw`, `initial_seed_money_usd`

2. **`transactions`** - 주식 거래 내역
   - `transaction_type` (BUY, SELL)
   - `ticker`, `stock_name`
   - `trade_price`, `quantity`
   - `currency` (자동 설정)

3. **`cash_transactions`** - 현금 거래
   - `transaction_type` (DEPOSIT, WITHDRAWAL, RP_INTEREST)
   - `amount`, `currency`

4. **`stock_prices`** - 가격 캐시 (Edge Function이 업데이트)
   - `ticker`, `current_price`
   - `last_updated`

5. **`portfolio_snapshots`** - 일일 스냅샷
   - `snapshot_date`
   - `stock_value`, `cash_balance`, `total_value`
   - `baseline_value`, `value_change`, `change_pct`

6. **`market_indices`** - 시장 지수 (SPX, NDX, KOSPI)

### 주요 함수

- `get_active_tickers()` - 현재 보유 종목 조회
- `calculate_cash_balance()` - 현금 잔고 계산
- `capture_portfolio_snapshot()` - 스냅샷 저장
- `get_portfolio_history()` - 시계열 데이터
- `upsert_market_indices()` - 시장 지수 업데이트

---

## 🔐 보안

- **Environment Variables**: `.env` 파일에 credentials 저장 (git 제외)
- **Row Level Security (RLS)**: Public은 SELECT만 가능
- **Read-Only App**: Streamlit 앱은 데이터 조회만
- **Service Role Key**: Edge Function에서만 사용 (환경 변수)

자세한 보안 가이드: **[SECURITY.md](SECURITY.md)** 참조

---

## 🚀 배포 (Streamlit Cloud)

### 1. GitHub Repository 연결

Streamlit Cloud → **New app** → GitHub repository 선택

### 2. Secrets 설정

**Settings** → **Secrets**:

```toml
[default]
PUBLIC_SUPABASE_URL = "https://[YOUR_PROJECT_REF].supabase.co"
PUBLIC_SUPABASE_ANON_KEY = "your_actual_anon_key_here"
```

### 3. 배포

- Main file path: `app.py`
- Python version: 3.9+
- Deploy! 🚀

---

## 💡 팁 & 트러블슈팅

### Q: 한국 주식 가격이 안 나와요
A: 한국 주식 티커는 `.KS` (KOSPI) 또는 `.KQ` (KOSDAQ) 접미사가 필수입니다.
   - 예: `005930.KS` (삼성전자), `035720.KQ` (카카오)

### Q: 통화 제한 오류가 발생해요
A: 각 계좌는 허용된 통화만 거래할 수 있습니다.
   - 계좌 1-3: USD만
   - 계좌 4: KRW만
   - 계좌 5: USD+KRW 모두

### Q: 청산 포지션이 안 보여요
A: 청산 포지션은 매수 수량 = 매도 수량일 때만 표시됩니다.
   - 완전히 매도한 종목만 청산 포지션으로 이동

### Q: 가격이 업데이트 안 돼요
A: 수동으로 Edge Function을 실행해보세요:
   ```bash
   curl -X POST 'https://[YOUR_PROJECT_REF].supabase.co/functions/v1/update-stock-prices' \
     -H 'Authorization: Bearer [YOUR_ANON_KEY]'
   ```

---

---

## 📄 라이선스

이 프로젝트는 **MIT License** 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참고하세요.

상업적 사용, 수정, 배포 모두 자유롭게 가능합니다.

---

## 🙏 Acknowledgments

- [Streamlit](https://streamlit.io) - 빠른 대시보드 개발
- [Supabase](https://supabase.com) - 백엔드 및 데이터베이스
- [Yahoo Finance](https://finance.yahoo.com) - 주식 가격 데이터
- [Claude Code](https://claude.ai/code) - 개발 지원

---

## 📞 Contact & Support

문제가 발생하거나 질문이 있으시면 GitHub Issues를 이용해주세요.

보안 이슈는 **[SECURITY.md](SECURITY.md)** 참조하여 비공개로 보고해주세요.

---

## 📚 추가 문서

- **[QUICKSTART.md](QUICKSTART.md)** - 5분 빠른 시작 가이드
- **[CHANGELOG.md](CHANGELOG.md)** - 버전 히스토리
- **[SECURITY.md](SECURITY.md)** - 보안 가이드
- **[csv_import_templates/README.md](csv_import_templates/README.md)** - CSV 임포트 가이드

---

**Built with ❤️ using Streamlit and Supabase**

**최종 업데이트**: 2025-10-14 | **버전**: 2.0
