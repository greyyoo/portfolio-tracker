"""
Backfill Market Indices Script
==============================
과거 누락된 market indices 데이터를 채우는 스크립트

사용법:
    python backfill_market_indices.py --start-date 2025-10-01 --end-date 2025-10-17

요구사항:
    - yfinance>=0.2.28
    - supabase>=2.0.0
    - pandas>=2.0.0
    - python-dotenv (optional)

주의사항:
    - .env 파일에 PUBLIC_SUPABASE_URL과 PUBLIC_SUPABASE_ANON_KEY 설정 필요
    - 주말 데이터는 자동으로 제외됨
    - 기존 데이터는 덮어쓰지 않고 업데이트됨 (COALESCE 사용)
"""

import os
import argparse
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
from supabase import create_client, Client
from typing import Dict

# 환경 변수 로드 (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def init_supabase() -> Client:
    """Supabase 클라이언트 초기화"""
    url = os.environ.get("PUBLIC_SUPABASE_URL")
    key = os.environ.get("PUBLIC_SUPABASE_ANON_KEY")

    if not url or not key:
        raise ValueError("PUBLIC_SUPABASE_URL and PUBLIC_SUPABASE_ANON_KEY must be set in environment variables")

    return create_client(url, key)


def fetch_historical_index(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    과거 지수 데이터 가져오기

    Args:
        ticker: Yahoo Finance ticker (e.g., '^GSPC', '^NDX', '^KS11', 'KRW=X')
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        DataFrame with Date and Close columns
    """
    print(f"  Fetching {ticker}...")

    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)

        if data.empty:
            print(f"    ⚠️  No data returned for {ticker}")
            return pd.DataFrame()

        # Multi-level columns handling
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Reset index to get Date column
        data = data.reset_index()

        # Select only Date and Close
        result = data[['Date', 'Close']].copy()
        result['Date'] = pd.to_datetime(result['Date']).dt.date

        print(f"    ✓ Fetched {len(result)} records")
        return result

    except Exception as e:
        print(f"    ❌ Error fetching {ticker}: {e}")
        return pd.DataFrame()


def backfill_market_indices(
    supabase: Client,
    start_date: str,
    end_date: str,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    과거 market indices 데이터 채우기

    Args:
        supabase: Supabase 클라이언트
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
        dry_run: True면 실제 저장 없이 시뮬레이션만 수행

    Returns:
        {
            'total_days': 처리된 날짜 수,
            'inserted': 새로 추가된 레코드 수,
            'updated': 업데이트된 레코드 수,
            'skipped_weekends': 건너뛴 주말 수,
            'errors': 오류 발생 횟수
        }
    """
    print(f"\n{'🔍 DRY RUN MODE' if dry_run else '▶️  BACKFILL START'}")
    print(f"Date range: {start_date} to {end_date}\n")

    # Fetch historical data for all indices
    print("📊 Fetching historical data...")
    spx_data = fetch_historical_index('^GSPC', start_date, end_date)
    ndx_data = fetch_historical_index('^NDX', start_date, end_date)
    kospi_data = fetch_historical_index('^KS11', start_date, end_date)
    usd_krw_data = fetch_historical_index('KRW=X', start_date, end_date)

    # Merge all data on Date
    print("\n🔗 Merging data...")
    merged = spx_data.rename(columns={'Close': 'spx_close'})

    if not ndx_data.empty:
        merged = merged.merge(
            ndx_data.rename(columns={'Close': 'ndx_close'}),
            on='Date',
            how='outer'
        )

    if not kospi_data.empty:
        merged = merged.merge(
            kospi_data.rename(columns={'Close': 'kospi_close'}),
            on='Date',
            how='outer'
        )

    if not usd_krw_data.empty:
        merged = merged.merge(
            usd_krw_data.rename(columns={'Close': 'usd_krw_rate'}),
            on='Date',
            how='outer'
        )

    # Filter out weekends
    merged['DayOfWeek'] = pd.to_datetime(merged['Date']).dt.dayofweek
    weekends = merged[merged['DayOfWeek'].isin([5, 6])]  # Saturday=5, Sunday=6
    merged = merged[~merged['DayOfWeek'].isin([5, 6])]

    print(f"  ✓ Total records: {len(merged)}")
    print(f"  ⏭️  Skipped weekends: {len(weekends)}")

    # Insert/Update data
    stats = {
        'total_days': len(merged),
        'inserted': 0,
        'updated': 0,
        'skipped_weekends': len(weekends),
        'errors': 0
    }

    if dry_run:
        print(f"\n🔍 DRY RUN: Would process {len(merged)} records")
        print("\nSample data (first 5 records):")
        print(merged.head().to_string(index=False))
        return stats

    print("\n💾 Storing data to Supabase...")

    for _, row in merged.iterrows():
        date = row['Date']
        spx = float(row['spx_close']) if pd.notna(row.get('spx_close')) else None
        ndx = float(row['ndx_close']) if pd.notna(row.get('ndx_close')) else None
        kospi = float(row['kospi_close']) if pd.notna(row.get('kospi_close')) else None
        usd_krw = float(row['usd_krw_rate']) if pd.notna(row.get('usd_krw_rate')) else None

        try:
            # Use upsert_market_indices RPC function
            result = supabase.rpc('upsert_market_indices', {
                'p_snapshot_date': str(date),
                'p_spx_close': spx,
                'p_ndx_close': ndx,
                'p_kospi_close': kospi,
                'p_usd_krw_rate': usd_krw
            }).execute()

            if result.data:
                stats['inserted'] += 1
                # Format values for display
                spx_str = f"{spx:.2f}" if spx is not None else "N/A"
                ndx_str = f"{ndx:.2f}" if ndx is not None else "N/A"
                kospi_str = f"{kospi:.2f}" if kospi is not None else "N/A"
                usd_krw_str = f"{usd_krw:.4f}" if usd_krw is not None else "N/A"
                print(f"  ✓ {date}: SPX={spx_str}, NDX={ndx_str}, KOSPI={kospi_str}, USD/KRW={usd_krw_str}")

        except Exception as e:
            stats['errors'] += 1
            print(f"  ❌ Error on {date}: {e}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Backfill market indices data for missing dates'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='End date (YYYY-MM-DD), defaults to yesterday'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate without actually storing data'
    )

    args = parser.parse_args()

    # Default end_date to yesterday
    if args.end_date is None:
        yesterday = datetime.now() - timedelta(days=1)
        args.end_date = yesterday.strftime('%Y-%m-%d')

    # Validate dates
    try:
        start = datetime.strptime(args.start_date, '%Y-%m-%d')
        end = datetime.strptime(args.end_date, '%Y-%m-%d')

        if start > end:
            print("❌ Error: start_date must be before end_date")
            return

    except ValueError as e:
        print(f"❌ Error: Invalid date format. Use YYYY-MM-DD. {e}")
        return

    # Initialize Supabase
    try:
        supabase = init_supabase()
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("\nPlease set environment variables:")
        print("  export PUBLIC_SUPABASE_URL='your_project_url'")
        print("  export PUBLIC_SUPABASE_ANON_KEY='your_anon_key'")
        print("\nOr create a .env file with:")
        print("  PUBLIC_SUPABASE_URL=your_project_url")
        print("  PUBLIC_SUPABASE_ANON_KEY=your_anon_key")
        return

    # Run backfill
    stats = backfill_market_indices(
        supabase,
        args.start_date,
        args.end_date,
        dry_run=args.dry_run
    )

    # Print summary
    print("\n" + "="*60)
    print("📊 BACKFILL SUMMARY")
    print("="*60)
    print(f"Total days processed:  {stats['total_days']}")
    print(f"Records inserted:      {stats['inserted']}")
    print(f"Records updated:       {stats['updated']}")
    print(f"Weekends skipped:      {stats['skipped_weekends']}")
    print(f"Errors:                {stats['errors']}")
    print("="*60)

    if stats['errors'] > 0:
        print("\n⚠️  Some errors occurred. Please check the output above.")
    elif args.dry_run:
        print("\n✓ Dry run completed successfully!")
        print("  Run without --dry-run to actually store the data.")
    else:
        print("\n✓ Backfill completed successfully!")


if __name__ == '__main__':
    main()
