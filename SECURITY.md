# 🔒 보안 가이드 (Security Guide)

이 문서는 프로젝트를 public GitHub repository에 안전하게 공개하기 위한 보안 가이드입니다.

## ✅ 보안 검토 완료 (Security Audit Completed)

**검토 날짜**: 2025-10-14
**검토 범위**: 모든 프로젝트 파일 및 설정

---

## 🔐 민감한 정보 보호 (Sensitive Information Protection)

### 1. 환경 변수 파일 (Environment Variables)

#### ⚠️ **절대 커밋하지 말 것 (NEVER COMMIT)**

- **`.env`**: Supabase URL 및 anon key 포함
- **`supabase/.temp/`**: Supabase 프로젝트 설정 및 연결 정보
- **`.streamlit/secrets.toml`**: Streamlit Cloud 배포 시 credential

#### ✅ **안전하게 제공됨 (Safe to Commit)**

- **`.env.example`**: 환경 변수 템플릿 (실제 값 없음)
- **`.gitignore`**: 민감한 파일 목록

### 2. Supabase 인증 정보 (Supabase Credentials)

프로젝트는 다음 Supabase 인증 정보를 사용합니다:

- **Supabase URL**: 프로젝트 공개 URL (예: `https://[PROJECT_REF].supabase.co`)
- **Anon Key**: 공개 읽기 전용 키 (Row Level Security로 보호됨)

#### 🔑 **Anon Key 보안 특성**

- ✅ **Read-only access**: RLS 정책으로 SELECT만 허용
- ✅ **No write operations**: INSERT/UPDATE/DELETE 불가
- ✅ **Public dashboard용**: 데이터 조회만 가능
- ⚠️ **노출 시 위험도**: 낮음 (읽기 전용이지만 공개 권장하지 않음)

#### 🔒 **Service Role Key (절대 노출 금지)**

- ❌ **Edge Function에서만 사용**: 서버 사이드 전용
- ❌ **Full database access**: 모든 테이블 읽기/쓰기 가능
- ❌ **노출 시 위험도**: 매우 높음 (즉시 키 재발급 필요)
- ✅ **Supabase 환경 변수로 관리**: Edge Function 배포 시 자동 주입

---

## 📝 .gitignore 설정 (Git Ignore Configuration)

### 제외된 파일 및 디렉토리

```gitignore
# 환경 변수 (CRITICAL)
.env
.env.local
.env.*.local

# Supabase 로컬 설정
supabase/.temp/
supabase/.branches/
.supabase/

# Python 가상환경
venv/
__pycache__/

# IDE 설정
.vscode/
.idea/

# Streamlit 비밀 정보
.streamlit/secrets.toml

# OS 파일
.DS_Store
Thumbs.db

# 로그 파일
*.log
*.tmp
```

---

## 🚀 Repository 공개 전 체크리스트

### 1. 필수 확인 사항 (Before Making Public)

- [x] `.env` 파일이 .gitignore에 포함됨
- [x] `.env.example` 템플릿 생성됨 (실제 값 없음)
- [x] `README.md`에서 실제 project-ref 제거됨
- [x] `supabase/.temp/` 디렉토리가 .gitignore에 포함됨
- [x] 모든 Python 파일에 하드코딩된 credential 없음 확인
- [x] Edge Function 코드에서 환경 변수 사용 확인

### 2. Git 초기화 및 첫 커밋

```bash
# Git 초기화 (아직 안 했다면)
git init

# .gitignore 확인
cat .gitignore

# 스테이징 (민감한 파일 제외됨)
git add .

# .env가 제외되었는지 확인
git status

# .env가 목록에 있으면 안됨! (있으면 STOP)
# 없으면 진행

# 첫 커밋
git commit -m "Initial commit: Portfolio tracker with multi-account support"

# GitHub 원격 저장소 추가
git remote add origin https://github.com/[YOUR_USERNAME]/[YOUR_REPO].git

# Push
git push -u origin main
```

### 3. 실수로 .env를 커밋한 경우 (Emergency Recovery)

```bash
# ⚠️ .env를 실수로 커밋한 경우 즉시 조치:

# 1. Git history에서 완전 제거
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# 2. 원격 저장소에 force push (이미 push한 경우)
git push origin --force --all

# 3. Supabase 키 즉시 재발급
# Supabase Dashboard → Settings → API → Reset keys

# 4. .env.example만 남기고 .env는 로컬에만 보관
```

---

## 🔒 Row Level Security (RLS) 정책

### Public Access 제한

데이터베이스는 RLS 정책으로 보호됩니다:

```sql
-- 모든 테이블에 RLS 활성화
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_cache ENABLE ROW LEVEL SECURITY;

-- Public은 SELECT만 가능
CREATE POLICY "Allow public read access to accounts"
    ON accounts FOR SELECT
    TO public
    USING (true);

-- INSERT/UPDATE/DELETE는 service_role만 가능 (Edge Function, Supabase Console)
```

### 보안 계층

1. **Application Layer**: Streamlit app은 read-only
2. **Database Layer**: RLS 정책으로 public은 SELECT만 허용
3. **API Layer**: Anon key는 RLS 정책 적용됨
4. **Server Layer**: Service role key는 Edge Function에서만 사용

---

## 🌐 Public Repository 운영 가이드

### 공개 가능 정보

✅ **안전하게 공개 가능**:
- 소스 코드 (Python, TypeScript)
- 데이터베이스 스키마 (SQL)
- 프로젝트 구조 및 설정 파일
- 문서 및 가이드
- CSV 템플릿
- `.env.example` (템플릿만)

❌ **절대 공개 금지**:
- `.env` 파일 (실제 credentials)
- Supabase Service Role Key
- 개인 거래 데이터 (이미 데이터베이스에만 저장)
- API keys 또는 access tokens

### Contributors 가이드

다른 사람이 프로젝트를 clone하여 사용하려면:

1. **Repository Clone**
   ```bash
   git clone https://github.com/[YOUR_USERNAME]/[YOUR_REPO].git
   cd [YOUR_REPO]
   ```

2. **환경 설정**
   ```bash
   # .env 파일 생성
   cp .env.example .env

   # .env 파일 편집하여 본인의 Supabase credentials 입력
   nano .env
   ```

3. **Supabase 프로젝트 생성**
   - [Supabase](https://supabase.com)에서 새 프로젝트 생성
   - SQL Editor에서 `complete_schema.sql` 실행
   - API keys 복사하여 `.env`에 입력

4. **애플리케이션 실행**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   streamlit run app.py
   ```

---

## 📊 보안 모니터링

### 주기적 점검 항목

- [ ] GitHub에 `.env` 파일이 노출되지 않았는지 확인
- [ ] Supabase Dashboard에서 API 사용량 모니터링
- [ ] 의심스러운 데이터베이스 접근 로그 확인
- [ ] Edge Function 로그에서 오류 확인

### 보안 업데이트

- 정기적으로 의존성 업데이트 (pip, npm)
- Supabase API key 주기적 재발급 (선택사항)
- RLS 정책 변경 시 테스트 수행

---

## 📞 보안 이슈 리포트

보안 취약점을 발견한 경우:

1. **GitHub Issue를 사용하지 마세요** (공개됨)
2. **Repository owner에게 직접 연락**
3. **문제 설명 및 재현 방법 제공**
4. **수정 후 공개 가능**

---

**최종 업데이트**: 2025-10-14
**보안 감사자**: Claude Code
