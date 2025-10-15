# CSV Import 가이드

Supabase 콘솔에서 거래 데이터를 CSV로 일괄 입력하는 방법을 설명합니다.

## 📋 transactions 테이블 CSV 템플릿

### 필수 컬럼

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| account_id | UUID | 계좌 ID (accounts 테이블에서 확인) | `550e8400-e29b-41d4-a716-446655440000` |
| transaction_type | TEXT | 거래 유형 (BUY 또는 SELL) | `BUY` |
| country | TEXT | 국가 코드 (KOR 또는 USA) | `USA` |
| stock_name | TEXT | 주식명 | `Apple Inc.` |
| ticker | TEXT | 티커 심볼 (한국 주식은 .KS 또는 .KQ 접미사 필수) | `AAPL` 또는 `005930.KS` |
| transaction_date | DATE | 거래 날짜 (YYYY-MM-DD) | `2024-01-15` |
| trade_price | NUMERIC | 거래 가격 | `150.25` |
| currency | TEXT | 통화 (KRW 또는 USD) | `USD` |
| quantity | INTEGER | 수량 | `10` |
| fee | NUMERIC | 거래 수수료 (선택사항, 없으면 0 또는 빈칸) | `1.5` |

### 통화 규칙

- **계좌 1-3**: USD만 허용
- **계좌 4**: KRW만 허용
- **계좌 5**: USD + KRW 모두 허용

⚠️ **중요**: 데이터베이스 트리거가 계좌별 통화 제한을 검증합니다. 잘못된 통화로 입력하면 오류가 발생합니다.

### 티커 형식

- **한국 주식**: 반드시 `.KS` (KOSPI) 또는 `.KQ` (KOSDAQ) 접미사 포함
  - 예: `005930.KS` (삼성전자), `035720.KS` (카카오)
- **미국 주식**: 티커만 입력
  - 예: `AAPL` (애플), `MSFT` (마이크로소프트)

## 🔧 Supabase에서 CSV Import 방법

### 1. 계좌 ID 확인

1. Supabase 프로젝트 대시보드 접속
2. **Table Editor** → **accounts** 테이블 선택
3. 각 계좌의 `id` (UUID) 복사

### 2. CSV 파일 준비

1. `transactions_template.csv` 파일을 복사
2. `account_id`를 실제 UUID로 교체
3. 거래 데이터 입력
   - 날짜 형식: `YYYY-MM-DD`
   - 통화에 맞는 가격 입력 (KRW는 소수점 없음, USD는 소수점 2자리)

### 3. Supabase에서 Import

1. **Table Editor** → **transactions** 테이블 선택
2. 우측 상단 **Insert** → **Import data from CSV** 클릭
3. 준비한 CSV 파일 업로드
4. 컬럼 매핑 확인
5. **Import** 클릭

### 4. 오류 처리

Import 중 오류 발생 시:
- **Currency restriction error**: 계좌의 `allowed_currencies`와 거래의 `currency` 불일치
- **Foreign key error**: `account_id`가 존재하지 않음
- **Check constraint error**: 수량 또는 가격이 0 이하

## 📊 예시 데이터

### 계좌 1 (USD 전용)
```csv
account_id,transaction_type,country,stock_name,ticker,transaction_date,trade_price,currency,quantity
uuid-of-account-1,BUY,USA,Apple Inc.,AAPL,2024-01-15,150.25,USD,10
uuid-of-account-1,BUY,USA,Microsoft Corp.,MSFT,2024-01-20,380.50,USD,5
uuid-of-account-1,SELL,USA,Apple Inc.,AAPL,2024-02-10,155.00,USD,3
```

### 계좌 4 (KRW 전용)
```csv
account_id,transaction_type,country,stock_name,ticker,transaction_date,trade_price,currency,quantity
uuid-of-account-4,BUY,KOR,삼성전자,005930.KS,2024-01-10,72000,KRW,10
uuid-of-account-4,BUY,KOR,SK하이닉스,000660.KS,2024-01-15,135000,KRW,5
uuid-of-account-4,SELL,KOR,삼성전자,005930.KS,2024-02-20,75000,KRW,3
```

### 계좌 5 (혼합)
```csv
account_id,transaction_type,country,stock_name,ticker,transaction_date,trade_price,currency,quantity
uuid-of-account-5,BUY,USA,Tesla Inc.,TSLA,2024-01-10,210.50,USD,10
uuid-of-account-5,BUY,KOR,NAVER,035420.KS,2024-01-15,220000,KRW,5
```

## 🔍 데이터 확인

Import 후:
1. Streamlit 앱 새로고침
2. Overview 페이지에서 전체 계좌 확인
3. 개별 계좌 페이지에서 거래 내역 확인

## 💡 팁

- **Excel에서 작업**: CSV는 Excel에서 편집하고 "CSV UTF-8" 형식으로 저장
- **대량 입력**: 여러 거래를 한 번에 입력하려면 모든 행을 CSV에 포함
- **백업**: Import 전 Supabase에서 데이터 백업 권장
- **날짜 정렬**: 거래 날짜 순서대로 정렬하면 관리가 편리함
