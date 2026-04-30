from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

WATCHLIST_DEFAULT = 'watchlist.csv'

REFERENCE_UNIVERSE = [
    {'code': '1332', 'name': 'ニッスイ', 'market': 'Prime', 'sector': '食品'},
    {'code': '1605', 'name': 'INPEX', 'market': 'Prime', 'sector': 'エネルギー'},
    {'code': '2502', 'name': 'アサヒ', 'market': 'Prime', 'sector': '食品'},
    {'code': '4063', 'name': '信越化学', 'market': 'Prime', 'sector': '化学'},
    {'code': '6501', 'name': '日立製作所', 'market': 'Prime', 'sector': '電機'},
    {'code': '6758', 'name': 'ソニーグループ', 'market': 'Prime', 'sector': '電機'},
    {'code': '7203', 'name': 'トヨタ自動車', 'market': 'Prime', 'sector': '輸送用機器'},
    {'code': '8306', 'name': '三菱UFJ', 'market': 'Prime', 'sector': '銀行'},
    {'code': '9432', 'name': 'NTT', 'market': 'Prime', 'sector': '情報通信'},
    {'code': '9983', 'name': 'ファストリ', 'market': 'Prime', 'sector': '小売'},
    {'code': '9348', 'name': 'ispace', 'market': 'Standard', 'sector': 'サービス'},
]


@st.cache_data
def load_universe(csv_path: str = "stocks.csv") -> pd.DataFrame:
    csv_file = Path(csv_path)
    if csv_file.exists():
        return pd.read_csv(csv_file, dtype={"code": str})
    return pd.DataFrame(REFERENCE_UNIVERSE)


def zscore_in_sector(df: pd.DataFrame, col: str, ascending: bool) -> pd.Series:
    def _z(s: pd.Series) -> pd.Series:
        std = s.std(ddof=0)
        if std == 0 or pd.isna(std):
            return pd.Series([0.0] * len(s), index=s.index)
        return (s - s.mean()) / std

    z = df.groupby('sector', group_keys=False)[col].apply(_z)
    return -z if ascending else z


def get_info(ticker: str) -> Dict:
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


def get_hist(ticker: str, period: str = '1y') -> pd.DataFrame:
    try:
        h = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        if h.empty:
            return h
        h.index = h.index.tz_localize(None)
        return h
    except Exception:
        return pd.DataFrame()


def compute_features(universe_df: pd.DataFrame, period: str) -> pd.DataFrame:
    rows = []
    for r in universe_df.itertuples(index=False):
        ticker = f'{r.code}.T'
        info = get_info(ticker)
        hist = get_hist(ticker, period=period)
        if hist.empty:
            continue

        close = hist['Close']
        ret_1m = close.pct_change(21).iloc[-1] if len(close) > 22 else np.nan
        ret_3m = close.pct_change(63).iloc[-1] if len(close) > 64 else np.nan
        vol_ratio = hist['Volume'].iloc[-1] / (hist['Volume'].tail(20).mean() + 1e-9)
        daily_ret = close.pct_change().dropna()
        price_z60 = 0.0
        if len(daily_ret) >= 60:
            r60 = daily_ret.tail(60)
            std = r60.std(ddof=0)
            price_z60 = float((r60.iloc[-1] - r60.mean()) / std) if std > 0 else 0.0

        rows.append(
            {
                'code': r.code,
                'name': r.name,
                'market': r.market,
                'sector': r.sector,
                'ticker': ticker,
                'close': float(close.iloc[-1]),
                'ret_1m': float(ret_1m) if pd.notna(ret_1m) else np.nan,
                'ret_3m': float(ret_3m) if pd.notna(ret_3m) else np.nan,
                'volume_ratio20': float(vol_ratio),
                'price_z60': price_z60,
                'roe': info.get('returnOnEquity', np.nan),
                'op_margin': info.get('operatingMargins', np.nan),
                'debt_to_equity': info.get('debtToEquity', np.nan),
                'trailing_pe': info.get('trailingPE', np.nan),
                'price_to_book': info.get('priceToBook', np.nan),
                'dividend_yield': info.get('dividendYield', np.nan),
                'revenue_growth': info.get('revenueGrowth', np.nan),
                'earnings_growth': info.get('earningsGrowth', np.nan),
            }
        )
    return pd.DataFrame(rows)


def score_stocks(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d['quality'] = (zscore_in_sector(d, 'roe', False) + zscore_in_sector(d, 'op_margin', False) + zscore_in_sector(d, 'debt_to_equity', True)) / 3
    d['growth'] = (zscore_in_sector(d, 'revenue_growth', False) + zscore_in_sector(d, 'earnings_growth', False)) / 2
    d['valuation'] = (zscore_in_sector(d, 'trailing_pe', True) + zscore_in_sector(d, 'price_to_book', True)) / 2
    d['safety'] = (zscore_in_sector(d, 'dividend_yield', False) + zscore_in_sector(d, 'debt_to_equity', True)) / 2
    d['total_score'] = 40 * d['quality'] + 25 * d['growth'] + 20 * d['valuation'] + 15 * d['safety']
    return d.sort_values('total_score', ascending=False)


def save_snapshot(df: pd.DataFrame, save_dir: str, filename: str = 'daily_snapshot.csv') -> Path:
    out_dir = Path(save_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    out = df.copy()
    out['snapshot_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if path.exists():
        old = pd.read_csv(path)
        out = pd.concat([old, out], ignore_index=True)
    out.to_csv(path, index=False, encoding='utf-8-sig')
    return path


def render_app() -> None:
    st.set_page_config(page_title='日本株長期投資スクリーナー', layout='wide')
    st.title('日本株 長期投資スクリーナー')

    st.subheader('データ取得設定')
    save_dir = st.text_input('ローカル保存先フォルダ', value='/Users/tomoki/Desktop/AI勉強用/株アプリ')
    period = st.selectbox('分析期間', ['6mo', '1y', '2y', '5y'], index=1)

    universe_df = load_universe()
    st.dataframe(universe_df, use_container_width=True)

    if st.button('データを取得して分析', type='primary'):
        feats = compute_features(universe_df, period)
        if feats.empty:
            st.warning('データ取得に失敗しました。')
            st.stop()

        scored = score_stocks(feats)
        try:
            save_path = save_snapshot(scored, save_dir)
            st.success(f'ローカル保存に成功: {save_path}')
        except Exception as exc:
            st.error(f'保存に失敗しました: {exc}')

        st.subheader('全体 Top10')
        st.dataframe(scored[['code', 'name', 'sector', 'close', 'total_score']].head(10), use_container_width=True)

        st.subheader('業種別 Top3')
        st.dataframe(scored.groupby('sector').head(3)[['code', 'name', 'sector', 'total_score']], use_container_width=True)

        st.subheader('業種別モメンタム')
        sec = scored.groupby('sector', as_index=False).agg(ret_1m=('ret_1m', 'mean'), ret_3m=('ret_3m', 'mean'))
        st.bar_chart(sec.set_index('sector')[['ret_1m', 'ret_3m']])

        st.subheader('異常検知（価格/出来高）')
        anomaly = scored.copy()
        anomaly['volume_spike'] = anomaly['volume_ratio20'] >= 3.0
        anomaly['price_jump'] = anomaly['price_z60'].abs() >= 3.0
        st.dataframe(anomaly[['code', 'name', 'volume_ratio20', 'price_z60', 'volume_spike', 'price_jump']].sort_values('volume_ratio20', ascending=False), use_container_width=True)


st.title("需給分析つき日本株スクリーナー")
st.write("アプリ起動成功")
if __name__ == '__main__':
    render_app()
