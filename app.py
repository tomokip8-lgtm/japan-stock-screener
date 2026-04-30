from datetime import datetime

import pandas as pd
import streamlit as st
import yfinance as yf


def build_sample_history() -> pd.DataFrame:
    dates = pd.date_range(end=datetime.today(), periods=30, freq="B")
    close = pd.Series(range(3000, 3030), index=dates, dtype="float64")
    frame = pd.DataFrame(
        {
            "Open": close - 5,
            "High": close + 10,
            "Low": close - 15,
            "Close": close,
            "Volume": 1_000_000,
        }
    )
    frame.index.name = "Date"
    return frame


def fetch_history(stock_code: str, period: str, offline_mode: bool) -> pd.DataFrame:
    if offline_mode:
        return build_sample_history()

    ticker = f"{stock_code}.T"
    data = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    if data.empty:
        return data

    use_cols = ["Open", "High", "Low", "Close", "Volume"]
    data = data[[c for c in use_cols if c in data.columns]].copy()
    data.index = data.index.tz_localize(None)
    return data


def render_app() -> None:
    st.set_page_config(page_title="日本株スクリーナー", layout="wide")
    st.title("日本株スクリーナー")
    st.caption("4桁の銘柄コードを入力して株価を取得します（例: 7203）。")

    st.subheader("設定")
    offline_mode = st.checkbox("オフラインテストモード（ダミーデータを使用）", value=True)
    if offline_mode:
        st.info("オフラインテストモード: yfinance に接続せず、サンプル株価データで動作確認します。")

    code_col, period_col = st.columns([2, 1])
    with code_col:
        stock_code = st.text_input("銘柄コード（4桁）", value="7203").strip()
    with period_col:
        period = st.selectbox("取得期間", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)

    if st.button("株価を取得", type="primary"):
        if not (stock_code.isdigit() and len(stock_code) == 4):
            st.error("銘柄コードは4桁の数字で入力してください。")
            st.stop()

        with st.spinner("株価データを取得中..."):
            try:
                history = fetch_history(stock_code, period, offline_mode)
            except Exception as exc:
                st.error(f"データ取得中にエラーが発生しました: {exc}")
                st.stop()

        if history.empty:
            st.warning("データが取得できませんでした。銘柄コードをご確認ください。")
            st.stop()

        if offline_mode:
            st.success("オフラインテストデータの表示に成功しました。")
        else:
            ticker = f"{stock_code}.T"
            st.success(f"{ticker} の株価データを取得しました。")

        st.subheader("終値チャート")
        st.line_chart(history["Close"])

        latest = history.iloc[-1]
        prev = history.iloc[-2] if len(history) >= 2 else latest
        diff = float(latest["Close"] - prev["Close"])
        diff_pct = (diff / float(prev["Close"]) * 100) if float(prev["Close"]) != 0 else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("最新終値", f"{latest['Close']:.2f}")
        m2.metric("前日比", f"{diff:+.2f}")
        m3.metric("前日比(%)", f"{diff_pct:+.2f}%")

        st.subheader("直近10件データ")
        st.dataframe(history.tail(10), use_container_width=True)


st.title("需給分析つき日本株スクリーナー")
st.write("アプリ起動成功")
if __name__ == "__main__":
    render_app()
