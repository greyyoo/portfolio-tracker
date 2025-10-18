# Market Indices 과거 데이터 채우기 가이드

과거에 누락된 시장 지수 데이터(SPX, NDX, KOSPI, USD/KRW)를 채우는 방법을 설명합니다.

## 📋 목차

1. [사전 준비](#사전-준비)
2. [빠른 시작](#빠른-시작)
3. [상세 사용법](#상세-사용법)
4. [주의사항](#주의사항)
5. [트러블슈팅](#트러블슈팅)

---

## 사전 준비

### 1. 환경 변수 설정

프로젝트 루트에 `.env` 파일이 있는지 확인하고, 없다면 생성:

```bash
# .env
PUBLIC_SUPABASE_URL=your_project_url
PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

**또는** 환경 변수로 직접 설정:

```bash
export PUBLIC_SUPABASE_URL='https://mhdtwomhgtryhzujpvjg.supabase.co'
export PUBLIC_SUPABASE_ANON_KEY='your_anon_key'
```

### 2. 필요한 Python 패키지 설치

```bash
pip install yfinance supabase pandas python-dotenv
```

또는 프로젝트 requirements.txt 사용:

```bash
pip install -r requirements.txt
```

---

## 빠른 시작

### 기본 사용법

```bash
# 2025년 10월 1일부터 어제까지 데이터 채우기
python backfill_market_indices.py --start-date 2025-10-01

# 특정 기간 지정
python backfill_market_indices.py --start-date 2025-10-01 --end-date 2025-10-17

# 실제 저장 전 시뮬레이션 (권장)
python backfill_market_indices.py --start-date 2025-10-01 --dry-run
```

---

## 상세 사용법

### 명령행 옵션

| 옵션 | 필수 | 설명 | 예시 |
|------|------|------|------|
| `--start-date` | ✓ | 시작 날짜 (YYYY-MM-DD) | `2025-10-01` |
| `--end-date` | ✗ | 종료 날짜 (기본값: 어제) | `2025-10-17` |
| `--dry-run` | ✗ | 실제 저장 없이 시뮬레이션만 수행 | - |

### 단계별 실행 과정

#### 1단계: Dry Run으로 확인

실제 데이터를 저장하기 전에 시뮬레이션으로 확인:

```bash
python backfill_market_indices.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-17 \
  --dry-run
```

**출력 예시:**
```
🔍 DRY RUN MODE
Date range: 2025-10-01 to 2025-10-17

📊 Fetching historical data...
  Fetching ^GSPC...
    ✓ Fetched 12 records
  Fetching ^NDX...
    ✓ Fetched 12 records
  Fetching ^KS11...
    ✓ Fetched 11 records
  Fetching KRW=X...
    ✓ Fetched 15 records

🔗 Merging data...
  ✓ Total records: 12
  ⏭️  Skipped weekends: 4

🔍 DRY RUN: Would process 12 records

Sample data (first 5 records):
        Date  spx_close  ndx_close  kospi_close  usd_krw_rate
  2025-10-01    5000.00   17500.00      2650.00       1320.50
  2025-10-02    5010.00   17520.00      2655.00       1321.00
  ...
```

#### 2단계: 실제 데이터 저장

확인 후 실제 저장:

```bash
python backfill_market_indices.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-17
```

**출력 예시:**
```
▶️  BACKFILL START
Date range: 2025-10-01 to 2025-10-17

📊 Fetching historical data...
  ...

💾 Storing data to Supabase...
  ✓ 2025-10-01: SPX=5000.00, NDX=17500.00, KOSPI=2650.00, USD/KRW=1320.5000
  ✓ 2025-10-02: SPX=5010.00, NDX=17520.00, KOSPI=2655.00, USD/KRW=1321.0000
  ...

============================================================
📊 BACKFILL SUMMARY
============================================================
Total days processed:  12
Records inserted:      12
Records updated:       0
Weekends skipped:      4
Errors:                0
============================================================

✓ Backfill completed successfully!
```

#### 3단계: 데이터 검증

Supabase SQL Editor에서 확인:

```sql
-- 최근 저장된 데이터 확인
SELECT
    snapshot_date,
    spx_close,
    ndx_close,
    kospi_close,
    usd_krw_rate,
    created_at
FROM market_indices
ORDER BY snapshot_date DESC
LIMIT 20;

-- 특정 기간 데이터 확인
SELECT COUNT(*) as total_records
FROM market_indices
WHERE snapshot_date BETWEEN '2025-10-01' AND '2025-10-17';

-- 누락된 날짜 찾기 (평일만)
WITH date_series AS (
    SELECT generate_series(
        '2025-10-01'::date,
        '2025-10-17'::date,
        '1 day'::interval
    )::date AS date
)
SELECT date
FROM date_series
WHERE EXTRACT(DOW FROM date) NOT IN (0, 6)  -- 주말 제외
  AND date NOT IN (SELECT snapshot_date FROM market_indices)
ORDER BY date;
```

---

## 주의사항

### ✅ 자동 처리되는 사항

1. **주말 제외**: 토요일(6), 일요일(0) 데이터는 자동으로 건너뜀
2. **중복 방지**: 기존 데이터가 있으면 `COALESCE`로 병합 (NULL 값만 업데이트)
3. **타임존**: Yahoo Finance는 UTC 기준 데이터 제공
4. **공휴일**: 시장 휴무일은 Yahoo Finance가 데이터를 반환하지 않으므로 자연스럽게 제외됨

### ⚠️ 주의할 점

1. **데이터 가용성**:
   - Yahoo Finance에서 데이터를 가져오므로 네트워크 연결 필요
   - 일부 오래된 날짜는 데이터가 없을 수 있음
   - 한국 시장(KOSPI)은 한국 공휴일에 데이터 없음

2. **대량 데이터 처리**:
   - 너무 긴 기간(1년 이상)은 분할해서 처리 권장
   - 예: 2024년 전체 → 월별로 나눠서 실행

3. **기존 데이터 보호**:
   - `upsert_market_indices` 함수는 NULL 값만 업데이트
   - 기존 값이 있으면 유지됨 (덮어쓰지 않음)

---

## 트러블슈팅

### 문제 1: "PUBLIC_SUPABASE_URL and PUBLIC_SUPABASE_ANON_KEY must be set" 오류

**원인**: 환경 변수가 설정되지 않음

**해결**:
```bash
# 방법 1: .env 파일 생성
echo "PUBLIC_SUPABASE_URL=your_url" > .env
echo "PUBLIC_SUPABASE_ANON_KEY=your_key" >> .env

# 방법 2: 환경 변수 직접 설정
export PUBLIC_SUPABASE_URL='your_url'
export PUBLIC_SUPABASE_ANON_KEY='your_key'
```

### 문제 2: "No data returned for ^KS11" 경고

**원인**: 한국 시장 데이터 없음 (공휴일, 휴무일 등)

**해결**: 정상 동작. 해당 날짜는 건너뛰어짐

### 문제 3: 일부 날짜만 저장되고 나머지는 건너뛰어짐

**원인**:
- 주말 데이터 자동 제외
- 시장 휴무일
- 기존 데이터가 이미 있는 경우

**확인**:
```bash
# Dry run으로 어떤 데이터가 처리되는지 확인
python backfill_market_indices.py --start-date 2025-10-01 --dry-run
```

### 문제 4: "Error fetching ^GSPC" 오류

**원인**:
- 네트워크 연결 문제
- Yahoo Finance API 일시적 오류

**해결**:
```bash
# 잠시 후 재시도
python backfill_market_indices.py --start-date 2025-10-01

# 또는 더 짧은 기간으로 분할
python backfill_market_indices.py --start-date 2025-10-01 --end-date 2025-10-07
python backfill_market_indices.py --start-date 2025-10-08 --end-date 2025-10-14
```

### 문제 5: 스크립트가 중간에 멈춤

**원인**:
- 네트워크 타임아웃
- Supabase API 제한

**해결**:
```bash
# 마지막 성공한 날짜부터 다시 시작
SELECT MAX(snapshot_date) FROM market_indices;  -- Supabase에서 확인

python backfill_market_indices.py --start-date [마지막_날짜+1일]
```

---

## 실제 사용 예시

### 예시 1: 최근 1주일 데이터 채우기

```bash
# 1. Dry run으로 확인
python backfill_market_indices.py \
  --start-date 2025-10-11 \
  --end-date 2025-10-17 \
  --dry-run

# 2. 실제 저장
python backfill_market_indices.py \
  --start-date 2025-10-11 \
  --end-date 2025-10-17
```

### 예시 2: 2025년 10월 전체 채우기

```bash
python backfill_market_indices.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-31
```

### 예시 3: 어제 데이터만 채우기

```bash
# end-date를 생략하면 자동으로 어제까지
python backfill_market_indices.py --start-date 2025-10-17
```

### 예시 4: 2024년 전체 데이터 채우기 (월별 분할)

```bash
for month in {01..12}; do
  python backfill_market_indices.py \
    --start-date 2024-${month}-01 \
    --end-date 2024-${month}-31
  sleep 5  # API 부하 방지
done
```

---

## FAQ

**Q: 주말 데이터도 저장할 수 있나요?**
A: 아니요. 시장이 열리지 않으므로 주말 데이터는 자동으로 제외됩니다.

**Q: 기존 데이터를 덮어쓸 수 있나요?**
A: 부분적으로 가능합니다. `upsert_market_indices` 함수는 `COALESCE`를 사용하므로 NULL 값만 업데이트됩니다. 완전히 덮어쓰려면 먼저 DELETE 후 재실행하세요.

**Q: 얼마나 오래된 데이터까지 가져올 수 있나요?**
A: Yahoo Finance에서 제공하는 범위 내에서 가능합니다. 일반적으로 10년 이상의 과거 데이터를 지원합니다.

**Q: 에러가 발생하면 어떻게 하나요?**
A: 에러가 발생한 날짜는 건너뛰고 계속 진행됩니다. 완료 후 Summary에서 에러 개수를 확인할 수 있습니다.

**Q: 매일 자동으로 실행하려면?**
A: Edge Function(`update-stock-prices`)이 이미 매시간 실행되므로 별도로 자동화할 필요 없습니다. 이 스크립트는 **과거 누락 데이터**를 채우는 용도입니다.

---

## 관련 파일

- **스크립트**: `backfill_market_indices.py`
- **Edge Function**: `supabase/functions/update-stock-prices/index.ts`
- **DB 함수**: `upsert_market_indices()` in `complete_schema.sql`
- **테이블**: `market_indices`
