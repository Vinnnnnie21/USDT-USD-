import streamlit as st
import requests
import pandas as pd
import time
import plotly.graph_objects as go
from datetime import datetime
import pytz

# --- 页面配置 ---
st.set_page_config(
    page_title="USDT 实时溢价监控",
    page_icon="⚡",
    layout="wide"
)

# --- 核心函数 ---
def get_binance_p2p_price(trade_type):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    data = {"asset": "USDT", "fiat": "CNY", "merchantCheck": False, "page": 1, "payTypes": [], "publisherType": None, "rows": 5, "tradeType": trade_type}
    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        if response.json()['code'] == "000000":
            prices = [float(ad['adv']['price']) for ad in response.json()['data']]
            if len(prices) > 2: prices.remove(max(prices)); prices.remove(min(prices))
            return sum(prices) / len(prices)
    except: return None

def get_real_usd_cny():
    try:
        import yfinance as yf
        ticker = yf.Ticker("CNY=X")
        data = ticker.history(period="1d", interval="1m")
        return data['Close'].iloc[-1] if not data.empty else ticker.history(period="1d")['Close'].iloc[-1]
    except: return None

# --- 初始化 Session State ---
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 页面布局 ---
st.title("⚡ USDT 溢价率实时监控终端")
st.caption("数据来源: Binance P2P & Yahoo Finance | 自动刷新: 约 5-10 秒")

# 🔥 修复点 1：使用 st.empty() 创建单一占位符，防止数据堆叠
dashboard_placeholder = st.empty()

# --- 主循环逻辑 ---
if st.button("🔄 点击开始/刷新监控"):
    st.rerun()

while True:
    # 1. 获取数据
    usdt_buy = get_binance_p2p_price("BUY")
    usdt_sell = get_binance_p2p_price("SELL")
    usd_cny = get_real_usd_cny()
    
    tz = pytz.timezone('Asia/Shanghai')
    now_time = datetime.now(tz).strftime("%H:%M:%S")

    if usdt_buy and usdt_sell and usd_cny:
        usdt_avg = (usdt_buy + usdt_sell) / 2
        premium_rate = ((usdt_avg - usd_cny) / usd_cny) * 100
        
        # 更新数据
        new_data = {
            "time": now_time,
            "rate": premium_rate,
            "usdt": usdt_avg,
            "usd": usd_cny
        }
        st.session_state.history.append(new_data)
        if len(st.session_state.history) > 100:
            st.session_state.history.pop(0)
            
        df = pd.DataFrame(st.session_state.history)

        # 🔥 修复点 2：所有内容都在 placeholder 容器内渲染
        # 每次循环开始，这里面的内容都会被清空重画
        with dashboard_placeholder.container():
            # (A) 顶部指标栏
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("USDT 溢价率", f"{premium_rate:+.2f}%", delta_color="inverse")
            kpi2.metric("Binance USDT", f"¥{usdt_avg:.3f}")
            kpi3.metric("USD 汇率", f"¥{usd_cny:.4f}")

            # (B) 交互式图表
            fig = go.Figure()
            color = '#00ff00' if premium_rate > 0 else '#ff3333'
            
            fig.add_trace(go.Scatter(
                x=df['time'], y=df['rate'],
                mode='lines+markers',
                line=dict(color=color, width=2),
                marker=dict(size=6),
                name='Premium',
                # 🔥 修复点 3：把价格整合进鼠标悬停提示 (Tooltip)
                # customdata 用于传递额外数据给 hovertemplate
                customdata=df[['usdt', 'usd']],
                hovertemplate=
                '<b>⏱ %{x}</b><br>' +
                '📈 溢价率: <b>%{y:.2f}%</b><br>' +
                '-------------------<br>' +
                '💰 USDT价格: ¥%{customdata[0]:.3f}<br>' +
                '🇺🇸 美元汇率: ¥%{customdata[1]:.4f}<br>' +
                '<extra></extra>'
            ))
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            
            fig.update_layout(
                height=500,
                paper_bgcolor='#0e1117',
                plot_bgcolor='#0e1117',
                xaxis=dict(showgrid=True, gridcolor='#262730', tickmode='auto', nticks=10),
                yaxis=dict(showgrid=True, gridcolor='#262730', tickformat="+.2f"),
                margin=dict(l=0, r=0, t=10, b=0),
                font=dict(color="white"),
                hovermode="x unified" # 鼠标一动，显示X轴上所有信息
            )

            st.plotly_chart(fig, use_container_width=True)
    
    else:
        # 如果获取失败，只在占位符里显示警告，不会堆叠
        dashboard_placeholder.warning(f"[{now_time}] 数据获取中，请稍候...")

    time.sleep(5)
