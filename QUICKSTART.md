# ⚡ 빠른 시작 가이드

**5분 안에** 포트폴리오 트래커를 실행하세요!

---

## 📋 사전 요구사항

- **Python 3.9+** 설치
- **Git** 설치
- **Supabase 계정** (무료 플랜 가능!)

---

## 🚀 설정 단계

### 1️⃣ Repository Clone (1분)

```bash
git clone https://github.com/greyyoo/portfolio-tracker.git
cd portfolio-tracker
```

### 2️⃣ 의존성 설치 (1분)

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate  # Windows

# 패키지 설치
pip install -r requirements.txt
```

### 3️⃣ Supabase 설정 (2분)

1. [Supabase](https://supabase.com)에 접속 → 새 프로젝트 생성
2. **Settings → API**에서 `Project URL`과 `anon key` 복사
3. **SQL Editor** 열기 → `complete_schema.sql` 전체 내용 붙여넣기 → 실행
4. ✅ 확인: "5 accounts created" 메시지

### 4️⃣ 환경 변수 설정 (30초)

```bash
# 템플릿 복사
cp .env.example .env

# .env 파일을 Supabase credentials로 편집
nano .env  # 또는 원하는 에디터 사용
```

credentials 입력:
```env
PUBLIC_SUPABASE_URL=https://[YOUR_PROJECT_REF].supabase.co
PUBLIC_SUPABASE_ANON_KEY=[YOUR_ANON_KEY]
```

### 5️⃣ 앱 실행 (30초)

```bash
streamlit run app.py
```

🎉 **완료!** 브라우저가 `http://localhost:8501`로 자동 열립니다.

---

## 📊 첫 거래 입력하기

### 방법 A: Supabase Console (처음 사용 시 권장)

1. Supabase Dashboard → **Table Editor** → `transactions`
2. **Insert** → **Insert row** 클릭
3. 필드 입력:
   - `account_id`: `accounts` 테이블에서 UUID 복사 (예: Account 1)
   - `transaction_type`: `BUY`
   - `country`: `USA`
   - `stock_name`: `Apple Inc.`
   - `ticker`: `AAPL`
   - `transaction_date`: `2024-01-15`
   - `trade_price`: `150.25`
   - `currency`: `USD`
   - `quantity`: `10`
4. **Save** 클릭

### 방법 B: CSV 일괄 입력 (대량 거래)

1. `csv_import_templates/transactions_template.csv` 편집
2. `[REPLACE_WITH_YOUR_ACCOUNT_UUID]`를 실제 UUID로 교체
3. Supabase → **Table Editor** → `transactions` → **Insert** → **Import data from CSV**

---

## 🔄 대시보드 새로고침

Streamlit 앱(`http://localhost:8501`)으로 돌아가서 새로고침 → 거래 내역 확인!

---

## 🎯 다음 단계

- **거래 추가하기**: CSV 임포트를 사용하여 더 많은 거래 입력
- **계좌 설정**: `accounts` 테이블에서 계좌명, 초기 금액 수정
- **자동 업데이트 활성화** (선택사항): Edge Function 배포 - README 참조
- **현금 거래 추가**: RP 이자, 입출금 기록

---

## ❓ 문제 해결

### 에러: "Supabase credentials not found"
→ `.env` 파일이 존재하고 올바른 값이 입력되었는지 확인

### 에러: "Currency not allowed for this account"
→ `accounts` 테이블에서 계좌의 `allowed_currencies` 확인

### 한국 주식 가격이 표시되지 않음
→ 티커에 `.KS` 또는 `.KQ` 접미사가 있는지 확인 (예: `005930.KS`)

### 앱이 로딩되지 않음
→ 가상환경이 활성화되었는지 확인: `source venv/bin/activate`

---

## 📚 추가 도움이 필요하신가요?

- **전체 가이드**: [README.md](README.md) 참조
- **보안**: [SECURITY.md](SECURITY.md) 참조
- **CSV 임포트**: [csv_import_templates/README.md](csv_import_templates/README.md) 참조
- **이슈**: [GitHub Issues](https://github.com/greyyoo/portfolio-tracker/issues)

---

**행복한 투자 추적!** 📈
