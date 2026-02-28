# ==========================================
# 0. 上帝模式补丁：拯救 Python 3.14 的全局依赖
# ==========================================
import sys
import builtins
builtins.sys = sys 

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import re
import datetime

# ==========================================
# 1. 网页全局配置 & Session State 初始化
# ==========================================
st.set_page_config(page_title="全球学术前沿雷达", page_icon="📡", layout="wide")
st.title("📡 全球学术前沿文献雷达 (双轴可视化版)")
st.markdown("支持**跨语言模糊检索**与**多维度数据洞察**。左轴看质量 (IF)，右轴看热度 (发文量)。")

# 初始化搜索框的默认值
if 'search_input' not in st.session_state:
    st.session_state.search_input = "photocatalysis VOCs"

# 初始化搜索历史记录 (预设几个实用方向)
if 'search_history' not in st.session_state:
    st.session_state.search_history = ["machine learning catalyst", "photocatalysis VOCs", "glaucoma"]

# 点击历史记录按钮的回调函数
def set_search_term(term):
    st.session_state.search_input = term

# ==========================================
# 2. 侧边栏：高级交互面板
# ==========================================
with st.sidebar:
    st.header("🕒 搜索历史 (点击快捷检索)")
    
    # 将历史记录变成两列并排的小按钮，更加美观
    history_cols = st.columns(2)
    for i, term in enumerate(reversed(st.session_state.search_history[-6:])): # 最多显示最近 6 条
        history_cols[i % 2].button(
            f"🔍 {term[:12]}..." if len(term)>12 else f"🔍 {term}", 
            key=f"hist_{i}", 
            help=term,
            on_click=set_search_term, 
            args=(term,)
        )
        
    st.markdown("---")
    st.header("⚙️ 检索参数设置")
    
    # 搜索框绑定 session_state
    search_keyword = st.text_input("🔍 检索关键词", key="search_input")
    
    # 核心升级 1：从单一日期变为日期范围选择
    today = datetime.date.today()
    last_year = today.replace(year=today.year - 1)
    date_range = st.date_input("📅 发表日期范围", value=(last_year, today), max_value=today)
    
    # 处理用户只点了一个日期还没选结束日期的情况
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = date_range[0], today

    max_papers = st.slider("📑 最大抓取数量", min_value=50, max_value=500, value=200, step=50)

# ==========================================
# 3. 史诗级全学科影响因子大字典 
# ==========================================
SUPER_IF_DICT = {
    # 综合 / 顶刊
    "Nature": 64.8, "Science": 56.9, "Cell": 64.5, "Nature Communications": 16.6, "Science Advances": 13.6,
    "The New England Journal of Medicine": 158.5, "The Lancet": 168.9, "JAMA": 120.7, "BMJ": 105.7, 
    "Nature Medicine": 82.9, "Nature Biotechnology": 68.1,
    # 医学专刊与开源大刊
    "Ophthalmology": 13.1, "JAMA Ophthalmology": 7.8, "Investigative Ophthalmology & Visual Science": 4.9,
    "PLoS One": 3.7, "Scientific Reports": 4.6, "Frontiers in Cell and Developmental Biology": 5.3, 
    "Frontiers in Immunology": 7.3, "International Journal of Molecular Sciences": 5.6, "Molecules": 4.6,
    # AI 与 计算机
    "Nature Machine Intelligence": 25.8, "IEEE Transactions on Pattern Analysis and Machine Intelligence": 23.6,
    "Expert Systems with Applications": 8.5, "Knowledge-Based Systems": 8.8,
    # 化学 / 材料 / 环境
    "Chemical Society Reviews": 46.2, "Advanced Materials": 29.4, "Journal of the American Chemical Society": 15.0, 
    "Energy & Environmental Science": 32.4, "Applied Catalysis B: Environment and Energy": 22.1, 
    "Chemical Engineering Journal": 15.1, "Water Research": 12.8, "Journal of Cleaner Production": 11.1, 
    "Science of The Total Environment": 9.8, "ACS Nano": 17.1, "Nano Letters": 10.8, "Small": 13.3
}
super_if_dict_lower = {k.lower(): v for k, v in SUPER_IF_DICT.items()}

# ==========================================
# 4. 核心抓取函数 (支持日期范围)
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_and_process_papers(keyword, start_str, end_str, limit):
    url = "https://api.openalex.org/works"
    papers_data = []
    page = 1
    
    while len(papers_data) < limit:
        # 增加 to_publication_date 实现范围筛选
        params = {
            "search": keyword,
            "filter": f"from_publication_date:{start_str},to_publication_date:{end_str}",
            "sort": "publication_date:desc",
            "per-page": 100,
            "page": page
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200: break
        except Exception:
            break
            
        data = response.json()
        results = data.get("results", [])
        if not results: break
            
        for item in results:
            source = item.get("primary_location", {}).get("source")
            journal = source.get("display_name", "Unknown") if source else "Unknown"
            
            concepts = item.get("concepts", [])
            sub_field = "Others"
            for c in concepts:
                if c.get("level", 0) > 0: 
                    sub_field = c.get("display_name", "Others")
                    break
            
            papers_data.append({
                "发表日期": item.get("publication_date", ""),
                "标题": item.get("title", "No Title"),
                "期刊名": journal,
                "领域聚类": sub_field,
                "DOI": item.get("doi", "")
            })
            if len(papers_data) >= limit: break
            page += 1
            time.sleep(0.1) 
        
    df = pd.DataFrame(papers_data)
    if not df.empty:
        def match_if(journal_name):
            j_lower = str(journal_name).lower()
            if j_lower in super_if_dict_lower: return super_if_dict_lower[j_lower]
            for key, val in super_if_dict_lower.items():
                if key in j_lower: return val
            return None
        df['IF'] = df['期刊名'].apply(match_if)
    return df

# ==========================================
# 5. 主程序渲染
# ==========================================
if st.sidebar.button("🚀 开始深度检索", type="primary", use_container_width=True):
    
    # 将最新搜索词加入历史记录
    if search_keyword and search_keyword not in st.session_state.search_history:
        st.session_state.search_history.append(search_keyword)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    with st.spinner(f"正在分析 {start_str} 至 {end_str} 期间关于 '{search_keyword}' 的数据..."):
        df = fetch_and_process_papers(search_keyword, start_str, end_str, max_papers)
    
    if df.empty:
        st.error("没有找到符合条件的文献，请尝试放宽日期范围或更换关键词。")
    else:
        st.success(f"🎉 抓取成功！共获取 {len(df)} 篇文献。")
        
        df_with_if = df.dropna(subset=['IF']).copy()
        match_rate = len(df_with_if) / len(df) * 100 if len(df) > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("抓取总文献数", f"{len(df)} 篇")
        col2.metric("成功匹配 IF 数量", f"{len(df_with_if)} 篇")
        col3.metric("IF 匹配率", f"{match_rate:.1f}%")

        if not df_with_if.empty:
            st.subheader("📊 领域热度与质量双轴图")
            
            # 计算每个领域的发文量，并按发文量降序排序
            count_df = df_with_if['领域聚类'].value_counts().reset_index()
            count_df.columns = ['领域聚类', '发文量']
            
            # 核心升级 2：创建双 Y 轴图表
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # 轨迹 1：右 Y 轴柱状图 (热度：发文量)
            fig.add_trace(
                go.Bar(
                    x=count_df['领域聚类'], 
                    y=count_df['发文量'], 
                    name="发文数量 (右轴)",
                    marker_color='rgba(135, 206, 250, 0.4)', # 浅蓝色半透明柱子
                    hovertemplate="<b>领域</b>: %{x}<br><b>发文量</b>: %{y} 篇<extra></extra>"
                ),
                secondary_y=True,
            )
            
            # 轨迹 2：左 Y 轴散点图 (质量：影响因子)
            for field in count_df['领域聚类']:
                df_sub = df_with_if[df_with_if['领域聚类'] == field]
                hover_text = (
                    "<b>影响因子:</b> " + df_sub['IF'].astype(str) + "<br>" +
                    "<b>标题:</b> " + df_sub['标题'].str[:80] + "...<br>" +
                    "<b>期刊:</b> " + df_sub['期刊名'] + "<br>" +
                    "<b>DOI:</b> " + df_sub['DOI']
                )
                
                # 使用透明的 Box 实现带抖动的 Scatter 效果
                fig.add_trace(
                    go.Box(
                        y=df_sub['IF'], x=df_sub['领域聚类'], name="影响因子 (左轴)",
                        boxpoints='all', jitter=0.5, pointpos=0, # 将点居中抖动
                        fillcolor='rgba(0,0,0,0)', line=dict(color='rgba(0,0,0,0)'), # 隐藏箱子
                        marker=dict(size=7, color='#ff7f0e', opacity=0.8, line=dict(width=1, color='white')),
                        text=hover_text, hoverinfo='text', showlegend=False
                    ),
                    secondary_y=False,
                )
                
            fig.update_layout(
                xaxis_tickangle=-35, 
                height=650,
                plot_bgcolor='rgba(250,250,250,1)',
                hovermode="closest",
                barmode='overlay', # 允许散点悬浮在柱子上
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            # 设置双 Y 轴标签
            fig.update_yaxes(title_text="<b>影响因子 (IF)</b> [橙色散点]", secondary_y=False, gridcolor='rgba(200,200,200,0.3)')
            fig.update_yaxes(title_text="<b>发文数量 (篇)</b> [蓝色柱状图]", secondary_y=True, showgrid=False)
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ 未能匹配到影响因子。您可以查阅下方完整列表。")

        st.subheader("📋 详细文献数据")
        df_display = df.copy()
        df_display['IF'] = df_display['IF'].fillna("未匹配")
        st.dataframe(df_display[['发表日期', '领域聚类', 'IF', '期刊名', '标题', 'DOI']], use_container_width=True, hide_index=True)