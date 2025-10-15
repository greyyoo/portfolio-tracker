"""
Market Data Module - Real-time market indices and Fear & Greed Index
"""
import yfinance as yf
import streamlit as st
from typing import Dict, Optional
from datetime import datetime


@st.cache_data(ttl=300)  # 5분 캐싱
def get_market_today() -> Dict:
    """
    실시간 시장 지표 조회 (S&P 500, NASDAQ 100, KOSPI, USD/KRW, Fear & Greed Index)

    Returns:
        {
            'sp500': {'price': float, 'change_pct': float, 'error': bool},
            'nasdaq': {'price': float, 'change_pct': float, 'error': bool},
            'kospi': {'price': float, 'change_pct': float, 'error': bool},
            'usdkrw': {'price': float, 'change_pct': float, 'error': bool},
            'fgi': {'value': int, 'classification': str, 'error': bool},
            'last_updated': str
        }
    """
    market_data = {}

    # S&P 500 (^GSPC)
    try:
        sp500 = yf.Ticker("^GSPC")
        hist = sp500.history(period="2d")
        if len(hist) >= 2:
            current = float(hist['Close'].iloc[-1])
            previous = float(hist['Close'].iloc[-2])
            change_pct = ((current - previous) / previous) * 100
            market_data['sp500'] = {'price': current, 'change_pct': change_pct, 'error': False}
        else:
            market_data['sp500'] = {'price': 0, 'change_pct': 0, 'error': True}
    except Exception as e:
        print(f"Error fetching S&P 500: {e}")
        market_data['sp500'] = {'price': 0, 'change_pct': 0, 'error': True}

    # NASDAQ 100 (^NDX)
    try:
        nasdaq = yf.Ticker("^NDX")
        hist = nasdaq.history(period="2d")
        if len(hist) >= 2:
            current = float(hist['Close'].iloc[-1])
            previous = float(hist['Close'].iloc[-2])
            change_pct = ((current - previous) / previous) * 100
            market_data['nasdaq'] = {'price': current, 'change_pct': change_pct, 'error': False}
        else:
            market_data['nasdaq'] = {'price': 0, 'change_pct': 0, 'error': True}
    except Exception as e:
        print(f"Error fetching NASDAQ 100: {e}")
        market_data['nasdaq'] = {'price': 0, 'change_pct': 0, 'error': True}

    # KOSPI (^KS11)
    try:
        kospi = yf.Ticker("^KS11")
        hist = kospi.history(period="2d")
        if len(hist) >= 2:
            current = float(hist['Close'].iloc[-1])
            previous = float(hist['Close'].iloc[-2])
            change_pct = ((current - previous) / previous) * 100
            market_data['kospi'] = {'price': current, 'change_pct': change_pct, 'error': False}
        else:
            market_data['kospi'] = {'price': 0, 'change_pct': 0, 'error': True}
    except Exception as e:
        print(f"Error fetching KOSPI: {e}")
        market_data['kospi'] = {'price': 0, 'change_pct': 0, 'error': True}

    # USD/KRW (KRW=X)
    try:
        # 여러 티커 시도 (KRW=X, USDKRW=X)
        tickers_to_try = ["KRW=X", "USDKRW=X"]
        success = False

        for ticker_symbol in tickers_to_try:
            try:
                krw = yf.Ticker(ticker_symbol)
                hist = krw.history(period="5d")  # 주말 고려해서 5일치 조회

                if len(hist) >= 1:
                    # 최근 데이터 가져오기
                    current = float(hist['Close'].iloc[-1])

                    # 유효성 검증 (환율이 합리적인 범위인지 확인: 1000-2000 KRW)
                    if 1000 <= current <= 2000:
                        # 전일 대비 변화율 계산
                        if len(hist) >= 2:
                            previous = float(hist['Close'].iloc[-2])
                            change_pct = ((current - previous) / previous) * 100
                        else:
                            change_pct = 0

                        market_data['usdkrw'] = {'price': current, 'change_pct': change_pct, 'error': False}
                        success = True
                        break
            except Exception as ticker_error:
                print(f"Error with ticker {ticker_symbol}: {ticker_error}")
                continue

        # 모든 티커 시도 실패 시 기본값 사용
        if not success:
            # exchange_rate.py의 함수 재사용 시도
            try:
                from exchange_rate import get_usd_krw_rate
                current_rate = get_usd_krw_rate()
                if current_rate and 1000 <= current_rate <= 2000:
                    market_data['usdkrw'] = {'price': current_rate, 'change_pct': 0, 'error': False}
                else:
                    market_data['usdkrw'] = {'price': 1300, 'change_pct': 0, 'error': True}
            except:
                market_data['usdkrw'] = {'price': 1300, 'change_pct': 0, 'error': True}

    except Exception as e:
        print(f"Error fetching USD/KRW: {e}")
        # 기본값 사용
        market_data['usdkrw'] = {'price': 1300, 'change_pct': 0, 'error': True}

    # Fear & Greed Index (CNN)
    try:
        import fear_and_greed
        fg = fear_and_greed.get()
        fgi_value = int(float(fg[0]))  # 0-100 점수
        fgi_status_raw = str(fg[1])  # 소문자로 반환될 수 있음

        # 대소문자 정규화 (Title Case로 변환)
        fgi_status = fgi_status_raw.title()  # 'fear' → 'Fear', 'extreme fear' → 'Extreme Fear'

        market_data['fgi'] = {'value': fgi_value, 'classification': fgi_status, 'error': False}
    except Exception as e:
        print(f"Error fetching Fear & Greed Index: {e}")
        market_data['fgi'] = {'value': 50, 'classification': 'Neutral', 'error': True}

    # 업데이트 시각 (KST)
    from zoneinfo import ZoneInfo
    kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
    market_data['last_updated'] = kst_now.strftime("%Y-%m-%d %H:%M:%S KST")

    return market_data


def get_fgi_badge_color(classification: str) -> str:
    """
    Fear & Greed 분류에 따른 배지 색상 반환

    Args:
        classification: 'Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'

    Returns:
        색상 코드
    """
    color_map = {
        'Extreme Fear': '#dc3545',  # 빨강 (진한 빨강)
        'Fear': '#e57373',          # 연한 빨강
        'Neutral': '#6c757d',       # 회색
        'Greed': '#81c784',         # 연한 초록
        'Extreme Greed': '#2e7d32'  # 진한 초록
    }
    return color_map.get(classification, '#6c757d')


def get_change_color(change_pct: float) -> str:
    """
    등락률에 따른 텍스트 색상 반환

    Args:
        change_pct: 등락률 (%)

    Returns:
        색상 (green, red, gray)
    """
    if change_pct > 0:
        return 'green'
    elif change_pct < 0:
        return 'red'
    else:
        return 'gray'
