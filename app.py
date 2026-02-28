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
import time
import re

# ==========================================
# 1. 网页全局配置
# ==========================================
st.set_page_config(page_title="全球学术前沿雷达", page_icon="📡", layout="wide")
st.title("📡 全球学术前沿文献雷达 (全学科海量 IF 版)")
st.markdown("内置扩容版 IF 数据库（涵盖医学专刊、综合开源大刊等）。自动抓取最新文献并生成图表。")

# ==========================================
# 2. 侧边栏
# ==========================================
with st.sidebar:
    st.header("⚙️ 检索参数设置")
    search_keyword = st.text_input("🔍 检索关键词 (支持模糊搜索)", value="glaucoma")
    start_date = st.date_input("📅 起始日期", value=pd.to_datetime("2025-01-01"))
    max_papers = st.slider("📑 最大抓取数量", min_value=50, max_value=500, value=200, step=50)
    st.markdown("---")
    st.markdown("💡 **提示**: 会议论文及预印本(如 Zenodo, OSF Preprints)本身无 IF 分数。")

def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

if contains_chinese(search_keyword):
    st.warning("👀 **检测到中文！** 建议替换为**英文关键词**以获取最精准的文献！")

# ==========================================
# 3. 史诗级全学科影响因子大字典 (超级扩容版)
# ==========================================
SUPER_IF_DICT = {
    # --- 综合 / 顶刊 ---
    "Nature": 64.8, "Science": 56.9, "Cell": 64.5, "Nature Communications": 16.6, 
    "Science Advances": 13.6, "Proceedings of the National Academy of Sciences": 11.1,
    
    # --- 生物医学顶刊 ---
    "The New England Journal of Medicine": 158.5, "The Lancet": 168.9, "JAMA": 120.7, 
    "BMJ": 105.7, "Nature Medicine": 82.9, "Nature Biotechnology": 68.1,
    "Nature Genetics": 30.8, "Immunity": 32.4, "Cancer Cell": 38.5, "Lancet Oncology": 51.1,
    
    # --- 眼科 / 视觉科学专刊 (Ophthalmology) ---
    "Ophthalmology": 13.1, "JAMA Ophthalmology": 7.8, "Progress in Retinal and Eye Research": 17.8,
    "American Journal of Ophthalmology": 4.1, "British Journal of Ophthalmology": 4.6,
    "Investigative Ophthalmology & Visual Science": 4.9, "Acta Ophthalmologica": 3.4,
    "Eye": 3.9, "Current Eye Research": 2.0, "Experimental Eye Research": 3.0,
    "International Ophthalmology": 1.4, "Translational Vision Science & Technology": 3.0,
    "Current Ophthalmology Reports": 1.2, "BMC Ophthalmology": 2.0,
    "Journal of Glaucoma": 2.0, "Clinical Ophthalmology": 1.7,
    
    # --- 极高频开源“超级大刊” (Frontiers, MDPI, BMC, PLoS) ---
    "PLoS One": 3.7, "Scientific Reports": 4.6, 
    "Frontiers in Cell and Developmental Biology": 5.3, "Frontiers in Immunology": 7.3,
    "Frontiers in Medicine": 3.9, "Frontiers in Oncology": 4.7, "Frontiers in Pharmacology": 5.6,
    "Frontiers in Neuroscience": 4.3, "Frontiers in Plant Science": 5.6,
    "International Journal of Molecular Sciences": 5.6, "Cancers": 5.2, "Cells": 6.0,
    "Sensors": 3.9, "Molecules": 4.6, "Marine Drugs": 5.4, "Nutrients": 5.9,
    "Journal of Clinical Medicine": 3.9, "Antioxidants": 7.0,
    "BMC Public Health": 4.1, "BMC Medicine": 9.3, "BMC Cancer": 3.8,
    
    # --- 计算机 / AI / 信息科学 ---
    "Nature Machine Intelligence": 25.8, "IEEE Transactions on Pattern Analysis and Machine Intelligence": 23.6,
    "International Journal of Computer Vision": 19.5, "Information Fusion": 18.6,
    "IEEE Transactions on Neural Networks and Learning Systems": 14.4, "Artificial Intelligence": 14.4,
    "Medical Image Analysis": 13.8, "IEEE Transactions on Image Processing": 10.6,
    "Expert Systems with Applications": 8.5, "Pattern Recognition": 8.0, "Knowledge-Based Systems": 8.8,
    
    # --- 化学 / 材料 / 环境 ---
    "Chemical Society Reviews": 46.2, "Advanced Materials": 29.4, "Journal of the American Chemical Society": 15.0, 
    "Energy & Environmental Science": 32.4, "Applied Catalysis B: Environment and Energy": 22.1, 
    "Chemical Engineering Journal": 15.1, "Water Research": 12.8, "Journal of Cleaner Production": 11.1, 
    "Science of The Total Environment": 9.8, "ACS Nano": 17.1, "Nano Letters": 10.8, "Small": 13.3
}
super_if_dict_lower = {k.lower(): v for k, v in SUPER_IF_DICT.items()}

# ==========================================
# 4. 核心抓取函数
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_and_process_papers(keyword, date_str, limit):
    url = "https://api.openalex.org/works"
    papers_data = []
    page = 1
    
    while len(papers_data) < limit:
        params = {
            "search": keyword,
            "filter": f"from_publication_date:{date_str}",
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
        # 部分包含匹配逻辑：应对带有后缀的期刊名
        def match_if(journal_name):
            j_lower = str(journal_name).lower()
            # 1. 尝试完全匹配
            if j_lower in super_if_dict_lower:
                return super_if_dict_lower[j_lower]
            # 2. 尝试子串匹配 (针对名字带小尾巴的情况)
            for key, val in super_if_dict_lower.items():
                if key in j_lower:
                    return val
            return None
            
        df['IF'] = df['期刊名'].apply(match_if)
    return df

# ==========================================
# 5. 主程序渲染
# ==========================================
if st.sidebar.button("🚀 开始检索并生成图表", type="primary", use_container_width=True):
    
    with st.spinner(f"正在跨库模糊检索关于 '{search_keyword}' 的文献..."):
        df = fetch_and_process_papers(search_keyword, start_date.strftime("%Y-%m-%d"), max_papers)
    
    if df.empty:
        st.error("没有找到符合条件的文献。")
    else:
        st.success(f"🎉 抓取成功！共获取 {len(df)} 篇文献。")
        
        df_with_if = df.dropna(subset=['IF']).copy()
        match_rate = len(df_with_if) / len(df) * 100 if len(df) > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("抓取总文献数", f"{len(df)} 篇")
        col2.metric("成功匹配 IF 数量", f"{len(df_with_if)} 篇")
        col3.metric("IF 匹配率", f"{match_rate:.1f}%")

        if not df_with_if.empty:
            st.subheader("📊 细分领域影响因子分布")
            
            fig = go.Figure()
            unique_fields = df_with_if['领域聚类'].unique()
            
            for field in unique_fields:
                df_sub = df_with_if[df_with_if['领域聚类'] == field]
                hover_text = (
                    "<b>影响因子:</b> " + df_sub['IF'].astype(str) + "<br>" +
                    "<b>标题:</b> " + df_sub['标题'].str[:80] + "...<br>" +
                    "<b>期刊:</b> " + df_sub['期刊名'] + "<br>" +
                    "<b>DOI:</b> " + df_sub['DOI']
                )
                
                fig.add_trace(go.Box(
                    y=df_sub['IF'], x=df_sub['领域聚类'], name=field,
                    boxpoints='all', jitter=0.5, whiskerwidth=0.2, marker_size=5,
                    text=hover_text, hoverinfo='text'
                ))
                
            fig.update_layout(
                xaxis_tickangle=-35, showlegend=False, height=600,
                plot_bgcolor='rgba(245,245,245,1)', yaxis_title="影响因子 (IF)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ 未能匹配到影响因子。您可以查阅下方完整列表。")

        st.subheader("📋 详细文献数据")
        df_display = df.copy()
        df_display['IF'] = df_display['IF'].fillna("未匹配/会议/预印本")
        st.dataframe(df_display[['发表日期', '领域聚类', 'IF', '期刊名', '标题', 'DOI']], use_container_width=True, hide_index=True)