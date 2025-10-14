"""
Chart generation module using Plotly.
"""
import plotly.graph_objects as go
import pandas as pd
from typing import Dict
from currency_utils import get_currency_symbol


def create_price_chart_with_transactions(
    historical_data: pd.DataFrame,
    transactions: pd.DataFrame,
    ticker: str,
    currency: str
) -> go.Figure:
    """
    거래 내역이 표시된 주가 차트 생성

    Args:
        historical_data: yfinance에서 가져온 히스토리컬 데이터 (Date index, Close column)
        transactions: 해당 티커의 거래 내역 DataFrame
        ticker: 티커 심볼
        currency: 통화 ('KRW' or 'USD')

    Returns:
        Plotly Figure 객체
    """
    fig = go.Figure()

    # 주가 라인 차트
    fig.add_trace(go.Scatter(
        x=historical_data.index,
        y=historical_data['Close'],
        mode='lines',
        name='종가',
        line=dict(color='#1f77b4', width=2)
    ))

    # 거래 내역 마커 추가
    if not transactions.empty:
        transactions['transaction_date'] = pd.to_datetime(transactions['transaction_date'])

        # 매수 거래 (녹색 삼각형)
        buy_txns = transactions[transactions['transaction_type'] == 'BUY']
        if not buy_txns.empty:
            fig.add_trace(go.Scatter(
                x=buy_txns['transaction_date'],
                y=buy_txns['trade_price'],
                mode='markers+text',
                name='매수',
                marker=dict(
                    symbol='triangle-up',
                    size=12,
                    color='green',
                    line=dict(color='darkgreen', width=2)
                ),
                text=['B'] * len(buy_txns),
                textposition='top center',
                hovertemplate=(
                    '<b>매수</b><br>' +
                    '날짜: %{x}<br>' +
                    f'가격: {get_currency_symbol(currency)}%{{y:,.{2 if currency == "USD" else 0}f}}<br>' +
                    '수량: %{customdata[0]}<br>' +
                    '<extra></extra>'
                ),
                customdata=buy_txns[['quantity']].values
            ))

        # 매도 거래 (빨간색 역삼각형)
        sell_txns = transactions[transactions['transaction_type'] == 'SELL']
        if not sell_txns.empty:
            fig.add_trace(go.Scatter(
                x=sell_txns['transaction_date'],
                y=sell_txns['trade_price'],
                mode='markers+text',
                name='매도',
                marker=dict(
                    symbol='triangle-down',
                    size=12,
                    color='red',
                    line=dict(color='darkred', width=2)
                ),
                text=['S'] * len(sell_txns),
                textposition='bottom center',
                hovertemplate=(
                    '<b>매도</b><br>' +
                    '날짜: %{x}<br>' +
                    f'가격: {get_currency_symbol(currency)}%{{y:,.{2 if currency == "USD" else 0}f}}<br>' +
                    '수량: %{customdata[0]}<br>' +
                    '<extra></extra>'
                ),
                customdata=sell_txns[['quantity']].values
            ))

    # 차트 레이아웃 설정
    fig.update_layout(
        title=f'{ticker} 주가 차트',
        xaxis_title='날짜',
        yaxis_title=f'가격 ({get_currency_symbol(currency)})',
        hovermode='x unified',
        template='plotly_white',
        height=500,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )

    # Y축 포맷 설정 (통화에 따라)
    if currency == 'KRW':
        fig.update_yaxes(tickformat=',.0f')
    else:
        fig.update_yaxes(tickformat=',.2f')

    return fig


def create_portfolio_distribution_chart(
    holdings_df: pd.DataFrame,
    current_prices: Dict[str, Dict],
    currency: str
) -> go.Figure:
    """
    포트폴리오 분포 파이 차트 생성

    Args:
        holdings_df: 현재 보유 주식 DataFrame (특정 통화로 필터링된 것)
        current_prices: 현재 가격 딕셔너리
        currency: 통화 ('KRW' or 'USD')

    Returns:
        Plotly Figure 객체
    """
    if holdings_df.empty:
        # 빈 차트 반환
        fig = go.Figure()
        fig.add_annotation(
            text="보유 주식이 없습니다",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20)
        )
        return fig

    # 각 주식의 평가 금액 계산
    market_values = []
    labels = []

    for ticker, row in holdings_df.iterrows():
        if ticker in current_prices:
            market_value = current_prices[ticker]['price'] * row['quantity']
            market_values.append(market_value)
            labels.append(f"{row['stock_name']} ({ticker})")

    # 파이 차트 생성
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=market_values,
        hovertemplate=(
            '<b>%{label}</b><br>' +
            f'평가금액: {get_currency_symbol(currency)}%{{value:,.{2 if currency == "USD" else 0}f}}<br>' +
            '비중: %{percent}<br>' +
            '<extra></extra>'
        )
    )])

    fig.update_layout(
        title=f'포트폴리오 분포 ({currency})',
        height=400
    )

    return fig
