"""
Exchange Rate Module - Real-time USD/KRW exchange rate fetching
"""
import yfinance as yf
import streamlit as st
from datetime import datetime


@st.cache_data(ttl=900)  # 15분 캐싱
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
            'timestamp': 조회 시각
        }
    """
    rate = get_usd_krw_rate()

    return {
        'rate': rate,
        'formatted': format_exchange_rate(rate),
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
