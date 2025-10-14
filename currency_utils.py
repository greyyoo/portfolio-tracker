"""
Currency formatting and utility functions.
"""


def format_currency(amount: float, currency: str) -> str:
    """
    통화 형식에 맞게 금액 포맷팅

    Args:
        amount: 금액
        currency: 'KRW' or 'USD'

    Returns:
        포맷팅된 문자열 (예: '₩1,000,000' or '$1,234.56')
    """
    if currency == 'KRW':
        return f"₩{amount:,.0f}"  # KRW는 소수점 없음
    elif currency == 'USD':
        return f"${amount:,.2f}"  # USD는 소수점 2자리
    else:
        return f"{amount:,.2f}"


def get_currency_symbol(currency: str) -> str:
    """
    통화 심볼 반환

    Args:
        currency: 'KRW' or 'USD'

    Returns:
        통화 심볼 ('₩' or '$')
    """
    return '₩' if currency == 'KRW' else '$'


def get_decimal_places(currency: str) -> int:
    """
    통화별 소수점 자리수 반환

    Args:
        currency: 'KRW' or 'USD'

    Returns:
        소수점 자리수 (KRW: 0, USD: 2)
    """
    return 0 if currency == 'KRW' else 2


def determine_currency_from_ticker(ticker: str) -> str:
    """
    티커 심볼로부터 통화 결정

    Args:
        ticker: 티커 심볼 (예: '005930.KS', 'AAPL')

    Returns:
        통화 코드 ('KRW' or 'USD')
    """
    if ticker.endswith('.KS') or ticker.endswith('.KQ'):
        return 'KRW'
    else:
        return 'USD'


def validate_ticker_format(ticker: str, country: str) -> str:
    """
    티커 형식 검증 및 자동 보정

    Args:
        ticker: 티커 심볼
        country: 'KOR' or 'USA'

    Returns:
        검증/보정된 티커 심볼
    """
    ticker = ticker.upper().strip()

    if country == 'KOR':
        # 한국 주식은 .KS 또는 .KQ 접미사 필요
        if not (ticker.endswith('.KS') or ticker.endswith('.KQ')):
            # 기본적으로 .KS 추가 (코스피)
            ticker = f"{ticker}.KS"

    return ticker
