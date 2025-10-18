"""
Database operations module for Supabase CRUD operations - Multi-account support.
"""
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
from typing import Dict, List, Optional
import pandas as pd


def init_supabase() -> Client:
    """Supabase 클라이언트 초기화"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ========== Account Management Functions ==========

def get_all_accounts(supabase: Client) -> pd.DataFrame:
    """
    모든 계좌 조회

    Returns:
        계좌 정보 DataFrame (account_number 순서)
    """
    response = supabase.table('accounts').select('*').order('account_number').execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


def get_account_by_id(supabase: Client, account_id: str) -> Dict:
    """
    특정 계좌 조회 (ID로)

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID

    Returns:
        계좌 정보 딕셔너리
    """
    response = supabase.table('accounts').select('*').eq('id', account_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}


def get_account_by_number(supabase: Client, account_number: int) -> Dict:
    """
    특정 계좌 조회 (번호로)

    Args:
        supabase: Supabase 클라이언트
        account_number: 계좌 번호 (1-5)

    Returns:
        계좌 정보 딕셔너리
    """
    response = supabase.table('accounts').select('*').eq('account_number', account_number).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return {}


def update_account(supabase: Client, account_id: str, account_data: Dict) -> Dict:
    """
    계좌 정보 업데이트

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID
        account_data: 업데이트할 데이터
            - account_name: 계좌명 (optional)
            - strategy_description: 전략 설명 (optional)
            - initial_seed_money_krw: 초기 투자금 KRW (optional)
            - initial_seed_money_usd: 초기 투자금 USD (optional)

    Returns:
        업데이트된 데이터
    """
    response = supabase.table('accounts').update(account_data).eq('id', account_id).execute()
    return response.data


# ========== Transaction Functions ==========

def insert_transaction(supabase: Client, transaction_data: Dict) -> Dict:
    """
    거래 데이터 삽입

    Args:
        supabase: Supabase 클라이언트
        transaction_data: 거래 정보 딕셔너리
            - account_id: 계좌 UUID (REQUIRED)
            - transaction_type: 'BUY' or 'SELL'
            - country: 'KOR' or 'USA'
            - stock_name: 주식명
            - ticker: 티커 심볼
            - transaction_date: 거래 날짜 (YYYY-MM-DD)
            - trade_price: 거래 가격
            - currency: 'KRW' or 'USD'
            - quantity: 수량

    Returns:
        삽입된 데이터

    Note:
        Database trigger will automatically validate currency restriction
    """
    response = supabase.table('transactions').insert(transaction_data).execute()
    return response.data


def get_all_transactions(supabase: Client) -> pd.DataFrame:
    """모든 거래 내역 조회 (최신순)"""
    response = supabase.table('transactions').select('*').order('transaction_date', desc=True).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


def get_transactions_by_account(supabase: Client, account_id: str) -> pd.DataFrame:
    """
    특정 계좌의 거래 내역 조회

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID

    Returns:
        거래 내역 DataFrame (날짜 역순)
    """
    response = supabase.table('transactions').select('*').eq('account_id', account_id).order('transaction_date', desc=True).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


def get_transactions_by_account_and_ticker(supabase: Client, account_id: str, ticker: str) -> pd.DataFrame:
    """
    특정 계좌의 특정 티커 거래 내역 조회

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID
        ticker: 티커 심볼

    Returns:
        거래 내역 DataFrame (날짜순)
    """
    response = (supabase.table('transactions')
                .select('*')
                .eq('account_id', account_id)
                .eq('ticker', ticker)
                .order('transaction_date')
                .execute())
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


def get_transactions_by_ticker(supabase: Client, ticker: str) -> pd.DataFrame:
    """특정 티커의 거래 내역 조회 (전체 계좌, 날짜순)"""
    response = supabase.table('transactions').select('*').eq('ticker', ticker).order('transaction_date').execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


def get_transactions_by_currency(supabase: Client, currency: str) -> pd.DataFrame:
    """특정 통화의 거래 내역 조회 (전체 계좌)"""
    response = supabase.table('transactions').select('*').eq('currency', currency).order('transaction_date', desc=True).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


# ========== Stock Price Cache Functions ==========

def get_cached_price(supabase: Client, ticker: str) -> Optional[float]:
    """
    캐시된 주식 가격 조회

    Args:
        supabase: Supabase 클라이언트
        ticker: 티커 심볼

    Returns:
        현재가 (float) 또는 None (캐시 없음)
    """
    response = (supabase.table('stock_prices')
                .select('current_price, last_updated, fetch_error')
                .eq('ticker', ticker)
                .eq('is_active', True)
                .execute())

    if response.data and len(response.data) > 0:
        price_data = response.data[0]
        # 에러가 없는 경우에만 가격 반환
        if price_data.get('fetch_error') is None:
            return float(price_data['current_price'])

    return None


def get_all_cached_prices(supabase: Client) -> pd.DataFrame:
    """
    모든 활성 주식의 캐시된 가격 조회

    Returns:
        ticker, current_price, currency, last_updated DataFrame
    """
    response = (supabase.table('stock_prices')
                .select('ticker, current_price, currency, last_updated, fetch_error')
                .eq('is_active', True)
                .order('ticker')
                .execute())

    df = pd.DataFrame(response.data) if response.data else pd.DataFrame()

    # 에러가 있는 항목 제외
    if not df.empty:
        df = df[df['fetch_error'].isna()].copy()

    return df


def get_cached_prices_by_tickers(supabase: Client, tickers: List[str]) -> Dict[str, float]:
    """
    여러 티커의 캐시된 가격 일괄 조회

    Args:
        supabase: Supabase 클라이언트
        tickers: 티커 리스트

    Returns:
        {ticker: price} 딕셔너리
    """
    if not tickers:
        return {}

    response = (supabase.table('stock_prices')
                .select('ticker, current_price')
                .in_('ticker', tickers)
                .eq('is_active', True)
                .is_('fetch_error', 'null')  # 에러 없는 것만
                .execute())

    return {item['ticker']: float(item['current_price'])
            for item in response.data} if response.data else {}


def get_price_cache_status(supabase: Client) -> Dict:
    """
    가격 캐시 상태 조회 (모니터링용)

    Returns:
        {
            'total_active': 전체 활성 종목 수,
            'successful': 성공적으로 가져온 종목 수,
            'failed': 실패한 종목 수,
            'last_update': 가장 최근 업데이트 시간,
            'stale_count': 2일 이상 업데이트 안된 종목 수
        }
    """
    # 전체 통계
    response = supabase.table('stock_prices').select('*').eq('is_active', True).execute()

    if not response.data:
        return {
            'total_active': 0,
            'successful': 0,
            'failed': 0,
            'last_update': None,
            'stale_count': 0
        }

    df = pd.DataFrame(response.data)

    # 최근 업데이트 시간
    df['last_updated'] = pd.to_datetime(df['last_updated'])
    last_update = df['last_updated'].max()

    # 2일 이상 된 데이터
    stale_threshold = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=2)
    stale_count = (df['last_updated'] < stale_threshold).sum()

    return {
        'total_active': len(df),
        'successful': df['fetch_error'].isna().sum(),
        'failed': df['fetch_error'].notna().sum(),
        'last_update': last_update.isoformat() if pd.notna(last_update) else None,
        'stale_count': int(stale_count)
    }


# Note: user_settings table is no longer used in multi-account system
# Each account has its own seed money in the accounts table


# ========== Cash Transaction Functions ==========

def get_cash_transactions(supabase: Client, account_id: Optional[str] = None) -> pd.DataFrame:
    """
    현금 거래 내역 조회 (입금, 출금, RP 이자)

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID (선택적 - None이면 전체 계좌)

    Returns:
        현금 거래 내역 DataFrame
    """
    query = supabase.table('cash_transactions').select('*').order('transaction_date', desc=True)

    if account_id:
        query = query.eq('account_id', account_id)

    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


def get_cash_transaction_summary(supabase: Client, account_id: str, currency: str) -> Dict:
    """
    현금 거래 요약 정보 조회 (DB 함수 사용)

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID
        currency: 통화 ('KRW' 또는 'USD')

    Returns:
        {
            'initial_seed': 초기 투자금,
            'total_deposits': 총 입금액,
            'total_withdrawals': 총 출금액,
            'total_rp_interest': 총 RP 이자,
            'total_adjustments_increase': 총 조정(+),
            'total_adjustments_decrease': 총 조정(-),
            'stock_invested': 주식 투자금,
            'current_cash_balance': 현재 현금 잔고
        }
    """
    try:
        response = supabase.rpc('get_cash_transaction_summary', {
            'p_account_id': account_id,
            'p_currency': currency
        }).execute()

        if response.data and len(response.data) > 0:
            # float 타입으로 변환하여 타입 불일치 해결
            result = response.data[0]
            return {
                'initial_seed': float(result.get('initial_seed', 0)),
                'total_deposits': float(result.get('total_deposits', 0)),
                'total_withdrawals': float(result.get('total_withdrawals', 0)),
                'total_rp_interest': float(result.get('total_rp_interest', 0)),
                'total_adjustments_increase': float(result.get('total_adjustments_increase', 0)),
                'total_adjustments_decrease': float(result.get('total_adjustments_decrease', 0)),
                'stock_invested': float(result.get('stock_invested', 0)),
                'current_cash_balance': float(result.get('current_cash_balance', 0))
            }
    except Exception as e:
        print(f"Error fetching cash transaction summary: {e}")

    # 데이터가 없거나 오류 발생 시 기본값 반환
    return {
        'initial_seed': 0.0,
        'total_deposits': 0.0,
        'total_withdrawals': 0.0,
        'total_rp_interest': 0.0,
        'total_adjustments_increase': 0.0,
        'total_adjustments_decrease': 0.0,
        'stock_invested': 0.0,
        'current_cash_balance': 0.0
    }


def calculate_cash_balance(supabase: Client, account_id: str, currency: str) -> float:
    """
    현재 현금 잔고 계산 (DB 함수 사용)

    Formula:
        Cash Balance = Initial Seed + Deposits + RP Interest - Stock Invested - Withdrawals

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID
        currency: 통화 ('KRW' 또는 'USD')

    Returns:
        현금 잔고 (float)
    """
    response = supabase.rpc('calculate_cash_balance', {
        'p_account_id': account_id,
        'p_currency': currency
    }).execute()

    # RPC 함수는 단일 값을 반환
    if response.data is not None:
        return float(response.data)

    return 0.0


# ========== Portfolio Snapshot Functions ==========

def get_portfolio_history(supabase: Client, account_id: str, currency: str, days: int = 90) -> pd.DataFrame:
    """
    계좌별 포트폴리오 이력 조회 (시계열 데이터)

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID
        currency: 통화 ('KRW' 또는 'USD')
        days: 조회할 일수 (기본 90일)

    Returns:
        포트폴리오 이력 DataFrame
    """
    response = supabase.rpc('get_portfolio_history', {
        'p_account_id': account_id,
        'p_currency': currency,
        'p_days': days
    }).execute()

    if response.data:
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['snapshot_date'] = pd.to_datetime(df['snapshot_date'])
        return df

    return pd.DataFrame()


def get_aggregate_portfolio_history(supabase: Client, days: int = 90) -> pd.DataFrame:
    """
    전체 계좌 통합 포트폴리오 이력 조회

    Args:
        supabase: Supabase 클라이언트
        days: 조회할 일수 (기본 90일)

    Returns:
        통합 포트폴리오 이력 DataFrame
    """
    response = supabase.rpc('get_aggregate_portfolio_history', {
        'p_days': days
    }).execute()

    if response.data:
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['snapshot_date'] = pd.to_datetime(df['snapshot_date'])
        return df

    return pd.DataFrame()


def get_market_indices(supabase: Client) -> pd.DataFrame:
    """
    시장 지수 히스토리 조회 (SPX, NDX, KOSPI)

    Returns:
        DataFrame with columns: snapshot_date, spx_close, ndx_close, kospi_close
    """
    response = supabase.table('market_indices').select('*').order('snapshot_date').execute()

    if response.data:
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['snapshot_date'] = pd.to_datetime(df['snapshot_date'])
        return df

    return pd.DataFrame()
