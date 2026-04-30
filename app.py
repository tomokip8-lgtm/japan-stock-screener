 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index 29bf32a3b40c87a262b238d87e0842cc0f0ec6a9..98f90ca0c35d2639bc81487747fa81518cca86c4 100644
--- a/app.py
+++ b/app.py
@@ -1,4 +1,62 @@
+import pandas as pd
 import streamlit as st
+import yfinance as yf
 
-st.title("需給分析つき日本株スクリーナー")
-st.write("アプリ起動成功")
\ No newline at end of file
+st.set_page_config(page_title="日本株スクリーナー", layout="wide")
+st.title("日本株スクリーナー")
+st.caption("4桁の銘柄コードを入力して株価を取得します（例: 7203）。")
+
+
+def fetch_history(stock_code: str, period: str) -> pd.DataFrame:
+    ticker = f"{stock_code}.T"
+    data = yf.Ticker(ticker).history(period=period, auto_adjust=False)
+    if data.empty:
+        return data
+
+    # 表示に使う列だけ残して見やすくする
+    use_cols = ["Open", "High", "Low", "Close", "Volume"]
+    data = data[[c for c in use_cols if c in data.columns]].copy()
+    data.index = data.index.tz_localize(None)
+    return data
+
+
+code_col, period_col = st.columns([2, 1])
+with code_col:
+    stock_code = st.text_input("銘柄コード（4桁）", value="7203").strip()
+with period_col:
+    period = st.selectbox("取得期間", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
+
+if st.button("株価を取得", type="primary"):
+    if not (stock_code.isdigit() and len(stock_code) == 4):
+        st.error("銘柄コードは4桁の数字で入力してください。")
+        st.stop()
+
+    with st.spinner("株価データを取得中..."):
+        try:
+            history = fetch_history(stock_code, period)
+        except Exception as exc:
+            st.error(f"データ取得中にエラーが発生しました: {exc}")
+            st.stop()
+
+    if history.empty:
+        st.warning("データが取得できませんでした。銘柄コードをご確認ください。")
+        st.stop()
+
+    ticker = f"{stock_code}.T"
+    st.success(f"{ticker} の株価データを取得しました。")
+
+    st.subheader("終値チャート")
+    st.line_chart(history["Close"])
+
+    latest = history.iloc[-1]
+    prev = history.iloc[-2] if len(history) >= 2 else latest
+    diff = float(latest["Close"] - prev["Close"])
+    diff_pct = (diff / float(prev["Close"]) * 100) if float(prev["Close"]) != 0 else 0.0
+
+    m1, m2, m3 = st.columns(3)
+    m1.metric("最新終値", f"{latest['Close']:.2f}")
+    m2.metric("前日比", f"{diff:+.2f}")
+    m3.metric("前日比(%)", f"{diff_pct:+.2f}%")
+
+    st.subheader("直近10件データ")
+    st.dataframe(history.tail(10), use_container_width=True)
 
EOF
)
