"""
Portfolio calculations module - Multi-account & Currency-aware calculations with exchange rate support.
"""
import pandas as pd
from typing import Dict, Tuple, List, Optional
from supabase import Client
from database import get_cached_prices_by_tickers, calculate_cash_balance


def calculate_holdings(transactions_df: pd.DataFrame, account_id: Optional[str] = None) -> pd.DataFrame:
    """
    현재 보유 주식 계산 (계좌별 필터링 가능, 통화별로 분리하여 평균 단가 계산)

    Args:
        transactions_df: 모든 거래 내역 DataFrame
        account_id: 특정 계좌 ID (None이면 전체)

    Returns:
        보유 주식 정보 DataFrame
        - ticker (index)
        - account_id: 계좌 ID (account_id 파라미터가 None일 때만)
        - quantity: 보유 수량
        - avg_price: 평균 단가
        - stock_name: 주식명
        - country: 국가
        - currency: 통화
        - total_cost_basis: 총 투자 금액
    """
    if transactions_df.empty:
        return pd.DataFrame()

    # 특정 계좌만 필터링
    if account_id:
        transactions_df = transactions_df[transactions_df['account_id'] == account_id].copy()

    holdings = {}

    # 계좌별, 티커별로 그룹화
    if account_id:
        # 단일 계좌: 티커별로만 그룹화
        group_keys = ['ticker']
    else:
        # 전체 계좌: (account_id, ticker)로 그룹화
        group_keys = ['account_id', 'ticker']

    for key, group in transactions_df.groupby(group_keys):
        if not account_id:
            acc_id, ticker = key
        else:
            # 단일 그룹화 시 key는 단일 값 (튜플 아님)
            ticker = key if isinstance(key, str) else key[0]
            acc_id = account_id

        # 매수/매도 거래 분리
        buy_txns = group[group['transaction_type'] == 'BUY']
        sell_txns = group[group['transaction_type'] == 'SELL']

        # 수량 계산
        total_buy_qty = buy_txns['quantity'].sum() if not buy_txns.empty else 0
        total_sell_qty = sell_txns['quantity'].sum() if not sell_txns.empty else 0
        current_qty = total_buy_qty - total_sell_qty

        # 현재 보유 중인 주식만 포함
        if current_qty > 0:
            # 평균 단가 계산 (Average Cost Method)
            # 평단가는 매수 거래만으로 계산 (부분 매도 시에도 평단가는 변하지 않음)
            # 수수료 포함: 총 매수 금액 = (거래가 × 수량) + 수수료
            total_buy_cost = ((buy_txns['trade_price'] * buy_txns['quantity']) + buy_txns['fee'].fillna(0)).sum() if not buy_txns.empty else 0

            # 평균 단가 = 총 매수 금액 / 총 매수 수량
            avg_price = total_buy_cost / total_buy_qty if total_buy_qty > 0 else 0

            # 현재 보유 주식의 취득원가 = 평단가 × 현재 보유 수량
            total_cost_basis = avg_price * current_qty

            holding_key = (acc_id, ticker) if not account_id else ticker
            holdings[holding_key] = {
                'quantity': current_qty,
                'avg_price': avg_price,
                'stock_name': group.iloc[0]['stock_name'],
                'country': group.iloc[0]['country'],
                'currency': group.iloc[0]['currency'],
                'total_cost_basis': total_cost_basis
            }

            if not account_id:
                holdings[holding_key]['account_id'] = acc_id

    if not holdings:
        return pd.DataFrame()

    holdings_df = pd.DataFrame.from_dict(holdings, orient='index')

    if account_id:
        # 단일 계좌: ticker만 인덱스
        holdings_df.index.name = 'ticker'
    else:
        # 전체 계좌: MultiIndex (account_id, ticker)가 있음
        # 인덱스를 리셋하여 컬럼으로 만듦
        if isinstance(holdings_df.index, pd.MultiIndex):
            holdings_df = holdings_df.reset_index()
            # 첫 두 컬럼이 account_id, ticker
            holdings_df.columns = ['account_id', 'ticker'] + list(holdings_df.columns[2:])
            holdings_df = holdings_df.set_index('ticker')
        else:
            # 이미 단일 인덱스인 경우
            holdings_df.index.name = 'ticker'

    return holdings_df


def calculate_portfolio_metrics(
    supabase: Client,
    account_id: str,
    holdings_df: pd.DataFrame,
    current_prices: Dict[str, Dict],
    seed_money_krw: float,
    seed_money_usd: float
) -> Dict:
    """
    포트폴리오 전체 지표 계산 (통화별 분리, 잔여 현금 포함)

    Args:
        supabase: Supabase 클라이언트
        account_id: 계좌 UUID
        holdings_df: 현재 보유 주식 DataFrame
        current_prices: 현재 가격 딕셔너리 {ticker: {'price': float, 'currency': str}}
        seed_money_krw: 초기 투자금 (KRW)
        seed_money_usd: 초기 투자금 (USD)

    Returns:
        포트폴리오 지표 딕셔너리
        {
            'krw': {
                'stock_value': 주식 평가액,
                'cash': 잔여 현금 (DB에서 계산, RP 이자 및 입출금 포함),
                'total_value': 총 평가액 (주식 + 현금),
                'pl': 손익,
                'return_pct': 수익률,
                'invested': 주식 투자금
            },
            'usd': {...}
        }
    """
    # 통화별 보유 주식 분리
    krw_holdings = holdings_df[holdings_df['currency'] == 'KRW'] if not holdings_df.empty else pd.DataFrame()
    usd_holdings = holdings_df[holdings_df['currency'] == 'USD'] if not holdings_df.empty else pd.DataFrame()

    # KRW 포트폴리오 계산
    krw_stock_value = 0
    krw_invested = 0
    for ticker, row in krw_holdings.iterrows():
        if ticker in current_prices:
            krw_stock_value += current_prices[ticker]['price'] * row['quantity']
            krw_invested += row['total_cost_basis']

    # KRW 잔여 현금 = DB에서 계산 (초기 투자금 + 입금 + RP이자 - 주식투자 - 출금)
    krw_cash = calculate_cash_balance(supabase, account_id, 'KRW')
    krw_total_value = krw_stock_value + krw_cash
    krw_pl = krw_total_value - seed_money_krw
    krw_return = (krw_pl / seed_money_krw * 100) if seed_money_krw > 0 else 0

    # USD 포트폴리오 계산
    usd_stock_value = 0
    usd_invested = 0
    for ticker, row in usd_holdings.iterrows():
        if ticker in current_prices:
            usd_stock_value += current_prices[ticker]['price'] * row['quantity']
            usd_invested += row['total_cost_basis']

    # USD 잔여 현금 = DB에서 계산 (초기 투자금 + 입금 + RP이자 - 주식투자 - 출금)
    usd_cash = calculate_cash_balance(supabase, account_id, 'USD')
    usd_total_value = usd_stock_value + usd_cash
    usd_pl = usd_total_value - seed_money_usd
    usd_return = (usd_pl / seed_money_usd * 100) if seed_money_usd > 0 else 0

    return {
        'krw': {
            'stock_value': krw_stock_value,
            'cash': krw_cash,
            'total_value': krw_total_value,
            'pl': krw_pl,
            'return_pct': krw_return,
            'invested': krw_invested
        },
        'usd': {
            'stock_value': usd_stock_value,
            'cash': usd_cash,
            'total_value': usd_total_value,
            'pl': usd_pl,
            'return_pct': usd_return,
            'invested': usd_invested
        }
    }


def calculate_aggregate_metrics(
    accounts_data: List[Dict],
    exchange_rate: float
) -> Dict:
    """
    전체 계좌 합산 지표 계산 (환율 적용)

    Args:
        accounts_data: 각 계좌별 메트릭 리스트
            [{'account_id': str, 'metrics': {...}, 'seed_krw': float, 'seed_usd': float}, ...]
        exchange_rate: USD/KRW 환율

    Returns:
        {
            'total_value_krw': 전체 자산 (KRW 기준),
            'total_value_usd': 전체 자산 (USD 기준),
            'total_invested_krw': 총 투자금 (KRW 기준),
            'total_invested_usd': 총 투자금 (USD 기준),
            'total_pl_krw': 총 손익 (KRW 기준),
            'total_pl_usd': 총 손익 (USD 기준),
            'total_return_pct': 총 수익률 (%),
            'exchange_rate': 사용된 환율
        }
    """
    total_krw_value = 0
    total_usd_value = 0
    total_krw_invested = 0
    total_usd_invested = 0

    for account in accounts_data:
        metrics = account['metrics']

        # 각 계좌의 KRW/USD 자산 합산
        total_krw_value += metrics['krw']['total_value']
        total_usd_value += metrics['usd']['total_value']

        # 초기 투자금 합산
        total_krw_invested += account.get('seed_krw', 0)
        total_usd_invested += account.get('seed_usd', 0)

    # 환율 적용하여 통합 총액 계산
    # KRW 기준: 기존 KRW + (USD를 KRW로 변환)
    combined_value_krw = total_krw_value + (total_usd_value * exchange_rate)
    combined_invested_krw = total_krw_invested + (total_usd_invested * exchange_rate)

    # USD 기준: 기존 USD + (KRW를 USD로 변환)
    combined_value_usd = total_usd_value + (total_krw_value / exchange_rate if exchange_rate > 0 else 0)
    combined_invested_usd = total_usd_invested + (total_krw_invested / exchange_rate if exchange_rate > 0 else 0)

    # 손익 계산
    total_pl_krw = combined_value_krw - combined_invested_krw
    total_pl_usd = combined_value_usd - combined_invested_usd

    # 수익률 계산 (KRW 기준)
    total_return_pct = (total_pl_krw / combined_invested_krw * 100) if combined_invested_krw > 0 else 0

    return {
        'total_value_krw': combined_value_krw,
        'total_value_usd': combined_value_usd,
        'total_invested_krw': combined_invested_krw,
        'total_invested_usd': combined_invested_usd,
        'total_pl_krw': total_pl_krw,
        'total_pl_usd': total_pl_usd,
        'total_return_pct': total_return_pct,
        'exchange_rate': exchange_rate
    }


def calculate_closed_positions(transactions_df: pd.DataFrame, account_id: Optional[str] = None) -> pd.DataFrame:
    """
    청산된 포지션 계산 (시간순 FIFO 매칭, 재매수 시나리오 지원)

    로직:
    1. 거래를 날짜순으로 정렬
    2. 매수/매도를 순차적으로 매칭
    3. 누적 수량이 0이 되는 시점 = 1개 청산 완료
    4. 청산 후 새 매수 = 새로운 포지션 시작
    5. 각 청산마다 별도 레코드 생성 (같은 티커의 여러 청산 지원)

    Args:
        transactions_df: 모든 거래 내역 DataFrame
        account_id: 특정 계좌 ID (None이면 전체)

    Returns:
        청산된 포지션 DataFrame
        - ticker: 티커
        - account_id: 계좌 ID (account_id 파라미터가 None일 때만)
        - stock_name: 주식명
        - country: 국가
        - currency: 통화
        - total_shares_traded: 총 거래 수량
        - realized_pl: 실현 손익
        - realized_return_pct: 실현 수익률 (%)
        - result: Win/Loss 분류
        - first_trade_date: 첫 거래 날짜
        - last_trade_date: 마지막 거래 날짜
        - holding_period_days: 보유 기간 (일)
    """
    if transactions_df.empty:
        return pd.DataFrame()

    # 특정 계좌만 필터링
    if account_id:
        transactions_df = transactions_df[transactions_df['account_id'] == account_id].copy()

    closed_positions_list = []

    # 계좌별, 티커별로 그룹화
    if account_id:
        group_keys = ['ticker']
    else:
        group_keys = ['account_id', 'ticker']

    for key, group in transactions_df.groupby(group_keys):
        if not account_id:
            acc_id, ticker = key
        else:
            # 단일 그룹화 시 key는 단일 값 (튜플 아님)
            ticker = key if isinstance(key, str) else key[0]
            acc_id = account_id

        # 날짜순 정렬
        group['transaction_date'] = pd.to_datetime(group['transaction_date'])
        sorted_txns = group.sort_values('transaction_date').reset_index(drop=True)

        # 포지션 추적 변수
        position_open = False
        current_position = {
            'buy_txns': [],
            'sell_txns': [],
            'first_date': None
        }
        running_qty = 0

        # 시간순으로 거래 처리
        for idx, txn in sorted_txns.iterrows():
            if txn['transaction_type'] == 'BUY':
                if not position_open:
                    # 새 포지션 시작
                    position_open = True
                    current_position['first_date'] = txn['transaction_date']

                current_position['buy_txns'].append(txn)
                running_qty += txn['quantity']

            elif txn['transaction_type'] == 'SELL':
                current_position['sell_txns'].append(txn)
                running_qty -= txn['quantity']

                # 청산 완료 (수량 0)
                if running_qty == 0 and position_open:
                    # 청산 레코드 생성
                    closed_record = _create_closed_record(
                        current_position,
                        txn['transaction_date'],
                        ticker,
                        acc_id,
                        sorted_txns.iloc[0],
                        account_id
                    )
                    closed_positions_list.append(closed_record)

                    # 포지션 초기화 (다음 매수를 위해)
                    position_open = False
                    current_position = {
                        'buy_txns': [],
                        'sell_txns': [],
                        'first_date': None
                    }

    if not closed_positions_list:
        return pd.DataFrame()

    # DataFrame 생성
    closed_df = pd.DataFrame(closed_positions_list)
    return closed_df


def _create_closed_record(
    position: Dict,
    last_date: pd.Timestamp,
    ticker: str,
    acc_id: str,
    metadata: pd.Series,
    account_id_filter: Optional[str]
) -> Dict:
    """
    청산 레코드 생성 헬퍼 함수

    Args:
        position: 현재 포지션 정보 (buy_txns, sell_txns, first_date)
        last_date: 마지막 거래 날짜
        ticker: 티커
        acc_id: 계좌 ID
        metadata: 메타데이터 (stock_name, currency 등)
        account_id_filter: 계좌 필터 (None이면 account_id 컬럼 포함)

    Returns:
        청산 레코드 딕셔너리
    """
    # 매수 비용 및 매도 수익 계산 (수수료 포함)
    # 수수료 포함 매수 비용 = (거래가 × 수량) + 수수료
    buy_cost = sum((txn['trade_price'] * txn['quantity']) + txn.get('fee', 0) for txn in position['buy_txns'])
    # 수수료 차감 매도 수익 = (거래가 × 수량) - 수수료
    sell_revenue = sum((txn['trade_price'] * txn['quantity']) - txn.get('fee', 0) for txn in position['sell_txns'])
    total_qty = sum(txn['quantity'] for txn in position['buy_txns'])

    # 실현 손익 및 수익률 (수수료 반영됨)
    realized_pl = sell_revenue - buy_cost
    realized_return_pct = (realized_pl / buy_cost * 100) if buy_cost > 0 else 0

    # 보유 기간
    holding_days = (last_date - position['first_date']).days

    # 레코드 생성
    record = {
        'ticker': ticker,
        'stock_name': metadata['stock_name'],
        'country': metadata['country'],
        'currency': metadata['currency'],
        'total_shares_traded': total_qty,
        'realized_pl': realized_pl,
        'realized_return_pct': realized_return_pct,
        'result': 'Win' if realized_return_pct >= 0 else 'Loss',
        'first_trade_date': position['first_date'].strftime('%Y-%m-%d'),
        'last_trade_date': last_date.strftime('%Y-%m-%d'),
        'holding_period_days': holding_days
    }

    # account_id 필터가 None일 때만 account_id 컬럼 추가
    if account_id_filter is None:
        record['account_id'] = acc_id

    return record


def calculate_win_rate(closed_positions_df: pd.DataFrame) -> Dict:
    """
    청산된 포지션의 승률 및 통계 계산

    Args:
        closed_positions_df: 청산된 포지션 DataFrame

    Returns:
        {
            'total_trades': 전체 청산 수,
            'wins': Win 개수,
            'losses': Loss 개수,
            'win_rate': 승률 (%),
            'avg_win': 평균 수익률 (Win만, %),
            'avg_loss': 평균 손실률 (Loss만, %),
            'total_pl': 총 실현 손익,
            'avg_pl': 평균 실현 손익
        }
    """
    if closed_positions_df.empty:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'total_pl': 0,
            'avg_pl': 0
        }

    # Win/Loss 분류
    wins = closed_positions_df[closed_positions_df['realized_return_pct'] >= 0]
    losses = closed_positions_df[closed_positions_df['realized_return_pct'] < 0]

    total_trades = len(closed_positions_df)
    win_count = len(wins)
    loss_count = len(losses)

    # 승률 계산
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    # 평균 수익/손실률
    avg_win = wins['realized_return_pct'].mean() if not wins.empty else 0
    avg_loss = losses['realized_return_pct'].mean() if not losses.empty else 0

    # 총 손익 및 평균 손익
    total_pl = closed_positions_df['realized_pl'].sum()
    avg_pl = closed_positions_df['realized_pl'].mean()

    return {
        'total_trades': total_trades,
        'wins': win_count,
        'losses': loss_count,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_pl': total_pl,
        'avg_pl': avg_pl
    }


def add_current_prices_to_holdings(
    holdings_df: pd.DataFrame,
    current_prices: Dict[str, Dict]
) -> pd.DataFrame:
    """
    현재 보유 주식에 현재가 정보 추가

    Args:
        holdings_df: 현재 보유 주식 DataFrame
        current_prices: 현재 가격 딕셔너리

    Returns:
        현재가 정보가 추가된 DataFrame
        - current_price: 현재가
        - market_value: 평가 금액
        - unrealized_pl: 평가 손익
        - return_pct: 수익률 (%)
    """
    if holdings_df.empty:
        return holdings_df

    holdings_with_prices = holdings_df.copy()

    # 현재가 정보 추가
    holdings_with_prices['current_price'] = holdings_with_prices.index.map(
        lambda ticker: current_prices.get(ticker, {}).get('price', 0)
    )

    # 평가 금액 계산
    holdings_with_prices['market_value'] = (
        holdings_with_prices['current_price'] * holdings_with_prices['quantity']
    )

    # 평가 손익 계산
    holdings_with_prices['unrealized_pl'] = (
        holdings_with_prices['market_value'] - holdings_with_prices['total_cost_basis']
    )

    # 수익률 계산
    holdings_with_prices['return_pct'] = (
        holdings_with_prices['unrealized_pl'] / holdings_with_prices['total_cost_basis'] * 100
    ).fillna(0)

    return holdings_with_prices


def get_current_prices_from_cache(
    supabase: Client,
    holdings_df: pd.DataFrame
) -> Dict[str, Dict]:
    """
    데이터베이스 캐시에서 현재 가격 조회

    Args:
        supabase: Supabase 클라이언트
        holdings_df: 현재 보유 주식 DataFrame

    Returns:
        {ticker: {'price': float, 'currency': str}} 형태의 딕셔너리
    """
    if holdings_df.empty:
        return {}

    # 보유 중인 티커 리스트 추출
    tickers = holdings_df.index.tolist()

    # 데이터베이스에서 가격 조회
    cached_prices = get_cached_prices_by_tickers(supabase, tickers)

    # 반환 형식 변환: {ticker: price} → {ticker: {'price': price, 'currency': currency}}
    result = {}
    for ticker in tickers:
        if ticker in cached_prices:
            # holdings_df에서 통화 정보 가져오기
            currency = holdings_df.loc[ticker, 'currency']
            result[ticker] = {
                'price': cached_prices[ticker],
                'currency': currency
            }

    return result
