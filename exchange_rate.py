"""
Exchange Rate Module - Real-time USD/KRW exchange rate fetching
"""
import yfinance as yf
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo


@st.cache_data(ttl=60)  # 1분 캐싱
def get_usd_krw_rate() -> float:
    """
    실시간 USD/KRW 환율 조회 (yfinance 사용)

    Returns:
        float: 1 USD = X KRW
    """
    try:
        # yfinance를 통해 USD/KRW=X (USDKRW=X) 환율 조회
        ticker = yf.Ticker("KRW=X")

        # 현재 환율 가져오기
        data = ticker.history(period="1d")

        if not data.empty:
            current_rate = data['Close'].iloc[-1]
            return float(current_rate)
        else:
            # 데이터를 가져오지 못한 경우 대체 방법
            ticker_info = ticker.info
            current_rate = ticker_info.get('regularMarketPrice', 1300.0)  # 기본값 1300
            return float(current_rate)

    except Exception as e:
        # 에러 발생 시 기본 환율 사용 (대략적인 값)
        st.warning(f"⚠️ 환율 조회 실패, 기본 환율(1 USD = 1300 KRW) 사용: {str(e)}")
        return 1300.0


@st.cache_data(ttl=3600)  # 1시간 캐싱 (과거 데이터는 변하지 않음)
def get_historical_usd_krw_rate(date: str) -> float:
    """
    특정 날짜의 USD/KRW 환율 조회

    Args:
        date: 날짜 (YYYY-MM-DD 형식 또는 datetime 객체)

    Returns:
        float: 해당 날짜의 환율 (1 USD = X KRW)
    """
    try:
        # datetime 객체를 문자열로 변환
        if hasattr(date, 'strftime'):
            date_str = date.strftime('%Y-%m-%d')
        else:
            date_str = str(date)

        # yfinance로 특정 날짜의 환율 조회
        ticker = yf.Ticker("KRW=X")

        # 해당 날짜 전후로 조회 (주말/공휴일 대비)
        from datetime import datetime, timedelta
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        start_date = (target_date - timedelta(days=3)).strftime('%Y-%m-%d')
        end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

        data = ticker.history(start=start_date, end=end_date)

        if not data.empty:
            # 가장 가까운 날짜의 종가 사용
            closest_rate = data['Close'].iloc[-1]
            return float(closest_rate)
        else:
            # 과거 데이터를 가져오지 못한 경우 현재 환율 사용
            return get_usd_krw_rate()

    except Exception as e:
        # 에러 발생 시 현재 환율 사용
        return get_usd_krw_rate()


def convert_usd_to_krw(usd_amount: float, exchange_rate: float) -> float:
    """
    USD를 KRW로 변환

    Args:
        usd_amount: USD 금액
        exchange_rate: 환율 (1 USD = X KRW)

    Returns:
        KRW 금액
    """
    return usd_amount * exchange_rate


def convert_krw_to_usd(krw_amount: float, exchange_rate: float) -> float:
    """
    KRW를 USD로 변환

    Args:
        krw_amount: KRW 금액
        exchange_rate: 환율 (1 USD = X KRW)

    Returns:
        USD 금액
    """
    return krw_amount / exchange_rate if exchange_rate > 0 else 0


def get_total_value_in_both_currencies(
    krw_value: float,
    usd_value: float,
    exchange_rate: float
) -> dict:
    """
    KRW와 USD 자산을 모두 각 통화로 변환하여 총액 계산

    Args:
        krw_value: KRW 자산 총액
        usd_value: USD 자산 총액
        exchange_rate: 현재 환율

    Returns:
        {
            'total_krw': KRW 기준 총 자산,
            'total_usd': USD 기준 총 자산,
            'exchange_rate': 사용된 환율
        }
    """
    # KRW 기준 총액: 기존 KRW + (USD를 KRW로 변환)
    total_krw = krw_value + convert_usd_to_krw(usd_value, exchange_rate)

    # USD 기준 총액: 기존 USD + (KRW를 USD로 변환)
    total_usd = usd_value + convert_krw_to_usd(krw_value, exchange_rate)

    return {
        'total_krw': total_krw,
        'total_usd': total_usd,
        'exchange_rate': exchange_rate
    }


def format_exchange_rate(rate: float) -> str:
    """
    환율을 읽기 쉬운 형식으로 포맷팅

    Args:
        rate: 환율

    Returns:
        포맷팅된 문자열 (예: "1 USD = 1,300.50 KRW")
    """
    return f"1 USD = {rate:,.2f} KRW"


def get_exchange_rate_info() -> dict:
    """
    환율 정보 및 메타데이터 조회

    Returns:
        {
            'rate': 환율,
            'formatted': 포맷팅된 환율 문자열,
            'timestamp': 조회 시각 (KST)
        }
    """
    rate = get_usd_krw_rate()

    # KST 시간으로 변환
    kst_now = datetime.now(ZoneInfo("Asia/Seoul"))

    return {
        'rate': rate,
        'formatted': format_exchange_rate(rate),
        'timestamp': kst_now.strftime("%Y-%m-%d %H:%M:%S KST")
    }
