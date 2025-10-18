"""
Stock Portfolio Tracker - Multi-Account Streamlit Application (Read-Only)
주식 포트폴리오 관리 및 분석 웹 애플리케이션 (5개 계좌 지원, 읽기 전용)

데이터 입력: Supabase 콘솔에서 직접 입력 또는 CSV import
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
from supabase import Client

# 로컬 모듈 임포트
from database import (
    init_supabase,
    get_all_accounts,
    get_account_by_number,
    get_all_transactions,
    get_transactions_by_account,
    get_transactions_by_account_and_ticker,
    get_cached_prices_by_tickers,
    get_price_cache_status,
    get_portfolio_history,
    get_aggregate_portfolio_history,
    get_market_indices,
    get_cash_transactions,
    get_cash_transaction_summary
)
from calculations import (
    calculate_holdings,
    calculate_portfolio_metrics,
    calculate_aggregate_metrics,
    calculate_closed_positions,
    calculate_win_rate,
    add_current_prices_to_holdings,
    get_current_prices_from_cache
)
from currency_utils import (
    format_currency,
    get_currency_symbol,
    determine_currency_from_ticker,
    validate_ticker_format
)
from exchange_rate import (
    get_usd_krw_rate,
    get_exchange_rate_info
)

# Try to import historical exchange rate function (may not be available in older versions)
try:
    from exchange_rate import get_historical_usd_krw_rate
except ImportError:
    # Fallback: use current rate for historical lookups
    get_historical_usd_krw_rate = lambda date: get_usd_krw_rate()
from charts import (
    create_price_chart_with_transactions
)
from market_data import (
    get_market_today,
    get_fgi_badge_color,
    get_change_color
)

# 페이지 설정
st.set_page_config(
    page_title="Multi-Account 포트폴리오 트래커",
    page_icon="📊",
    layout="wide"
)


# Supabase 클라이언트 초기화
@st.cache_resource
def get_supabase_client() -> Client:
    """Supabase 클라이언트 초기화 (캐싱)"""
    return init_supabase()


# 현재 가격 조회 (데이터베이스 캐시 사용)
# TTL=0: 캐싱 비활성화 (DB 자체가 캐시 역할, Edge Function이 주기적으로 업데이트)
def get_current_prices(tickers: list, _supabase: Client) -> dict:
    """
    여러 티커의 현재 가격 조회 (데이터베이스 캐시 사용)

    Args:
        tickers: 티커 리스트
        _supabase: Supabase 클라이언트 (캐싱 제외)

    Returns:
        {ticker: {'price': float, 'currency': str, 'change': 0, 'change_pct': 0}}
    """
    # 튜플이나 비정상 타입 필터링
    clean_tickers = []
    for ticker in tickers:
        if isinstance(ticker, tuple):
            ticker = ticker[-1]  # MultiIndex 문제 해결
        if isinstance(ticker, str):
            clean_tickers.append(ticker)

    if not clean_tickers:
        return {}

    # 데이터베이스에서 캐시된 가격 조회
    cached_prices = get_cached_prices_by_tickers(_supabase, clean_tickers)

    # 반환 형식 변환
    prices = {}
    for ticker in clean_tickers:
        currency = determine_currency_from_ticker(ticker)

        if ticker in cached_prices:
            # 캐시에서 가격 찾음
            prices[ticker] = {
                'price': cached_prices[ticker],
                'currency': currency,
                'change': 0,  # Edge Function에서 계산 안함
                'change_pct': 0
            }
        else:
            # 캐시에 없는 경우 (새로 추가된 종목 등)
            st.warning(f"⚠️ {ticker} 가격 캐시가 없습니다. Edge Function이 다음 업데이트 시 추가합니다.")
            prices[ticker] = {
                'price': 0,
                'currency': currency,
                'change': 0,
                'change_pct': 0
            }

    return prices


# 히스토리컬 데이터 조회 (캐싱)
@st.cache_data(ttl=900)
def get_historical_data(ticker: str, period: str = '1y') -> pd.DataFrame:
    """히스토리컬 주가 데이터 조회"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        return hist
    except Exception as e:
        st.error(f"히스토리컬 데이터 조회 실패: {str(e)}")
        return pd.DataFrame()


def show_overview_page(supabase: Client):
    """Overview 페이지 - 전체 계좌 요약"""
    st.title("📊 전체 포트폴리오 Overview")

    # Market Today 섹션
    st.markdown("### 📈 Market Today")

    market_data = get_market_today()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        sp500 = market_data['sp500']
        if not sp500['error']:
            change_color = get_change_color(sp500['change_pct'])
            st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">S&P 500</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:28px; font-weight:600; margin-top:0; margin-bottom:0;">{sp500["price"]:,.2f}</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:16px; color:{change_color}; margin-top:0;">{sp500["change_pct"]:+.2f}%</p>', unsafe_allow_html=True)
        else:
            st.metric("S&P 500", "N/A", delta="0.00%")

    with col2:
        nasdaq = market_data['nasdaq']
        if not nasdaq['error']:
            change_color = get_change_color(nasdaq['change_pct'])
            st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">NASDAQ 100</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:28px; font-weight:600; margin-top:0; margin-bottom:0;">{nasdaq["price"]:,.2f}</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:16px; color:{change_color}; margin-top:0;">{nasdaq["change_pct"]:+.2f}%</p>', unsafe_allow_html=True)
        else:
            st.metric("NASDAQ 100", "N/A", delta="0.00%")

    with col3:
        kospi = market_data['kospi']
        if not kospi['error']:
            change_color = get_change_color(kospi['change_pct'])
            st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">KOSPI</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:28px; font-weight:600; margin-top:0; margin-bottom:0;">{kospi["price"]:,.2f}</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:16px; color:{change_color}; margin-top:0;">{kospi["change_pct"]:+.2f}%</p>', unsafe_allow_html=True)
        else:
            st.metric("KOSPI", "N/A", delta="0.00%")

    with col4:
        usdkrw = market_data['usdkrw']
        if not usdkrw['error']:
            change_color = get_change_color(usdkrw['change_pct'])
            st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">USD/KRW</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:28px; font-weight:600; margin-top:0; margin-bottom:0;">{usdkrw["price"]:,.2f}</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:16px; color:{change_color}; margin-top:0;">{usdkrw["change_pct"]:+.2f}%</p>', unsafe_allow_html=True)
        else:
            st.metric("USD/KRW", "N/A", delta="0.00%")

    with col5:
        fgi = market_data['fgi']
        if not fgi['error']:
            badge_color = get_fgi_badge_color(fgi['classification'])
            st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">Fear & Greed</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:28px; font-weight:600; margin-top:0; margin-bottom:4px;">{fgi["value"]}</p>', unsafe_allow_html=True)
            st.markdown(f'<span style="background-color:{badge_color}; color:white; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:600;">{fgi["classification"]}</span>', unsafe_allow_html=True)
        else:
            st.metric("Fear & Greed", "N/A")

    st.caption(f"마지막 업데이트: {market_data['last_updated']}")
    st.markdown("---")

    # 환율 조회
    exchange_rate_info = get_exchange_rate_info()
    exchange_rate = exchange_rate_info['rate']

    # 모든 계좌 조회
    accounts_df = get_all_accounts(supabase)

    if accounts_df.empty:
        st.warning("계좌 정보가 없습니다. 데이터베이스를 확인해주세요.")
        return

    # 전체 거래 내역 조회
    all_transactions = get_all_transactions(supabase)

    # 각 계좌별 메트릭 계산
    accounts_metrics = []

    for _, account in accounts_df.iterrows():
        account_id = account['id']
        account_txns = all_transactions[all_transactions['account_id'] == account_id] if not all_transactions.empty else pd.DataFrame()

        # 보유 주식 계산
        holdings = calculate_holdings(account_txns, account_id)

        # 현재가 조회 (데이터베이스 캐시)
        if not holdings.empty:
            tickers = holdings.index.tolist()
            current_prices = get_current_prices(tickers, supabase)
        else:
            current_prices = {}

        # 포트폴리오 지표 계산 (잔여 현금 포함 - RP 이자 및 입출금 반영)
        metrics = calculate_portfolio_metrics(
            supabase,
            account['id'],
            holdings,
            current_prices,
            float(account['initial_seed_money_krw']),
            float(account['initial_seed_money_usd'])
        )

        accounts_metrics.append({
            'account_number': account['account_number'],
            'account_name': account['account_name'],
            'account_id': account_id,
            'strategy': account.get('strategy_description', ''),
            'allowed_currencies': account.get('allowed_currencies', []),
            'metrics': metrics,
            'seed_krw': float(account['initial_seed_money_krw']),
            'seed_usd': float(account['initial_seed_money_usd']),
            'holdings_count': len(holdings) if not holdings.empty else 0
        })

    # 전체 합산 지표 계산
    aggregate = calculate_aggregate_metrics(accounts_metrics, exchange_rate)

    # 전체 합산 지표 표시
    st.markdown("### 💰 전체 자산 요약")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">총 자산 (KRW)</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:36px; font-weight:600; margin-top:0;">{format_currency(aggregate["total_value_krw"], "KRW")}</p>', unsafe_allow_html=True)

    with col2:
        st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">총 자산 (USD)</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:36px; font-weight:600; margin-top:0;">{format_currency(aggregate["total_value_usd"], "USD")}</p>', unsafe_allow_html=True)

    with col3:
        # 손익 색상 결정 (KRW)
        pl_color_krw = "green" if aggregate['total_pl_krw'] > 0 else ("red" if aggregate['total_pl_krw'] < 0 else "gray")
        st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">총 손익 (KRW)</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:36px; font-weight:600; color:{pl_color_krw}; margin-top:0;">{format_currency(aggregate["total_pl_krw"], "KRW")}</p>', unsafe_allow_html=True)

    with col4:
        # 손익 색상 결정 (USD)
        pl_color_usd = "green" if aggregate['total_pl_usd'] > 0 else ("red" if aggregate['total_pl_usd'] < 0 else "gray")
        st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">총 손익 (USD)</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:36px; font-weight:600; color:{pl_color_usd}; margin-top:0;">{format_currency(aggregate["total_pl_usd"], "USD")}</p>', unsafe_allow_html=True)

    with col5:
        # 수익률 색상 결정
        return_color = "green" if aggregate['total_return_pct'] > 0 else ("red" if aggregate['total_return_pct'] < 0 else "gray")
        st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">총 수익률</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:36px; font-weight:600; color:{return_color}; margin-top:0;">{aggregate["total_return_pct"]:.2f}%</p>', unsafe_allow_html=True)

    st.markdown("---")

    # 계좌별 요약 카드
    st.markdown("### 📋 계좌별 성과 Summary")

    for acc in accounts_metrics:
        krw_val = acc['metrics']['krw']['total_value']
        usd_val = acc['metrics']['usd']['total_value']
        allowed_currencies = acc['allowed_currencies']

        # 환율 적용한 총액 (KRW 기준과 USD 기준 모두 계산)
        total_in_krw = krw_val + (usd_val * exchange_rate)
        total_in_usd = usd_val + (krw_val / exchange_rate if exchange_rate > 0 else 0)

        total_invested_krw = acc['seed_krw'] + (acc['seed_usd'] * exchange_rate)
        total_invested_usd = acc['seed_usd'] + (acc['seed_krw'] / exchange_rate if exchange_rate > 0 else 0)

        return_pct = ((total_in_krw - total_invested_krw) / total_invested_krw * 100) if total_invested_krw > 0 else 0

        # USD 단일 통화 계좌인지 확인
        is_usd_only = 'USD' in allowed_currencies and 'KRW' not in allowed_currencies

        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])

            with col1:
                st.markdown(f"**{acc['account_name']}**")
                st.caption(acc['strategy'])

            with col2:
                if is_usd_only:
                    # USD 계좌: USD를 크게 표시, KRW는 참고로 표시
                    st.metric("평가금액 (USD)", format_currency(total_in_usd, 'USD'))
                    st.caption(f"₩{total_in_krw:,.0f}")
                else:
                    # KRW 계좌: KRW만 표시 (기존 방식 유지)
                    st.metric("평가금액 (KRW)", format_currency(total_in_krw, 'KRW'))

            with col3:
                if is_usd_only:
                    # USD 계좌: USD를 크게 표시, KRW는 참고로 표시
                    st.metric("투자금 (USD)", format_currency(total_invested_usd, 'USD'))
                    st.caption(f"₩{total_invested_krw:,.0f}")
                else:
                    # KRW 계좌: KRW만 표시 (기존 방식 유지)
                    st.metric("투자금 (KRW)", format_currency(total_invested_krw, 'KRW'))

            with col4:
                # 수익률 색상 결정
                return_color = "green" if return_pct > 0 else ("red" if return_pct < 0 else "gray")
                st.markdown('<p style="font-size:14px; color:gray; margin-bottom:0;">수익률</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="font-size:36px; font-weight:600; color:{return_color}; margin-top:0;">{return_pct:.2f}%</p>', unsafe_allow_html=True)

            with col5:
                st.metric("종목", acc['holdings_count'])

            st.markdown("---")

    # 가격 캐시 상태 표시 (expander로 숨김)
    with st.expander("📊 가격 캐시 상태 (Price Cache Status)"):
        cache_status = get_price_cache_status(supabase)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("전체 활성 종목", cache_status['total_active'])

        with col2:
            st.metric("성공", cache_status['successful'], delta=None)

        with col3:
            st.metric("실패", cache_status['failed'], delta=None)

        with col4:
            st.metric("오래된 데이터", cache_status['stale_count'], delta=None)

        if cache_status['last_update']:
            from datetime import datetime, timedelta
            # UTC 시간을 파싱
            last_update_utc = datetime.fromisoformat(cache_status['last_update'].replace('Z', '+00:00'))
            # KST로 변환 (UTC+9)
            last_update_kst = last_update_utc + timedelta(hours=9)
            st.caption(f"최근 업데이트: {last_update_kst.strftime('%Y-%m-%d %H:%M:%S KST')}")
        else:
            st.caption("최근 업데이트: 데이터 없음")

        if cache_status['failed'] > 0:
            st.warning(f"⚠️ {cache_status['failed']}개 종목의 가격 조회 실패. Edge Function 로그를 확인하세요.")

        if cache_status['stale_count'] > 0:
            st.warning(f"⚠️ {cache_status['stale_count']}개 종목이 2일 이상 업데이트되지 않았습니다.")

    st.markdown("---")
    st.info("👆 계좌를 선택하려면 사이드바에서 페이지를 선택하세요.")


def show_account_page(supabase: Client, account_number: int):
    """개별 계좌 상세 페이지"""
    account = get_account_by_number(supabase, account_number)

    if not account:
        st.error(f"계좌 {account_number}을(를) 찾을 수 없습니다.")
        return

    account_id = account['id']
    allowed_currencies = account.get('allowed_currencies', [])

    st.title(f"📊 계좌 {account_number} - {account['account_name']}")
    st.caption(f"전략: {account.get('strategy_description', '설명 없음')}")

    # 계좌의 허용 통화 확인
    has_krw = 'KRW' in allowed_currencies
    has_usd = 'USD' in allowed_currencies

    # 거래 내역 조회
    account_txns = get_transactions_by_account(supabase, account_id)

    # 보유 주식 계산
    holdings_df = calculate_holdings(account_txns, account_id)

    # 현재 가격 조회 (데이터베이스 캐시)
    if not holdings_df.empty:
        tickers = holdings_df.index.tolist()
        current_prices = get_current_prices(tickers, supabase)
    else:
        current_prices = {}

    # 포트폴리오 지표 계산 (RP 이자 및 입출금 반영)
    metrics = calculate_portfolio_metrics(
        supabase,
        account_id,
        holdings_df,
        current_prices,
        float(account['initial_seed_money_krw']),
        float(account['initial_seed_money_usd'])
    )

    # 환율 조회
    exchange_rate = get_usd_krw_rate()

    # 포트폴리오 요약
    st.markdown("### 💼 포트폴리오 요약")

    # 계좌의 허용 통화 확인
    has_krw = 'KRW' in allowed_currencies
    has_usd = 'USD' in allowed_currencies

    # KRW 섹션 (KRW가 허용된 경우만 표시)
    if has_krw:
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.markdown('<p style="font-size:14px; color:gray;">초기 투자금</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px; font-weight:bold;">{format_currency(account["initial_seed_money_krw"], "KRW")}</p>', unsafe_allow_html=True)

        with col2:
            st.markdown('<p style="font-size:14px; color:gray;">총 평가액</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px; font-weight:bold;">{format_currency(metrics["krw"]["total_value"], "KRW")}</p>', unsafe_allow_html=True)

        with col3:
            st.markdown('<p style="font-size:14px; color:gray;">주식 평가액</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px;">{format_currency(metrics["krw"]["stock_value"], "KRW")}</p>', unsafe_allow_html=True)

        with col4:
            st.markdown('<p style="font-size:14px; color:gray;">잔여 현금</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px;">{format_currency(metrics["krw"]["cash"], "KRW")}</p>', unsafe_allow_html=True)

        with col5:
            pl_color = "green" if metrics['krw']['pl'] >= 0 else "red"
            st.markdown('<p style="font-size:14px; color:gray;">평가 손익</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px; font-weight:bold; color:{pl_color};">{format_currency(metrics["krw"]["pl"], "KRW")}</p>', unsafe_allow_html=True)

        with col6:
            pl_color = "green" if metrics['krw']['pl'] >= 0 else "red"
            st.markdown('<p style="font-size:14px; color:gray;">수익률</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px; font-weight:bold; color:{pl_color};">{metrics["krw"]["return_pct"]:.2f}%</p>', unsafe_allow_html=True)

    # USD 섹션 (USD가 허용된 경우만 표시)
    if has_usd:
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.markdown('<p style="font-size:14px; color:gray;">초기 투자금</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px; font-weight:bold;">{format_currency(account["initial_seed_money_usd"], "USD")}</p>', unsafe_allow_html=True)

        with col2:
            st.markdown('<p style="font-size:14px; color:gray;">총 평가액</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px; font-weight:bold;">{format_currency(metrics["usd"]["total_value"], "USD")}</p>', unsafe_allow_html=True)

        with col3:
            st.markdown('<p style="font-size:14px; color:gray;">주식 평가액</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px;">{format_currency(metrics["usd"]["stock_value"], "USD")}</p>', unsafe_allow_html=True)

        with col4:
            st.markdown('<p style="font-size:14px; color:gray;">잔여 현금</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px;">{format_currency(metrics["usd"]["cash"], "USD")}</p>', unsafe_allow_html=True)

        with col5:
            pl_color = "green" if metrics['usd']['pl'] >= 0 else "red"
            st.markdown('<p style="font-size:14px; color:gray;">평가 손익</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px; font-weight:bold; color:{pl_color};">{format_currency(metrics["usd"]["pl"], "USD")}</p>', unsafe_allow_html=True)

        with col6:
            pl_color = "green" if metrics['usd']['pl'] >= 0 else "red"
            st.markdown('<p style="font-size:14px; color:gray;">수익률</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:24px; font-weight:bold; color:{pl_color};">{metrics["usd"]["return_pct"]:.2f}%</p>', unsafe_allow_html=True)

    st.markdown("---")

    # 포트폴리오 구성 파이 차트
    st.subheader("📊 포트폴리오 구성")

    # 현재 보유 주식으로 파이차트 데이터 생성
    pie_items = []
    pie_values = []

    if not holdings_df.empty:
        # 개별 종목별로 평가액 추가
        for ticker, row in holdings_df.iterrows():
            if ticker in current_prices:
                stock_value = current_prices[ticker]['price'] * row['quantity']
                pie_items.append(f"{row['stock_name']} ({ticker})")
                pie_values.append(stock_value)

    # 현금 잔고 추가 (KRW 또는 USD)
    if has_krw and metrics['krw']['cash'] > 0:
        pie_items.append('현금')
        pie_values.append(metrics['krw']['cash'])
        currency = 'KRW'
    elif has_usd and metrics['usd']['cash'] > 0:
        pie_items.append('현금')
        pie_values.append(metrics['usd']['cash'])
        currency = 'USD'
    else:
        # 현금이 없으면 기본 통화 설정
        currency = 'KRW' if has_krw else 'USD'

    # 데이터가 있을 때만 차트 표시
    if pie_items and pie_values:
        pie_data = pd.DataFrame({
            '항목': pie_items,
            '금액': pie_values
        })

        # 색상을 명시적으로 각 항목에 매핑
        default_colors = px.colors.qualitative.Plotly

        # 각 항목에 고유한 색상 할당 (딕셔너리 사용)
        color_map = {item: default_colors[i % len(default_colors)]
                     for i, item in enumerate(pie_items)}

        # 파이차트 생성
        fig = px.pie(
            pie_data,
            values='금액',
            names='항목',
            hole=0.4,
            color='항목',
            color_discrete_map=color_map
        )

        # 범례에 사용할 색상 리스트 (pie_items 순서와 동일)
        colors = [color_map[item] for item in pie_items]

        # 통화 기호 설정
        currency_symbol = '₩' if currency == 'KRW' else '$'
        currency_format = ',.0f' if currency == 'KRW' else ',.2f'

        fig.update_traces(
            textposition='inside',
            textinfo='percent',
            textfont_size=14,
            marker=dict(line=dict(color='white', width=2)),
            hovertemplate='<b>%{label}</b><br>' +
                         f'금액: {currency_symbol}%{{value:{currency_format}}}<br>' +
                         '비중: %{percent}<br>' +
                         '<extra></extra>'
        )

        # 범례 숨기기 (HTML로 직접 만들 것임)
        fig.update_layout(
            showlegend=False,
            height=450,
            margin=dict(l=20, r=20, t=40, b=40)
        )

        # 차트와 범례를 나란히 배치 (좌측 정렬)
        col_chart, col_legend = st.columns([1.5, 1.5])

        with col_chart:
            st.plotly_chart(fig, use_container_width=True)

        with col_legend:
            st.markdown("##### 범례")

            # 멀티컬럼 범례 생성 (항목이 많으면 2열)
            num_items = len(pie_items)

            if num_items > 8:
                # 2열 레이아웃
                legend_html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px;">'
                for i, (item, color) in enumerate(zip(pie_items, colors)):
                    legend_html += f'<div style="display: flex; align-items: center; gap: 5px;"><div style="width: 12px; height: 12px; background-color: {color}; border-radius: 2px; flex-shrink: 0;"></div><span style="font-size: 10pt; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{item}">{item}</span></div>'
                legend_html += '</div>'
            else:
                # 1열 레이아웃
                legend_html = '<div>'
                for i, (item, color) in enumerate(zip(pie_items, colors)):
                    legend_html += f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;"><div style="width: 14px; height: 14px; background-color: {color}; border-radius: 2px; flex-shrink: 0;"></div><span style="font-size: 11pt;">{item}</span></div>'
                legend_html += '</div>'

            st.markdown(legend_html, unsafe_allow_html=True)
    else:
        st.info("포트폴리오 데이터가 없습니다.")

    st.markdown("---")

    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 현재 보유", "📜 거래 내역", "💰 현금 내역", "✅ 청산 포지션"])

    # 탭 1: 현재 보유 주식
    with tab1:
        st.subheader("현재 보유 주식")

        # 현재가 정보 확인
        if not holdings_df.empty:
            if not current_prices:
                st.warning("⚠️ 현재가 정보를 불러올 수 없습니다. 가격 캐시를 확인해주세요.")

            # 보유 주식에 현재가 정보 추가
            holdings_with_prices = add_current_prices_to_holdings(holdings_df, current_prices)
        else:
            holdings_with_prices = pd.DataFrame()

        if not holdings_with_prices.empty:
            # 수익률 기준 내림차순 정렬 (포맷팅 전에 먼저 정렬)
            if 'return_pct' in holdings_with_prices.columns:
                holdings_with_prices = holdings_with_prices.sort_values('return_pct', ascending=False)

            # 표시용 DataFrame 생성 (인덱스를 컬럼으로 변환)
            display_df = holdings_with_prices.reset_index()

            # level_0을 ticker로 이름 변경 (reset_index 후 인덱스 이름이 level_0으로 바뀜)
            if 'level_0' in display_df.columns:
                display_df.rename(columns={'level_0': 'ticker'}, inplace=True)

            # 컬럼 순서 및 이름 변경 (통화, 국가 제거, 티커를 주식명 다음으로)
            display_columns = {
                'stock_name': '주식명',
                'ticker': '티커',
                'quantity': '수량',
                'avg_price': '평균 단가',
                'current_price': '현재가',
                'market_value': '평가 금액',
                'unrealized_pl': '평가 손익',
                'return_pct': '수익률 (%)'
            }

            # 존재하는 컬럼만 선택
            available_cols = [col for col in display_columns.keys() if col in display_df.columns]
            display_df = display_df[available_cols].copy()

            # currency 컬럼 임시 보관 (포맷팅용)
            if 'currency' in holdings_with_prices.columns:
                currency_col = holdings_with_prices['currency'].values
            else:
                currency_col = None

            # 조건부 색상을 위해 원본 숫자 값 저장
            unrealized_pl_values = display_df['unrealized_pl'].copy() if 'unrealized_pl' in display_df.columns else None
            return_pct_values = display_df['return_pct'].copy() if 'return_pct' in display_df.columns else None

            # 모든 컬럼을 문자열로 변환 (set_properties의 text-align이 작동하도록)
            if currency_col is not None:
                for idx in range(len(display_df)):
                    currency = currency_col[idx]

                    # 티커는 이미 문자열

                    # 수량을 문자열로 변환 (정수 표시)
                    if 'quantity' in display_df.columns:
                        display_df.at[idx, 'quantity'] = f"{int(display_df.at[idx, 'quantity'])}"

                    # 가격 컬럼들을 통화 기호와 함께 문자열로 변환
                    if 'avg_price' in display_df.columns:
                        display_df.at[idx, 'avg_price'] = format_currency(display_df.at[idx, 'avg_price'], currency)
                    if 'current_price' in display_df.columns:
                        display_df.at[idx, 'current_price'] = format_currency(display_df.at[idx, 'current_price'], currency)
                    if 'market_value' in display_df.columns:
                        display_df.at[idx, 'market_value'] = format_currency(display_df.at[idx, 'market_value'], currency)
                    if 'unrealized_pl' in display_df.columns:
                        display_df.at[idx, 'unrealized_pl'] = format_currency(display_df.at[idx, 'unrealized_pl'], currency)
                    if 'return_pct' in display_df.columns:
                        display_df.at[idx, 'return_pct'] = f"{display_df.at[idx, 'return_pct']:.2f}%"

            # 컬럼명 변경
            display_df.columns = [display_columns.get(col, col) for col in display_df.columns]

            # 조건부 색상 적용 함수
            def apply_color(row):
                styles = [''] * len(row)

                # 평가 손익 색상 (0이면 기본색, 양수면 초록, 음수면 빨강)
                if '평가 손익' in display_df.columns:
                    pl_idx = display_df.columns.get_loc('평가 손익')
                    row_idx = row.name
                    if unrealized_pl_values is not None and row_idx < len(unrealized_pl_values):
                        original_val = unrealized_pl_values.iloc[row_idx]
                        if pd.notna(original_val) and original_val != 0:
                            color = 'red' if original_val < 0 else 'green'
                            styles[pl_idx] = f'color: {color}; font-weight: bold'

                # 수익률 색상 (0이면 기본색, 양수면 초록, 음수면 빨강)
                if '수익률 (%)' in display_df.columns:
                    return_idx = display_df.columns.get_loc('수익률 (%)')
                    row_idx = row.name
                    if return_pct_values is not None and row_idx < len(return_pct_values):
                        original_val = return_pct_values.iloc[row_idx]
                        if pd.notna(original_val) and original_val != 0:
                            color = 'red' if original_val < 0 else 'green'
                            styles[return_idx] = f'color: {color}; font-weight: bold'

                return styles

            # 색상만 적용하는 함수 (정렬은 set_properties로 처리)
            def apply_color_only(row):
                styles = [''] * len(row)

                # 평가 손익 색상
                if '평가 손익' in display_df.columns:
                    pl_idx = display_df.columns.get_loc('평가 손익')
                    row_idx = row.name
                    if unrealized_pl_values is not None and row_idx < len(unrealized_pl_values):
                        original_val = unrealized_pl_values.iloc[row_idx]
                        if pd.notna(original_val) and original_val != 0:
                            color = 'red' if original_val < 0 else 'green'
                            styles[pl_idx] = f'color: {color}; font-weight: bold'

                # 수익률 색상
                if '수익률 (%)' in display_df.columns:
                    return_idx = display_df.columns.get_loc('수익률 (%)')
                    row_idx = row.name
                    if return_pct_values is not None and row_idx < len(return_pct_values):
                        original_val = return_pct_values.iloc[row_idx]
                        if pd.notna(original_val) and original_val != 0:
                            color = 'red' if original_val < 0 else 'green'
                            styles[return_idx] = f'color: {color}; font-weight: bold'

                return styles

            # 색상 스타일 적용
            styled_df = display_df.style.apply(apply_color_only, axis=1)

            # 전체 테이블 폰트 크기 설정
            styled_df = styled_df.set_properties(**{'font-size': '18pt'})

            # 주식명 컬럼 너비 설정
            if '주식명' in display_df.columns:
                styled_df = styled_df.set_properties(subset=['주식명'], **{
                    'width': '200px',
                    'min-width': '200px'
                })

            # HTML/CSS로 정렬 적용 (Streamlit의 text-align은 작동하지 않음)
            st.markdown("""
                <style>
                /* 테이블 전체 스타일 */
                .stDataFrame table {
                    font-size: 18pt !important;
                }

                /* 주식명: 좌측정렬 */
                .stDataFrame td:nth-child(1),
                .stDataFrame th:nth-child(1) {
                    text-align: left !important;
                }

                /* 티커: 중앙정렬 */
                .stDataFrame td:nth-child(2),
                .stDataFrame th:nth-child(2) {
                    text-align: center !important;
                }

                /* 수량: 중앙정렬 */
                .stDataFrame td:nth-child(3),
                .stDataFrame th:nth-child(3) {
                    text-align: center !important;
                }

                /* 평균 단가: 우측정렬 */
                .stDataFrame td:nth-child(4),
                .stDataFrame th:nth-child(4) {
                    text-align: right !important;
                }

                /* 현재가: 우측정렬 */
                .stDataFrame td:nth-child(5),
                .stDataFrame th:nth-child(5) {
                    text-align: right !important;
                }

                /* 평가 금액: 우측정렬 */
                .stDataFrame td:nth-child(6),
                .stDataFrame th:nth-child(6) {
                    text-align: right !important;
                }

                /* 평가 손익: 우측정렬 */
                .stDataFrame td:nth-child(7),
                .stDataFrame th:nth-child(7) {
                    text-align: right !important;
                }

                /* 수익률 (%): 중앙정렬 */
                .stDataFrame td:nth-child(8),
                .stDataFrame th:nth-child(8) {
                    text-align: center !important;
                }
                </style>
            """, unsafe_allow_html=True)

            # 높이 제한 없이 전체 표시 (height 파라미터 생략)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("현재 보유 중인 주식이 없습니다.")

    # 탭 2: 거래 내역
    with tab2:
        st.subheader("거래 내역")

        if not account_txns.empty:
            display_txns = account_txns.copy()

            # created_at 기준 내림차순 정렬 (최신 거래가 맨 위)
            if 'created_at' in display_txns.columns:
                display_txns = display_txns.sort_values('created_at', ascending=False)
        else:
            st.info("거래 내역이 없습니다. Supabase 콘솔에서 데이터를 추가해주세요.")
            display_txns = pd.DataFrame()

        if not display_txns.empty:
            # 통화 정보를 currency 컬럼에서 가져와서 임시 저장 (포맷팅용)
            currency_col = display_txns['currency'].copy() if 'currency' in display_txns.columns else None

            # 컬럼 매핑 (국가, 통화 제외)
            column_mapping = {
                'transaction_date': '거래 날짜',
                'transaction_type': '유형',
                'stock_name': '주식명',
                'ticker': '티커',
                'trade_price': '거래 가격',
                'quantity': '수량',
                'fee': '수수료'
            }

            display_cols = [col for col in column_mapping.keys() if col in display_txns.columns]
            display_txns = display_txns[display_cols].copy()
            display_txns.columns = [column_mapping[col] for col in display_cols]

            # 유형 한글화
            if '유형' in display_txns.columns:
                display_txns['유형'] = display_txns['유형'].map({'BUY': '매수', 'SELL': '매도'})

            # 가격 및 수수료 포맷팅 (통화 정보 사용)
            if currency_col is not None:
                for idx in range(len(display_txns)):
                    currency = currency_col.iloc[idx]

                    # 거래 가격 포맷팅
                    if '거래 가격' in display_txns.columns:
                        display_txns.iloc[idx, display_txns.columns.get_loc('거래 가격')] = format_currency(
                            display_txns.iloc[idx, display_txns.columns.get_loc('거래 가격')],
                            currency
                        )

                    # 수수료 포맷팅 (0이면 '-' 표시)
                    if '수수료' in display_txns.columns:
                        fee_value = display_txns.iloc[idx, display_txns.columns.get_loc('수수료')]
                        if pd.isna(fee_value) or fee_value == 0:
                            display_txns.iloc[idx, display_txns.columns.get_loc('수수료')] = '-'
                        else:
                            display_txns.iloc[idx, display_txns.columns.get_loc('수수료')] = format_currency(
                                fee_value,
                                currency
                            )

            # 주식명 컬럼 너비 설정
            column_config = {
                '주식명': st.column_config.TextColumn(
                    '주식명',
                    width='medium'
                )
            }

            # 거래 내역은 스크롤 가능하게 높이 제한 (400px)
            st.dataframe(
                display_txns,
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config=column_config
            )

    # 탭 3: 현금 내역
    with tab3:
        st.subheader("💰 현금 거래 내역")

        # 현금 거래 요약 정보 조회
        cash_summary_krw = get_cash_transaction_summary(supabase, account_id, 'KRW') if 'KRW' in allowed_currencies else None
        cash_summary_usd = get_cash_transaction_summary(supabase, account_id, 'USD') if 'USD' in allowed_currencies else None

        # KRW 현금 내역
        if cash_summary_krw:
            st.markdown("#### 원화 (KRW)")

            # 6-column 레이아웃
            col1, col2, col3, col4, col5, col6 = st.columns(6)

            with col1:
                st.metric("총 입금액", format_currency(cash_summary_krw['total_deposits'], 'KRW'))

            with col2:
                st.metric("총 출금액", format_currency(cash_summary_krw['total_withdrawals'], 'KRW'))

            with col3:
                st.metric("RP 이자", format_currency(cash_summary_krw['total_rp_interest'], 'KRW'))

            with col4:
                st.metric("조정(+)", format_currency(cash_summary_krw['total_adjustments_increase'], 'KRW'))

            with col5:
                st.metric("조정(-)", format_currency(cash_summary_krw['total_adjustments_decrease'], 'KRW'))

            with col6:
                st.metric("현재 잔고", format_currency(cash_summary_krw['current_cash_balance'], 'KRW'))

        # USD 현금 내역
        if cash_summary_usd:
            st.markdown("#### 달러 (USD)")

            # 6-column 레이아웃
            col1, col2, col3, col4, col5, col6 = st.columns(6)

            with col1:
                st.metric("총 입금액", format_currency(cash_summary_usd['total_deposits'], 'USD'))

            with col2:
                st.metric("총 출금액", format_currency(cash_summary_usd['total_withdrawals'], 'USD'))

            with col3:
                st.metric("RP 이자", format_currency(cash_summary_usd['total_rp_interest'], 'USD'))

            with col4:
                st.metric("조정(+)", format_currency(cash_summary_usd['total_adjustments_increase'], 'USD'))

            with col5:
                st.metric("조정(-)", format_currency(cash_summary_usd['total_adjustments_decrease'], 'USD'))

            with col6:
                st.metric("현재 잔고", format_currency(cash_summary_usd['current_cash_balance'], 'USD'))

        st.markdown("---")

        # 현금 거래 테이블
        cash_txns = get_cash_transactions(supabase, account_id)

        if not cash_txns.empty:
            # 날짜순 내림차순 정렬 (최신 거래가 위로)
            cash_txns = cash_txns.sort_values('transaction_date', ascending=False)

            # 누적 잔고 계산 (오래된 것부터 계산하므로 오름차순 정렬)
            cash_txns_sorted = cash_txns.sort_values('transaction_date', ascending=True).copy()

            # 통화별로 누적 잔고 계산
            cash_txns_sorted['cumulative_balance'] = 0.0

            for currency in ['KRW', 'USD']:
                currency_mask = cash_txns_sorted['currency'] == currency
                currency_txns = cash_txns_sorted[currency_mask].copy()

                if not currency_txns.empty:
                    # 초기 시드 머니
                    if currency == 'KRW':
                        initial_seed = account['initial_seed_money_krw']
                    else:
                        initial_seed = account['initial_seed_money_usd']

                    running_balance = initial_seed

                    for idx in currency_txns.index:
                        txn_type = cash_txns_sorted.loc[idx, 'transaction_type']
                        amount = cash_txns_sorted.loc[idx, 'amount']

                        if txn_type in ('DEPOSIT', 'RP_INTEREST', 'ADJUSTMENT_INCREASE'):
                            running_balance += amount
                        elif txn_type in ('WITHDRAWAL', 'ADJUSTMENT_DECREASE'):
                            running_balance -= amount

                        cash_txns_sorted.loc[idx, 'cumulative_balance'] = running_balance

            # 다시 내림차순으로 정렬 (최신 거래가 위로)
            display_cash = cash_txns_sorted.sort_values('transaction_date', ascending=False).copy()

            # 표시용 DataFrame 생성
            display_cash['유형'] = display_cash['transaction_type'].map({
                'DEPOSIT': '입금',
                'WITHDRAWAL': '출금',
                'RP_INTEREST': 'RP 이자',
                'ADJUSTMENT_INCREASE': '조정(+)',
                'ADJUSTMENT_DECREASE': '조정(-)'
            })

            # 금액 포맷팅
            display_cash['금액_formatted'] = display_cash.apply(
                lambda row: format_currency(row['amount'], row['currency']),
                axis=1
            )

            # 누적 잔고 포맷팅
            display_cash['누적잔고_formatted'] = display_cash.apply(
                lambda row: format_currency(row['cumulative_balance'], row['currency']),
                axis=1
            )

            # 표시할 컬럼 선택
            table_df = display_cash[['transaction_date', '유형', 'currency', '금액_formatted', '누적잔고_formatted', 'description']].copy()
            table_df.columns = ['날짜', '유형', '통화', '금액', '누적 잔고', '설명']

            # 설명이 없는 경우 '-' 표시
            table_df['설명'] = table_df['설명'].fillna('-')

            # 유형별 색상 스타일 적용 함수
            def apply_cash_txn_color(row):
                styles = [''] * len(row)

                # 유형 컬럼 색상
                if '유형' in table_df.columns:
                    type_idx = table_df.columns.get_loc('유형')
                    txn_type = row['유형']

                    if txn_type == '입금':
                        styles[type_idx] = 'color: blue; font-weight: bold'
                    elif txn_type == '출금':
                        styles[type_idx] = 'color: red; font-weight: bold'
                    elif txn_type == 'RP 이자':
                        styles[type_idx] = 'color: green; font-weight: bold'
                    elif txn_type == '조정(+)':
                        styles[type_idx] = 'color: orange; font-weight: bold'
                    elif txn_type == '조정(-)':
                        styles[type_idx] = 'color: darkorange; font-weight: bold'

                return styles

            # 스타일 적용
            styled_cash = table_df.style.apply(apply_cash_txn_color, axis=1)

            st.dataframe(styled_cash, use_container_width=True, hide_index=True, height=400)
        else:
            st.info("현금 거래 내역이 없습니다.")

    # 탭 4: 청산 포지션
    with tab4:
        st.subheader("청산된 포지션")

        closed_positions = calculate_closed_positions(account_txns, account_id)

        if closed_positions.empty:
            st.info("청산된 포지션이 없습니다.")
        else:
            # 승률 통계 계산
            win_stats = calculate_win_rate(closed_positions)

            # 승률 통계 표시 (4-column 레이아웃)
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("전체 청산", f"{win_stats['total_trades']}건")

            with col2:
                st.metric(
                    "Win",
                    f"{win_stats['wins']}건",
                    delta=f"평균 {win_stats['avg_win']:.2f}%",
                    delta_color="normal"
                )

            with col3:
                st.metric(
                    "Loss",
                    f"{win_stats['losses']}건",
                    delta=f"평균 {win_stats['avg_loss']:.2f}%",
                    delta_color="inverse"
                )

            with col4:
                # 승률 HTML 마크다운 (50% 이상 초록, 미만 빨강)
                wr_color = "green" if win_stats['win_rate'] >= 50 else "red"
                st.markdown(
                    f'<p style="font-size:14px; color:gray; margin-bottom:0;">승률 (WR)</p>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<p style="font-size:36px; font-weight:600; color:{wr_color}; margin-top:0;">{win_stats["win_rate"]:.2f}%</p>',
                    unsafe_allow_html=True
                )

            st.markdown("---")

            # 청산 포지션 테이블
            display_closed = closed_positions.copy()

            # 통화 정보를 currency 컬럼에서 가져와서 임시 저장 (포맷팅용)
            currency_col = display_closed['currency'].copy() if 'currency' in display_closed.columns else None
            # result 컬럼도 임시 저장 (색상 코딩용)
            result_col = display_closed['result'].copy() if 'result' in display_closed.columns else None

            # 컬럼 매핑
            column_mapping = {
                'ticker': '티커',
                'stock_name': '주식명',
                'result': '결과',
                'total_shares_traded': '거래 수량',
                'realized_pl': '실현 손익',
                'realized_return_pct': '수익률 (%)',
                'first_trade_date': '첫 거래',
                'last_trade_date': '마지막 거래',
                'holding_period_days': '보유 기간 (일)'
            }

            display_closed = display_closed[[col for col in column_mapping.keys() if col in display_closed.columns]].copy()
            display_closed.columns = [column_mapping[col] for col in display_closed.columns]

            # 손익 포맷팅 (통화 정보 사용)
            if currency_col is not None and '실현 손익' in display_closed.columns:
                for idx in range(len(display_closed)):
                    currency = currency_col.iloc[idx]
                    display_closed.iloc[idx, display_closed.columns.get_loc('실현 손익')] = format_currency(
                        display_closed.iloc[idx, display_closed.columns.get_loc('실현 손익')],
                        currency
                    )

            # 수익률 포맷팅
            if '수익률 (%)' in display_closed.columns:
                for idx in range(len(display_closed)):
                    display_closed.iloc[idx, display_closed.columns.get_loc('수익률 (%)')] = f"{display_closed.iloc[idx, display_closed.columns.get_loc('수익률 (%)')]:.2f}"

            # 청산 포지션 테이블 표시
            st.dataframe(display_closed, use_container_width=True, hide_index=True)


def show_statistics_page(supabase: Client):
    """통계 페이지 - 정규화된 성과 비교 차트 (2025-10-13 기준 = 1.0)"""
    st.title("📈 통계")

    # 데이터 로드
    market_indices = get_market_indices(supabase)
    aggregate_history = get_aggregate_portfolio_history(supabase, days=365)

    # 계좌 정보 조회
    accounts_df = get_all_accounts(supabase)

    # 모든 계좌의 스냅샷 데이터 조회 (직접 쿼리)
    portfolio_snapshots_response = supabase.table('portfolio_snapshots')\
        .select('*')\
        .order('snapshot_date', desc=False)\
        .execute()

    portfolio_snapshots = pd.DataFrame(portfolio_snapshots_response.data) if portfolio_snapshots_response.data else pd.DataFrame()

    if not portfolio_snapshots.empty:
        portfolio_snapshots['snapshot_date'] = pd.to_datetime(portfolio_snapshots['snapshot_date'])

    if market_indices.empty and aggregate_history.empty:
        st.info("아직 통계 데이터가 없습니다. 스냅샷이 생성되면 데이터가 표시됩니다.")
        return

    # 기준일 설정 (2025-10-13)
    baseline_date = pd.to_datetime('2025-10-13')

    # 정규화된 데이터를 저장할 리스트
    normalized_data = []

    # 1. 시장 지수 정규화
    if not market_indices.empty:
        # 기준일 데이터
        baseline_indices = market_indices[market_indices['snapshot_date'] == baseline_date]

        if not baseline_indices.empty:
            baseline_spx = baseline_indices['spx_close'].iloc[0] if 'spx_close' in baseline_indices.columns else None
            baseline_ndx = baseline_indices['ndx_close'].iloc[0] if 'ndx_close' in baseline_indices.columns else None
            baseline_kospi = baseline_indices['kospi_close'].iloc[0] if 'kospi_close' in baseline_indices.columns else None

            # 각 지수 정규화
            for _, row in market_indices.iterrows():
                date = row['snapshot_date']

                # SPX 정규화
                if baseline_spx and pd.notna(baseline_spx) and baseline_spx > 0:
                    if 'spx_close' in row and pd.notna(row['spx_close']):
                        normalized_data.append({
                            'snapshot_date': date,
                            'Category': 'S&P 500',
                            'Normalized Value': row['spx_close'] / baseline_spx,
                            'Actual Value': row['spx_close']
                        })

                # NDX 정규화
                if baseline_ndx and pd.notna(baseline_ndx) and baseline_ndx > 0:
                    if 'ndx_close' in row and pd.notna(row['ndx_close']):
                        normalized_data.append({
                            'snapshot_date': date,
                            'Category': 'NASDAQ 100',
                            'Normalized Value': row['ndx_close'] / baseline_ndx,
                            'Actual Value': row['ndx_close']
                        })

                # KOSPI 정규화
                if baseline_kospi and pd.notna(baseline_kospi) and baseline_kospi > 0:
                    if 'kospi_close' in row and pd.notna(row['kospi_close']):
                        normalized_data.append({
                            'snapshot_date': date,
                            'Category': 'KOSPI',
                            'Normalized Value': row['kospi_close'] / baseline_kospi,
                            'Actual Value': row['kospi_close']
                        })
        else:
            st.warning("⚠️ 2025-10-13의 시장 지수 기준 데이터가 없습니다. 지수 차트가 표시되지 않습니다.")
    else:
        st.info("ℹ️ 시장 지수 데이터가 아직 없습니다.")

    # 2. 계좌별 포트폴리오 정규화
    if not portfolio_snapshots.empty and not accounts_df.empty:
        # 계좌명 매핑
        account_names = {}
        for _, acc in accounts_df.iterrows():
            account_names[acc['id']] = f"계좌 {acc['account_number']}"

        # 계좌별로 처리
        for account_id in portfolio_snapshots['account_id'].unique():
            account_data = portfolio_snapshots[portfolio_snapshots['account_id'] == account_id]
            account_name = account_names.get(account_id, f"계좌 {account_id}")

            # 날짜별로 그룹화하고 KRW + USD 합산
            account_by_date = {}
            for date, group in account_data.groupby('snapshot_date'):
                total_value = group['total_value'].sum()
                account_by_date[date] = total_value

            # 기준일 값
            if baseline_date in account_by_date:
                baseline_value = account_by_date[baseline_date]

                if baseline_value > 0:
                    # 정규화
                    for date, value in account_by_date.items():
                        normalized_data.append({
                            'snapshot_date': date,
                            'Category': account_name,
                            'Normalized Value': value / baseline_value,
                            'Actual Value': value
                        })

    # 3. 전체 포트폴리오 정규화
    if not aggregate_history.empty:
        # 기준일 데이터
        baseline_agg = aggregate_history[aggregate_history['snapshot_date'] == baseline_date]

        if not baseline_agg.empty:
            baseline_total = baseline_agg['total_value'].iloc[0]

            if baseline_total > 0:
                for _, row in aggregate_history.iterrows():
                    normalized_data.append({
                        'snapshot_date': row['snapshot_date'],
                        'Category': '전체 포트폴리오',
                        'Normalized Value': row['total_value'] / baseline_total,
                        'Actual Value': row['total_value']
                    })

    # 4. 통합 차트 생성
    if normalized_data:
        st.caption("모든 지표를 2025-10-13 기준 1.0으로 정규화하여 상대적 성과를 비교합니다.")

        normalized_df = pd.DataFrame(normalized_data)

        # 범례 순서 지정
        category_order = [
            '전체 포트폴리오',
            '계좌 1',
            '계좌 2',
            '계좌 3',
            '계좌 4',
            '계좌 5',
            'S&P 500',
            'NASDAQ 100',
            'KOSPI'
        ]

        # Category를 Categorical로 변환하여 순서 적용
        normalized_df['Category'] = pd.Categorical(
            normalized_df['Category'],
            categories=category_order,
            ordered=True
        )

        # Y축 범위 계산 (최소/최대값에 여유 공간 추가)
        min_value = normalized_df['Normalized Value'].min()
        max_value = normalized_df['Normalized Value'].max()
        y_margin = (max_value - min_value) * 0.1  # 10% 여유
        y_range = [min_value - y_margin, max_value + y_margin]

        # Plotly 라인 차트 생성
        import plotly.express as px
        fig = px.line(
            normalized_df,
            x='snapshot_date',
            y='Normalized Value',
            color='Category',
            category_orders={'Category': category_order},  # 범례 순서 지정
            title='성과 비교',
            labels={'snapshot_date': '날짜', 'Category': '항목'},
            hover_data={
                'snapshot_date': '|%Y-%m-%d',  # 날짜 형식
                'Normalized Value': False,  # 정규화 값 숨김
                'Actual Value': ':,.0f'  # 실제 값 표시 (천 단위 구분)
            }
        )

        fig.update_layout(
            hovermode='closest',  # 개별 라인 호버로 변경
            legend=dict(
                orientation='v',
                yanchor='top',
                y=1,
                xanchor='left',
                x=1.02
            ),
            height=600,
            yaxis_title=None  # Y축 제목 제거
        )

        # X축 설정 (날짜만 표시)
        fig.update_xaxes(
            dtick="D1",  # 하루 단위
            tickformat="%Y-%m-%d"  # 날짜 형식
        )

        # Y축 설정 (눈금 숨김)
        fig.update_yaxes(
            showticklabels=False,  # 눈금 레이블 숨김
            range=y_range  # 자동 계산된 범위
        )

        st.plotly_chart(fig, use_container_width=True)

        # 범례 설명
        with st.expander("💡 차트 사용법"):
            st.markdown("""
            - **범례 클릭**: 특정 항목을 숨기거나 표시할 수 있습니다
            - **더블 클릭**: 해당 항목만 단독으로 표시합니다
            - **기준선 (1.0)**: 2025년 10월 13일 기준값
            - **1.05**: 기준일 대비 5% 상승
            - **0.95**: 기준일 대비 5% 하락
            """)
    else:
        st.info("정규화할 데이터가 부족합니다. 2025-10-13의 기준 데이터가 필요합니다.")

    # ========== 원금 vs 계좌평가액 차트 ==========
    st.markdown("---")
    st.markdown("### 💰 원금 vs 계좌평가액")
    st.caption("계좌별 원금(입출금만 반영)과 계좌평가액(주식+현금)의 시계열 추이")
    st.info("ℹ️ 개별 계좌는 각 계좌의 원래 통화로 표시되며, 전체 포트폴리오는 일별 실제 환율을 반영하여 KRW로 통합 표시됩니다.")

    if not portfolio_snapshots.empty and not accounts_df.empty:
        # 계좌별 차트 생성 (각 계좌의 원래 통화로 표시)
        account_charts_data = []
        # 전체 포트폴리오용 데이터 (일별 환율 반영하여 KRW로 통합)
        total_portfolio_data = {}

        for _, acc in accounts_df.iterrows():
            account_id = acc['id']
            account_number = acc['account_number']
            account_name = f"계좌 {account_number}"
            allowed_currencies = acc['allowed_currencies']

            # 해당 계좌의 스냅샷 데이터
            account_snapshots = portfolio_snapshots[portfolio_snapshots['account_id'] == account_id].copy()

            if not account_snapshots.empty:
                # cash_transactions 미리 조회 (한 번만)
                cash_txns_account = get_cash_transactions(supabase, account_id)
                if not cash_txns_account.empty:
                    cash_txns_account['transaction_date'] = pd.to_datetime(cash_txns_account['transaction_date'])

                # 초기 시드 머니
                initial_seed_krw = acc['initial_seed_money_krw']
                initial_seed_usd = acc['initial_seed_money_usd']

                # 계좌의 주 통화 결정 (allowed_currencies에서 첫 번째)
                primary_currency = allowed_currencies[0] if allowed_currencies else 'KRW'

                # 개별 계좌 차트용: 주 통화 기준
                account_by_date = {}

                for date, group in account_snapshots.groupby('snapshot_date'):
                    # exchange_rate 가져오기 (해당 날짜의 실제 환율)
                    # 1. 스냅샷에 저장된 환율 우선 사용
                    exchange_rate = None
                    if 'exchange_rate' in group.columns:
                        valid_rates = group['exchange_rate'].dropna()
                        if len(valid_rates) > 0:
                            exchange_rate = float(valid_rates.iloc[0])

                    # 2. 스냅샷에 없으면 해당 날짜의 과거 환율 조회
                    if exchange_rate is None:
                        exchange_rate = get_historical_usd_krw_rate(date)

                    # 원금 계산 (초기 시드 + 입금 - 출금, RP 이자 및 주식 투자 제외)
                    principal_krw = 0
                    principal_usd = 0

                    if not cash_txns_account.empty:
                        # 해당 날짜까지의 거래만 필터링
                        cash_until_date = cash_txns_account[cash_txns_account['transaction_date'] <= date]

                        # KRW 원금 계산
                        krw_txns = cash_until_date[cash_until_date['currency'] == 'KRW']
                        deposits_krw = krw_txns[krw_txns['transaction_type'] == 'DEPOSIT']['amount'].sum() if not krw_txns.empty else 0
                        withdrawals_krw = krw_txns[krw_txns['transaction_type'] == 'WITHDRAWAL']['amount'].sum() if not krw_txns.empty else 0
                        principal_krw = initial_seed_krw + deposits_krw - withdrawals_krw

                        # USD 원금 계산
                        usd_txns = cash_until_date[cash_until_date['currency'] == 'USD']
                        deposits_usd = usd_txns[usd_txns['transaction_type'] == 'DEPOSIT']['amount'].sum() if not usd_txns.empty else 0
                        withdrawals_usd = usd_txns[usd_txns['transaction_type'] == 'WITHDRAWAL']['amount'].sum() if not usd_txns.empty else 0
                        principal_usd = initial_seed_usd + deposits_usd - withdrawals_usd
                    else:
                        # cash_transactions가 없으면 초기 시드만
                        principal_krw = initial_seed_krw
                        principal_usd = initial_seed_usd

                    # 계좌 평가액 계산 (통화별 합산)
                    total_value_krw = 0
                    total_value_usd = 0

                    for _, row in group.iterrows():
                        currency = row['currency']
                        total_val = row['total_value']

                        if currency == 'KRW':
                            total_value_krw += total_val
                        else:  # USD
                            total_value_usd += total_val

                    # 개별 계좌 차트: 주 통화 기준으로 저장
                    if primary_currency == 'USD':
                        # USD 계좌: USD로 표시
                        account_by_date[date] = {
                            'total_value': total_value_usd + (total_value_krw / exchange_rate),
                            'principal': principal_usd + (principal_krw / exchange_rate),
                            'currency': 'USD'
                        }
                    else:
                        # KRW 계좌: KRW로 표시
                        account_by_date[date] = {
                            'total_value': total_value_krw + (total_value_usd * exchange_rate),
                            'principal': principal_krw + (principal_usd * exchange_rate),
                            'currency': 'KRW'
                        }

                    # 전체 포트폴리오용: 일별 환율 반영하여 KRW로 통합
                    if date not in total_portfolio_data:
                        total_portfolio_data[date] = {'total_value': 0, 'principal': 0}

                    total_portfolio_data[date]['total_value'] += total_value_krw + (total_value_usd * exchange_rate)
                    total_portfolio_data[date]['principal'] += principal_krw + (principal_usd * exchange_rate)

                account_charts_data.append({
                    'account_name': account_name,
                    'account_number': account_number,
                    'data': account_by_date,
                    'currency': primary_currency
                })

        # 계좌별 차트 표시 (2-column 레이아웃)
        if account_charts_data:
            for i in range(0, len(account_charts_data), 2):
                cols = st.columns(2)

                for col_idx, chart_data in enumerate(account_charts_data[i:i+2]):
                    with cols[col_idx]:
                        # 데이터 준비
                        dates = sorted(chart_data['data'].keys())
                        total_values = [chart_data['data'][d]['total_value'] for d in dates]
                        principals = [chart_data['data'][d]['principal'] for d in dates]
                        currency = chart_data['currency']

                        # DataFrame 생성
                        chart_df = pd.DataFrame({
                            'Date': dates * 2,
                            'Type': ['계좌평가액'] * len(dates) + ['원금'] * len(dates),
                            'Value': total_values + principals
                        })

                        # 통화에 따른 레이블 및 포맷
                        if currency == 'USD':
                            value_label = '금액 (USD)'
                            tick_format = "$,.0f" if max(total_values + principals) >= 1000 else "$,.2f"
                        else:
                            value_label = '금액 (KRW)'
                            tick_format = ",.0f"

                        # Plotly 차트
                        fig_account = px.line(
                            chart_df,
                            x='Date',
                            y='Value',
                            color='Type',
                            title=chart_data['account_name'],
                            labels={'Date': '날짜', 'Value': value_label, 'Type': '구분'},
                            color_discrete_map={'계좌평가액': '#2e7d32', '원금': '#1976d2'}
                        )

                        fig_account.update_layout(
                            hovermode='x unified',
                            legend=dict(
                                orientation='h',
                                yanchor='bottom',
                                y=1.02,
                                xanchor='right',
                                x=1
                            ),
                            height=400
                        )

                        fig_account.update_xaxes(tickformat="%Y-%m-%d")
                        fig_account.update_yaxes(tickformat=tick_format)

                        st.plotly_chart(fig_account, use_container_width=True)

            # 전체 포트폴리오 차트 (full-width) - 일별 환율 반영
            st.markdown("#### 전체 포트폴리오 (일별 환율 반영)")

            # 전체 포트폴리오 데이터는 이미 계산됨 (total_portfolio_data)
            # 데이터 준비
            dates = sorted(total_portfolio_data.keys())
            total_values = [total_portfolio_data[d]['total_value'] for d in dates]
            principals = [total_portfolio_data[d]['principal'] for d in dates]

            # DataFrame 생성
            total_chart_df = pd.DataFrame({
                'Date': dates * 2,
                'Type': ['계좌평가액'] * len(dates) + ['원금'] * len(dates),
                'Value': total_values + principals
            })

            # Plotly 차트
            fig_total = px.line(
                total_chart_df,
                x='Date',
                y='Value',
                color='Type',
                title='전체 포트폴리오',
                labels={'Date': '날짜', 'Value': '금액 (KRW)', 'Type': '구분'},
                color_discrete_map={'계좌평가액': '#2e7d32', '원금': '#1976d2'}
            )

            fig_total.update_layout(
                hovermode='x unified',
                legend=dict(
                    orientation='h',
                    yanchor='bottom',
                    y=1.02,
                    xanchor='right',
                    x=1
                ),
                height=500
            )

            fig_total.update_xaxes(tickformat="%Y-%m-%d")
            fig_total.update_yaxes(tickformat=",.0f")

            st.plotly_chart(fig_total, use_container_width=True)
        else:
            st.info("차트를 표시할 데이터가 없습니다.")
    else:
        st.info("포트폴리오 스냅샷 데이터가 없습니다.")


def main():
    """메인 애플리케이션 (읽기 전용)"""
    supabase = get_supabase_client()

    # 사이드바: 네비게이션
    with st.sidebar:
        st.header("📂 페이지 선택")

        page = st.radio(
            "이동:",
            ["🏠 Overview", "📈 통계", "1️⃣ 계좌 1", "2️⃣ 계좌 2", "3️⃣ 계좌 3", "4️⃣ 계좌 4", "5️⃣ 계좌 5"],
            label_visibility="collapsed"
        )

    # 메인 영역: 선택된 페이지 표시
    if page == "🏠 Overview":
        show_overview_page(supabase)
    elif page == "📈 통계":
        show_statistics_page(supabase)
    else:
        # 계좌 번호 추출 (예: "1️⃣ 계좌 1" -> 1)
        account_num = int(page.split()[-1])  # 마지막 요소가 숫자
        show_account_page(supabase, account_num)


if __name__ == "__main__":
    main()
