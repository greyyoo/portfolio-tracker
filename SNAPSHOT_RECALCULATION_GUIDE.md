# 스냅샷 재계산 가이드

과거 날짜의 거래 내역이나 현금 거래를 수정했을 때 포트폴리오 스냅샷을 재계산하는 방법입니다.

## 📋 개요

스냅샷은 매일 자동으로 생성되지만, 과거 날짜의 거래를 나중에 추가하거나 수정한 경우 해당 날짜의 스냅샷을 재계산해야 정확한 성과 추이를 확인할 수 있습니다.

## 🔧 사용 방법

### 1. 특정 날짜 하나만 재계산

```sql
-- 예시: 2024-10-14 스냅샷만 재계산 (모든 계좌)
SELECT * FROM recalculate_snapshots('2024-10-14', '2024-10-14');
```

### 2. 날짜 범위 재계산

```sql
-- 예시: 2024-10-14부터 오늘까지 모든 스냅샷 재계산
SELECT * FROM recalculate_snapshots('2024-10-14');

-- 예시: 2024-10-14부터 2024-10-20까지 재계산
SELECT * FROM recalculate_snapshots('2024-10-14', '2024-10-20');
```

### 3. 특정 계좌만 재계산

```sql
-- 예시: 특정 계좌의 특정 기간만 재계산
SELECT * FROM recalculate_snapshots(
    '2024-10-14',
    '2024-10-20',
    '[ACCOUNT_UUID]'::uuid
);
```

## 📊 함수 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `p_start_date` | DATE | ✅ | - | 재계산 시작 날짜 |
| `p_end_date` | DATE | ❌ | `CURRENT_DATE` | 재계산 종료 날짜 (오늘까지) |
| `p_account_id` | UUID | ❌ | `NULL` | 특정 계좌 UUID (NULL이면 전체 계좌) |

## 🎯 실행 결과

함수는 재계산된 스냅샷 정보를 반환합니다:

```
 recalculated_date | account_id | currency | snapshot_id
-------------------+------------+----------+-------------
 2024-10-14        | uuid...    | KRW      | uuid...
 2024-10-14        | uuid...    | USD      | uuid...
 2024-10-15        | uuid...    | KRW      | uuid...
 2024-10-15        | uuid...    | USD      | uuid...
```

## 💡 사용 예시

### 시나리오 1: 과거 거래 추가
10월 14일 거래를 10월 15일에 뒤늦게 입력한 경우:

```sql
-- 10월 14일부터 오늘까지 재계산
SELECT * FROM recalculate_snapshots('2024-10-14');
```

### 시나리오 2: 현금 거래 수정
10월 10일부터 14일까지 여러 RP 이자를 수정한 경우:

```sql
-- 10월 10일부터 오늘까지 재계산
SELECT * FROM recalculate_snapshots('2024-10-10');
```

### 시나리오 3: 특정 계좌만 수정
계좌 1번의 10월 14일 거래만 수정한 경우:

```sql
-- 계좌 UUID 조회
SELECT id, account_number, account_name FROM accounts;

-- 해당 계좌만 재계산
SELECT * FROM recalculate_snapshots(
    '2024-10-14',
    CURRENT_DATE,
    '계좌1의UUID'::uuid
);
```

## ⚠️ 주의사항

1. **날짜 순서**: `p_start_date`는 `p_end_date`보다 이전이어야 합니다.
2. **실행 시간**: 날짜 범위가 클수록 실행 시간이 오래 걸립니다.
3. **price_cache 의존성**: 현재 가격 캐시의 데이터를 사용하므로, 정확한 재계산을 위해서는 가격 데이터가 최신이어야 합니다.
4. **환율**: 현재 저장된 USD/KRW 환율을 사용합니다 (없으면 1300 기본값).

## 🔄 자동 재계산 vs 수동 재계산

### 자동 (Cron Job)
- 매시간 정각에 "오늘" 날짜 스냅샷 생성/업데이트
- 이미 존재하면 자동으로 UPDATE

### 수동 (이 함수)
- 과거 날짜 거래 수정 시 사용
- 원하는 날짜 범위 지정 가능
- 특정 계좌만 선택 가능

## 📝 추가 팁

### 전체 스냅샷 재생성
초기 설정이나 대규모 데이터 수정 후 전체 재계산:

```sql
-- 2024년 1월 1일부터 오늘까지 모든 스냅샷 재생성
SELECT * FROM recalculate_snapshots('2024-01-01');
```

### 실행 전 확인
스냅샷이 어떻게 변경될지 미리 확인하고 싶다면:

```sql
-- 기존 스냅샷 조회
SELECT snapshot_date, account_id, currency, stock_value, cash_balance, total_value
FROM portfolio_snapshots
WHERE snapshot_date = '2024-10-14'
ORDER BY account_id, currency;

-- 재계산 후 다시 조회하여 비교
```

## 🚀 성능 최적화

대량 재계산 시 성능 팁:
1. 특정 계좌만 지정하여 실행
2. 필요한 날짜 범위만 지정
3. 트래픽이 적은 시간대에 실행

