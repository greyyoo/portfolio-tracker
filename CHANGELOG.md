# 변경 이력

이 프로젝트의 주요 변경 사항을 기록합니다.

---

## [0.1.3] - 2025-10-15

### 🐛 긴급 수정 (Hotfix)

#### Fear & Greed Index
- **패키지 버전 수정**: fear-and-greed 1.0.0 → 0.4
  - **이유**: 1.0.0 버전이 PyPI에 존재하지 않아 설치 실패
  - **영향**: Market Today 섹션의 F&G Index 표시 오류 해결
  - **파일**: `requirements.txt` (line 10)

#### 원금 vs 계좌평가액 차트
- **환율 fallback 로직 개선**
  - **이전**: 하드코딩된 1300 KRW 기본값 사용
  - **수정**: 실시간 환율 API(`get_usd_krw_rate()`) 호출로 fallback
  - **적용 시점**:
    - 스냅샷 데이터에 `exchange_rate` 컬럼이 없을 때
    - 스냅샷 데이터가 NULL일 때
  - **효과**: USD 계좌 원금 변동의 정확도 향상 (환율 변동 반영)
  - **파일**: `app.py` (lines 1373-1380)

#### PostgreSQL 함수 오버로딩 오류
- **calculate_cash_balance() 함수 오버로드 추가**
  - **문제**:
    - DB에는 3-param 버전만 존재: `(p_account_id, p_currency, p_date)`
    - Python 앱과 Edge Function은 2-param 호출: `(p_account_id, p_currency)`
    - 에러: `PGRST202: Could not find the function`
  - **해결**: 2-param 버전 추가 (내부적으로 `CURRENT_DATE`와 함께 3-param 호출)
  - **영향**: Python 앱과 Edge Function의 현금 잔고 계산 정상화
  - **파일**:
    - `complete_schema.sql`: 함수 정의 추가
    - `sql_archive/fix_calculate_cash_balance_overload.sql`: 독립 실행 스크립트

### 🚀 데이터베이스 개선

#### Market Indices 테이블
- **usd_krw_rate 컬럼 추가**
  - **목적**: 시장 지수와 함께 환율도 스냅샷에 저장
  - **데이터 소스**: Edge Function이 매시간 yfinance에서 조회
  - **활용**: 과거 특정 날짜의 환율 추적 가능
  - **파일**:
    - `complete_schema.sql` (line 130)
    - `supabase/functions/update-stock-prices/index.ts` (lines 273-283)

#### Snapshot 함수 최적화

**capture_portfolio_snapshot() 개선**:
- **Baseline 로직 변경**:
  - **이전**: 첫 스냅샷 또는 현재 값 기반 동적 계산
  - **수정**: 계좌별 고정 baseline 값 사용
    - Account 1: $20,000 (USD)
    - Account 2: ₩10,000,000 (KRW)
    - Account 3: $4,000 (USD)
    - Account 4: $4,000 (USD)
    - Account 5: $4,000 (USD)
  - **효과**: 일관된 성과 추적, 계산 성능 향상
- **파일**: `complete_schema.sql` (lines 193-211)

**recalculate_snapshots() 최적화**:
- **성능 개선**:
  - 서브쿼리 중첩 → JOIN으로 변경
  - `calculate_cash_balance()` 함수 재사용으로 중복 로직 제거
  - 테이블 별칭 사용 (t, ct, pc)으로 컬럼 명확화
- **RETURN TABLE 명확화**:
  - 컬럼명 변경: `snapshot_date`, `account_name`, `currency`, `snapshot_id`
  - 결과 가독성 향상
- **파일**: `complete_schema.sql` (lines 379-492)

### 🔧 개발자 도구

#### 과거 환율 조회 함수
- **get_historical_usd_krw_rate() 추가**
  - **기능**: 특정 날짜의 USD/KRW 환율 조회
  - **로직**:
    1. 입력 날짜 전후 3일 범위로 yfinance 조회
    2. 주말/공휴일 대비 가장 가까운 영업일 데이터 사용
    3. 데이터 없으면 현재 환율로 fallback
  - **캐싱**: 1시간 TTL (과거 데이터는 변하지 않음)
  - **파라미터**:
    - `date`: 문자열 ('YYYY-MM-DD') 또는 datetime 객체
  - **반환값**: `float` (1 USD = X KRW)
  - **파일**: `exchange_rate.py` (lines 40-79)

### 📁 파일 변경사항

**수정된 파일**:
- `requirements.txt`: fear-and-greed 버전 수정 (1.0.0 → 0.4)
- `app.py`: 원금 차트 환율 fallback 개선 (lines 1373-1380)
- `complete_schema.sql`:
  - `market_indices` 테이블에 `usd_krw_rate` 컬럼 추가
  - `calculate_cash_balance()` 2-param 오버로드 추가
  - `capture_portfolio_snapshot()` baseline 로직 개선
  - `recalculate_snapshots()` 성능 최적화
- `exchange_rate.py`: `get_historical_usd_krw_rate()` 함수 추가
- `supabase/functions/update-stock-prices/index.ts`: market_indices에 환율 저장

**추가된 파일**:
- `sql_archive/fix_calculate_cash_balance_overload.sql`: 함수 오버로드 독립 실행 스크립트

### 🔧 데이터베이스 마이그레이션

**필수 실행 SQL**:
```sql
-- 1. market_indices 테이블에 환율 컬럼 추가
ALTER TABLE market_indices ADD COLUMN IF NOT EXISTS usd_krw_rate NUMERIC(10, 4);

-- 2. calculate_cash_balance 2-param 오버로드 추가
CREATE OR REPLACE FUNCTION calculate_cash_balance(
    p_account_id UUID,
    p_currency TEXT
)
RETURNS NUMERIC AS $$
BEGIN
    RETURN calculate_cash_balance(p_account_id, p_currency, CURRENT_DATE);
END;
$$ LANGUAGE plpgsql;
```

또는 스크립트 실행:
```bash
# Supabase SQL Editor에서 실행
sql_archive/fix_calculate_cash_balance_overload.sql
```

---

## [0.1.2] - 2025-10-15

### 🐛 버그 수정

#### 수정됨
- **평단가 계산 로직 수정**: 부분 매도 시 평단가가 잘못 계산되던 문제 해결
  - **이전 로직**: `평단가 = (총 매수금액 - 총 매도금액) / 현재 보유수량`
  - **수정 로직**: `평단가 = 총 매수금액 / 총 매수수량`
  - **예시**: MARA 20주 @ $19.615 매수 → 10주 @ $22.28 매도 시
    - 이전: $16.95 (잘못된 계산) ❌
    - 수정: $19.615 (올바른 평단가) ✅
  - 부분 매도 시에도 평단가가 변하지 않도록 수정

- **USD/KRW 환율 표시 오류 수정**: Market Today 섹션의 USD/KRW 환율 표시 오류 해결
  - 다중 티커 시도 (KRW=X, USDKRW=X) 및 fallback 체인 구현
  - 유효성 검증 추가 (1000-2000 KRW 범위)
  - exchange_rate.py 함수 재사용으로 신뢰성 향상

- **PostgreSQL 함수 타입 불일치 해결**: get_cash_transaction_summary 함수 타입 불일치 수정
  - double precision → NUMERIC 타입 변환 오류 해결
  - Python에서 float() 타입 변환 추가
  - 에러 처리 강화 및 기본값 반환

- **시간대 표시 개선**: 환율 타임스탬프를 KST (한국 표준시)로 표시
  - `zoneinfo` import 추가하여 적절한 시간대 변환
  - 타임스탬프 형식: `YYYY-MM-DD HH:MM:SS KST`
  - 이전에는 UTC로 표시되어 사용자 혼란 발생

### 🚀 성능 및 캐시 최적화

#### 변경됨
- **Streamlit 캐시 지연 제거**: `get_current_prices()` 함수에서 `@st.cache_data` 데코레이터 제거
  - **이전**: 15분 TTL로 인해 가격 업데이트에 5-30분 지연 발생
  - **이후**: 데이터베이스 캐시에서 즉시 가격 반영
  - 데이터베이스가 주 캐시 계층 역할, Edge Function을 통해 매시간 업데이트
  - Streamlit이 이제 페이지 새로고침 시 데이터베이스를 직접 조회

- **환율 캐싱 최적화**: `get_usd_krw_rate()` TTL을 15분에서 1분으로 단축
  - 환율 변동에 더 빠르게 반응
  - 시간당 가격 업데이트 일정과 더 잘 맞춤

#### 인프라
- **Cron Job 일정 업데이트**: 하루 2회에서 매시간 실행으로 변경
  - **새 일정**: 매시간 정각 실행 (`0 * * * *`)
  - **이전 일정**: 07:00 UTC (한국 장) 및 21:00 UTC (미국 장)
  - 거래 시간 중 더 자주 가격 업데이트
  - 장중 포트폴리오 모니터링 지원 개선

### 🚀 새로운 기능

#### 추가됨
- **수수료(Fee) 컬럼 지원**: 거래 수수료 추적 및 계산 반영
  - **평단가 계산**: 수수료 포함 매수 비용 = (거래가 × 수량) + 수수료
  - **청산 손익 계산**:
    - 수수료 포함 매수 비용 = (거래가 × 수량) + 수수료
    - 수수료 차감 매도 수익 = (거래가 × 수량) - 수수료
  - **거래 내역 테이블**: 수수료 컬럼 추가 (0이면 '-' 표시)
  - nullable 컬럼으로 과거 데이터와 호환

- **💰 현금 내역 탭**: 개별 계좌 페이지에 현금 거래 내역 표시
  - **4-column 요약**: 총 입금액, 총 출금액, RP 이자, 현재 잔고 (KRW/USD 각각)
  - **현금 거래 테이블**: 날짜, 유형, 통화, 금액, 누적 잔고, 설명
  - **색상 코딩**: 입금 (파란색), 출금 (빨간색), RP 이자 (초록색)
  - **누적 잔고 추적**: 시간순 현금 잔고 변화 추적

- **원금 vs 계좌평가액 차트**: 통계 페이지에 시계열 차트 추가
  - **위치**: 정규화 성과 차트 아래
  - **계좌별 차트**: 2-column 레이아웃으로 모든 계좌 표시
  - **전체 포트폴리오 차트**: Full-width 통합 차트
  - **데이터 구성**:
    - 원금 (파란색): 초기 시드 + 입금 - 출금 (RP 이자 제외)
    - 계좌평가액 (초록색): 주식 평가액 + 현금 잔고
  - **USD 계좌 처리**: 일일 환율 변동 반영하여 KRW로 표시
  - **안내 메시지**: USD 계좌의 원금 변동은 환율 변동에 의한 것임을 명시

- **승률(Win Rate) 계산 기능**: 청산된 포지션 기반 트레이딩 성과 분석
  - **개별 계좌 페이지 "청산 포지션" 탭에 승률 통계 섹션 추가**:
    - 전체 청산 건수
    - Win 건수 및 평균 수익률
    - Loss 건수 및 평균 손실률
    - 승률 (WR) - 50% 이상 초록색, 미만 빨간색
  - **Win/Loss 분류 기준**: 수익률 ≥ 0 → Win, < 0 → Loss
  - **청산 포지션 테이블에 "결과" 컬럼 추가**: Win/Loss 표시

- **재매수 시나리오 지원**: 청산 후 재매수 시 별도 포지션으로 관리
  - **시간순 FIFO 매칭 로직 구현**:
    1. 거래를 날짜순으로 정렬
    2. 매수/매도를 순차적으로 매칭
    3. 누적 수량이 0이 되는 시점 = 1개 청산 완료
    4. 청산 후 새 매수 = 새로운 포지션 시작
    5. 각 청산마다 별도 레코드 생성
  - **지원 시나리오**:
    - 단순 청산: AAPL 100주 매수 → 100주 전량 매도 (1건 청산)
    - 재매수 후 보유: AAPL 100주 매수 → 100주 매도 (청산 1) → AAPL 50주 재매수 (새 포지션)
    - 재매수 후 재청산: AAPL 100주 매수 → 100주 매도 (청산 1) → AAPL 50주 재매수 → 50주 매도 (청산 2)
    - 같은 티커의 여러 청산 기록이 테이블에 별도 행으로 표시

- **스냅샷 재계산 헬퍼 함수**: 과거 거래 수정 시 스냅샷을 재계산하는 PostgreSQL 함수 추가
  - **함수명**: `recalculate_snapshots(p_start_date, p_end_date, p_account_id)`
  - **기능**:
    - 지정된 날짜 범위의 스냅샷을 재계산
    - 선택적 계좌 필터링 지원
    - 주식 평가액과 현금 잔고를 처음부터 다시 계산
    - UPSERT 패턴으로 기존 스냅샷 업데이트 또는 신규 생성
  - **사용 예시**:
    - `SELECT * FROM recalculate_snapshots('2024-10-14');` - 10월 14일부터 오늘까지 재계산
    - `SELECT * FROM recalculate_snapshots('2024-10-14', '2024-10-20');` - 특정 날짜 범위
    - `SELECT * FROM recalculate_snapshots('2024-10-14', CURRENT_DATE, '[UUID]'::uuid);` - 특정 계좌만
  - **문서**: `SNAPSHOT_RECALCULATION_GUIDE.md` 추가 (사용법, 예시, 주의사항)

### 🎨 UI/UX 개선

#### 추가됨
- **개요 페이지에 Market Today 섹션 추가**: 실시간 시장 지수 및 시장 심리 추적
  - **5열 레이아웃**:
    - S&P 500 (^GSPC): 가격 및 전일 대비 변동률
    - NASDAQ 100 (^NDX): 가격 및 전일 대비 변동률
    - KOSPI (^KS11): 가격 및 전일 대비 변동률
    - USD/KRW (KRW=X): 환율 및 전일 대비 변동률
    - Fear & Greed Index: CNN 공포탐욕지수 및 분류 배지
  - 색상 코딩 변동 지표: 초록색 (상승) / 빨간색 (하락) / 회색 (중립)
  - 최적 성능을 위한 5분 캐싱
  - 마지막 업데이트 타임스탬프는 KST 시간대 사용

- **개요 페이지의 색상 코딩 손익 지표**: 포트폴리오 성과에 대한 향상된 시각적 피드백
  - **총 자산 요약** (5열 레이아웃):
    - 총 손익 (KRW): 초록색 (수익) / 빨간색 (손실) / 회색 (중립)
    - 총 손익 (USD): 초록색 (수익) / 빨간색 (손실) / 회색 (중립)
    - 총 수익률 %: 초록색 (수익) / 빨간색 (손실) / 회색 (중립)
  - **계좌 성과 요약 카드**:
    - 계좌별 수익률 %: 위와 동일한 색상 코딩
  - 개별 계좌 페이지와 일관된 스타일링
  - 정확한 색상 제어 및 타이포그래피를 위한 HTML 마크다운

#### 변경됨
- **개요 페이지 레이아웃 최적화**:
  - 자산 요약에서 중복 환율 열 제거
  - 환율 정보는 이미 상단 정보 배너에 표시됨
  - 더 깔끔한 5열 레이아웃: 총 자산 (KRW/USD), 손익 (KRW/USD), 수익률 %

- **Fear & Greed Index 배지 색상 조정**:
  - Extreme Fear: #dc3545 (진한 빨강)
  - Fear: #e57373 (연한 빨강)
  - Neutral: #6c757d (회색)
  - Greed: #81c784 (연한 초록)
  - Extreme Greed: #2e7d32 (진한 초록)

### 📝 Technical Details

**Cache Architecture Changes**:
```
Layer 1: Edge Function (Hourly) → Yahoo Finance API → stock_prices table
Layer 2: Supabase Database → Primary cache storage
Layer 3: Streamlit → No caching (direct DB queries)
```

**Benefits**:
- Zero latency for new stock additions after Edge Function execution
- Immediate price reflection on page refresh
- Database handles all caching efficiently with indexed queries

**UI Color Coding Logic**:
```python
color = "green" if value > 0 else ("red" if value < 0 else "gray")
```

**Files Modified**:
- `calculations.py`:
  - 평단가 계산 수정: 수수료 포함 로직 추가 (lines 67-71)
    - `total_buy_cost = ((buy_txns['trade_price'] * buy_txns['quantity']) + buy_txns['fee'].fillna(0)).sum()`
  - 청산 손익 계산: 수수료 반영 (lines 398-406)
    - 매수 비용: `(txn['trade_price'] * txn['quantity']) + txn.get('fee', 0)`
    - 매도 수익: `(txn['trade_price'] * txn['quantity']) - txn.get('fee', 0)`
  - `calculate_closed_positions()` 함수 전면 재작성 (시간순 FIFO 로직, lines 264-371)
  - `_create_closed_record()` 헬퍼 함수 추가 (lines 374-427)
  - `calculate_win_rate()` 함수 추가 (lines 430-489)
  - `result` 컬럼 추가 (Win/Loss)

- `complete_schema.sql`:
  - `fee` 컬럼 추가: transactions 테이블에 수수료 컬럼 추가 (NUMERIC(15, 2), DEFAULT 0)
  - `stock_prices` 테이블 표준화: `price_cache`에서 `stock_prices`로 이름 변경
    - `current_price` 컬럼 추가 (기존 `price` 대체)
    - `is_active`, `fetch_error`, `retry_count` 컬럼 추가
  - `recalculate_snapshots()` 함수 추가: 과거 거래 수정 시 스냅샷 재계산 기능
    - 테이블 별칭 사용 (t, ct, pc)으로 컬럼 모호성 해결
    - RETURNS TABLE 컬럼명 변경 (result_account_id, result_currency, result_snapshot_id)
    - 날짜 범위 및 계좌 필터링 지원
  - RLS 정책 업데이트: `cash_transactions` 테이블에 공개 읽기 권한 추가

- `SNAPSHOT_RECALCULATION_GUIDE.md` (NEW FILE):
  - 스냅샷 재계산 함수 사용 가이드
  - 파라미터 설명 및 사용 예시
  - 시나리오별 활용법 (과거 거래 추가, 현금 거래 수정, 특정 계좌 수정)
  - 주의사항 및 성능 최적화 팁

- `app.py`:
  - Removed `@st.cache_data` from `get_current_prices()` (line 66)
  - Added Market Today section at top of Overview page (lines 143-198)
  - Added color-coded P&L display in Overview page
  - 거래 내역 테이블에 수수료 컬럼 추가 (lines 833-872)
    - 수수료 포맷팅: 0이면 '-' 표시, 그 외 통화 기호와 함께 표시
  - 💰 현금 내역 탭 추가 (lines 891-1028)
    - 4개 탭으로 변경: 현재 보유, 거래 내역, 현금 내역, 청산 포지션
    - KRW/USD 각각 4-column 요약, 현금 거래 테이블, 누적 잔고 계산
  - 원금 vs 계좌평가액 차트 추가 (lines 1339-1521)
    - 계좌별 차트 (2-column), 전체 포트폴리오 차트 (full-width)
    - USD → KRW 환율 변환, Plotly 인터랙티브 차트
  - `calculate_win_rate`, `get_cash_transactions`, `get_cash_transaction_summary` import 추가
  - 청산 포지션 탭에 승률 통계 섹션 추가

- `database.py`:
  - `get_cash_transaction_summary()`: PostgreSQL 타입 불일치 해결 (lines 329-357)
    - try-except 블록 추가, float() 타입 변환
    - 에러 처리 강화 및 기본값 반환

- `market_data.py` (NEW FILE):
  - Created module for real-time market data retrieval
  - `get_market_today()`: Fetches S&P 500, NASDAQ 100, KOSPI, USD/KRW, Fear & Greed Index
  - USD/KRW 다중 티커 시도 및 fallback 체인 (lines 72-119)
    - KRW=X, USDKRW=X 티커 시도
    - 유효성 검증 (1000-2000 KRW 범위)
    - exchange_rate.py 함수 재사용
  - `get_fgi_badge_color()`: Returns color code based on F&G classification
  - `get_change_color()`: Returns color based on change percentage
  - 5-minute TTL caching with error handling
  - Fear & Greed Index 배지 색상 조정 및 .title() 정규화

- `exchange_rate.py`:
  - Reduced TTL from 900s to 60s (line 10)
  - Added KST timezone conversion (lines 7, 128)
  - Updated timestamp format to include "KST" suffix (line 133)

- `requirements.txt`:
  - Added `fear-and-greed>=1.0.0` package dependency

- `README.md`:
  - 프로젝트 구조에 `market_data.py` 추가
  - Cron Job 일정 업데이트 (매일 21:00 UTC → 매시간 정각)
  - 버전 정보 업데이트 (2.0 → 0.1.2)

- `csv_import_templates/README.md`:
  - 필수 컬럼 테이블에 `fee` 컬럼 추가
  - 수수료 컬럼 설명 및 예시 추가

- `csv_import_templates/transactions_template.csv`:
  - CSV 템플릿에 `fee` 컬럼 추가
  - 샘플 데이터에 수수료 값 포함

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
