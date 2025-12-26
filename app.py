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
    # Streamlit Cloud 有时访问 Yahoo Finance 不稳定，这里增加备用源逻辑
    # 暂时还是尝试 Yahoo，如果失败用户可能需要刷新
    try:
        import yfinance as yf
        ticker = yf.Ticker("CNY=X")
        data = ticker.history(period="1d", interval="1m")
        return data['Close'].iloc[-1] if not data.empty else ticker.history(period="1d")['Close'].iloc[-1]
    except: return None

# --- 初始化 Session State (用于存储数据) ---
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 页面布局 ---
st.title("⚡ USDT 溢价率实时监控终端")
st.caption("数据来源: Binance P2P & Yahoo Finance | 自动刷新: 约 5-10 秒")

# 创建占位符容器
metric_container = st.container()
chart_container = st.empty()

# --- 主循环逻辑 ---
# Streamlit 的特殊机制，为了自动刷新，我们使用 rerun
if st.button("🔄 点击开始/刷新监控"):
    st.rerun()

# 自动运行逻辑
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
        
        # 保持最近 100 个点
        if len(st.session_state.history) > 100:
            st.session_state.history.pop(0)
            
        # 转换为 DataFrame
        df = pd.DataFrame(st.session_state.history)

        # --- 2. 渲染指标卡片 ---
        with metric_container:
            # 清空旧内容
            col1, col2, col3 = st.columns(3)
            col1.metric("USDT 溢价率", f"{premium_rate:+.2f}%", delta_color="inverse")
            col2.metric("Binance USDT", f"¥{usdt_avg:.3f}")
            col3.metric("USD 汇率", f"¥{usd_cny:.4f}")

        # --- 3. 渲染交互式图表 ---
        fig = go.Figure()
        
        # 动态颜色
        color = '#00ff00' if premium_rate > 0 else '#ff3333'
        
        fig.add_trace(go.Scatter(
            x=df['time'], y=df['rate'],
            mode='lines+markers',
            line=dict(color=color, width=2),
            marker=dict(size=6),
            name='Premium',
            hovertemplate='时间: %{x}<br>溢价: %{y:.2f}%<extra></extra>'
        ))
        
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        fig.update_layout(
            height=500,
            paper_bgcolor='#0e1117',
            plot_bgcolor='#0e1117',
            xaxis=dict(showgrid=True, gridcolor='#262730', tickmode='auto', nticks=10),
            yaxis=dict(showgrid=True, gridcolor='#262730', tickformat="+.2f"),
            margin=dict(l=0, r=0, t=30, b=0),
            font=dict(color="white")
        )

        # 更新图表
        chart_container.plotly_chart(fig, use_container_width=True)
    
    else:
        st.warning(f"[{now_time}] 数据获取中，请稍候...")

    # 休息 5 秒
    time.sleep(5)
    # 注意：Streamlit Cloud 在循环中会自动更新前端，不需要手动 rerun
