import streamlit as st
import os
import tempfile
import json
import re
from pathlib import Path
from dotenv import load_dotenv

from agent_full import run_agent, tools, TOOL_FUNCTIONS
from pdf_parser import extract_text_from_file
from trace_logger import TraceLogger

load_dotenv()

# ================= 1. 页面基础配置 =================
st.set_page_config(
    page_title="金融AI智能体 - 年报分析",
    page_icon="📊",
    layout="wide"
)

# ================= 2. 全局样式 =================
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    /* 专属主标题样式 */
    .main-title {
        font-size: 38px !important;
        font-weight: 700 !important;
        color: #1E293B !important;
        margin-top: 10px !important;
        margin-bottom: 20px !important;
        letter-spacing: -0.5px !important;
        display: block !important;
    }

    /* 专属限制：AI 生成的报告里的标题 */
    div[data-testid="stMarkdownContainer"] h1,
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3 {
        font-size: 18px !important;
        font-weight: 600 !important;
        margin-top: 12px !important;
        margin-bottom: 8px !important;
        line-height: 1.4 !important;
        color: #1E293B !important;
    }

    /* 主按钮样式 */
    .stButton>button {
        background-color: #2563EB;
        color: #FFFFFF;
        border-radius: 6px;
        border: none;
        font-weight: 500;
        padding: 8px 24px;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }

    /* 标签页 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 16px;
        background-color: #F8FAFC;
        color: #64748B;
        border: 1px solid #E2E8F0;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #2563EB !important;
        border: 1px solid #2563EB;
    }

    /* 自定义上传区域放大 */
    section[data-testid="stFileUploader"] {
        padding: 20px;
        background-color: #F8FAFC;
        border: 1px dashed #CBD5E1;
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    
    /* 顶部特性标签样式 */
    .feature-tag {
        text-align: center; 
        background-color: #EFF6FF; 
        color: #1D4ED8; 
        padding: 12px 0; 
        border-radius: 8px; 
        border: 1px solid #BFDBFE; 
        font-weight: 600; 
        font-size: 18px;
    }
</style>
""", unsafe_allow_html=True)

# ================= 3. 自定义页眉 =================
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 20px;">
    <div style="font-size: 18px; font-weight: 700; color: #1E293B; letter-spacing: -0.5px;">AI Agent</div>
    <div style="font-size: 14px; color: #64748B;">智能财报分析工作台 v1.0</div>
</div>
""", unsafe_allow_html=True)

# ================= 4. 页面主标题与核心特性标签 =================
st.markdown('<div class="main-title">📊 上市公司财务报告智能分析</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<div class="feature-tag">多格式解析</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="feature-tag">多步推理</div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="feature-tag">可追溯日志</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ================= 5. 上传区域（加大尺寸） =================
upload_col1, upload_col2, upload_col3 = st.columns([1, 4, 1])

with upload_col2:
    uploaded_file = st.file_uploader(
        "📂 请上传财报文件（支持 PDF / Word / Excel / TXT / CSV / HTML）",
        type=["pdf", "docx", "txt", "csv", "xlsx", "xls", "html", "htm"],
        label_visibility="visible"
    )
    
    if uploaded_file is not None:
        st.success(f"已上传：{uploaded_file.name}")
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            st.info("📊 正在使用 Excel 解析引擎...")
        elif uploaded_file.name.endswith('.docx'):
            st.info("📝 正在使用 Word 解析引擎...")
        elif uploaded_file.name.endswith('.pdf'):
            st.info("📄 正在使用 PDF 解析引擎...")

st.markdown("---")

# ================= 6. 主区域逻辑 =================
if uploaded_file is not None:
    file_suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name

    logger = TraceLogger(output_path="trace_web.jsonl")
    logger.log_file_access(tmp_file_path)

    with st.spinner(f"正在解析 {file_suffix} 文件..."):
        raw_text = extract_text_from_file(tmp_file_path)

    target_keyword = "主要会计数据"
    if target_keyword in raw_text:
        start_idx = raw_text.find(target_keyword)
        financial_text = raw_text[start_idx : start_idx + 4500]
    else:
        financial_text = raw_text[:4500]

    query = f"""
    请分析以下上市公司财务报告片段，完成以下任务：
    1. 从中提取营业收入、净利润、经营现金流（注意单位是千元）
    2. 计算同比增速（如果文本中包含上期数据）
    3. 识别非经常性损益项目
    4. 检测净利润与经营现金流是否存在背离
    5. 输出结构化的分析报告（Markdown格式）

    财务报告原文：
    {financial_text}
    """

    st.info("🤖 智能体正在分析中，这可能需要 30 秒左右...")

    with st.spinner("正在进行多步推理和工具调用..."):
        result = run_agent(query, tools=tools, tool_functions=TOOL_FUNCTIONS)

    if "final_answer" in result:
        st.success("分析完成！")
        report_text = result["final_answer"]

        def extract_metric(keyword):
            pattern = rf"{keyword}.*?([\d,]+\.\d+|\d+)"
            match = re.search(pattern, report_text)
            if match:
                return match.group(1)
            return "--"

        st.markdown("### 📊 核心财务指标")
        
        # 使用自定义 HTML 卡片渲染指标，确保字号完全受控
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">营业收入</div>
                <div style="font-size: 36px; font-weight: 700; color: #1E293B;">{extract_metric("营业收入")}</div>
                <div style="font-size: 14px; color: #16A34A; background-color: #DCFCE7; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 10px;">↑ 同比详见报告</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">归母净利润</div>
                <div style="font-size: 36px; font-weight: 700; color: #1E293B;">{extract_metric("净利润")}</div>
                <div style="font-size: 14px; color: #16A34A; background-color: #DCFCE7; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 10px;">↑ 同比详见报告</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">经营现金流</div>
                <div style="font-size: 36px; font-weight: 700; color: #1E293B;">{extract_metric("经营现金流")}</div>
                <div style="font-size: 14px; color: #16A34A; background-color: #DCFCE7; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 10px;">↑ 同比详见报告</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        st.markdown("### 📝 智能体分析报告")
        parts = report_text.split("## ")
        parts = [p.strip() for p in parts if p.strip()]

        tabs = st.tabs(["📋 报告总览", "📈 同比分析", "🔍 非经常性损益", "⚠️ 现金流风险"])

        with tabs[0]:
            st.markdown("## " + parts[0] if len(parts) > 0 else report_text)
        with tabs[1]:
            st.markdown("## " + parts[1] if len(parts) > 1 else "暂无数据")
        with tabs[2]:
            st.markdown("## " + parts[2] if len(parts) > 2 else "暂无数据")
        with tabs[3]:
            st.markdown("## " + parts[3] if len(parts) > 3 else "暂无数据")

        st.markdown("---")

        if "trace" in result:
            trace_json_str = "\n".join([json.dumps(entry, ensure_ascii=False) for entry in result["trace"]])
            st.download_button(
                label="📥 下载执行日志 (trace.jsonl)",
                data=trace_json_str.encode('utf-8'),
                file_name="trace.jsonl",
                mime="application/json"
            )

    else:
        st.error("分析未能完成，请检查 API Key 或稍后重试。")

else:
    st.markdown("### 📊 核心财务指标")
    # 同样使用自定义 HTML 卡片渲染占位卡
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">营业收入</div>
            <div style="font-size: 36px; font-weight: 700; color: #1E293B;">--</div>
            <div style="font-size: 14px; color: #16A34A; background-color: #DCFCE7; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 10px;">↑ 等待分析</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">归母净利润</div>
            <div style="font-size: 36px; font-weight: 700; color: #1E293B;">--</div>
            <div style="font-size: 14px; color: #16A34A; background-color: #DCFCE7; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 10px;">↑ 等待分析</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">经营现金流</div>
            <div style="font-size: 36px; font-weight: 700; color: #1E293B;">--</div>
            <div style="font-size: 14px; color: #16A34A; background-color: #DCFCE7; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 10px;">↑ 等待分析</div>
        </div>
        """, unsafe_allow_html=True)

# ================= 7. 自定义页脚 =================
st.markdown("""
<div style="text-align: center; margin-top: 60px; padding-top: 20px; border-top: 1px solid #E2E8F0; color: #94A3B8; font-size: 12px;">
    <p>© 2026 上市公司财务报告智能分析 | 基于 DeepSeek 大模型构建</p>
    <p>本系统仅供学术研究与比赛演示使用，不构成任何投资建议。</p>
</div>
""", unsafe_allow_html=True)
