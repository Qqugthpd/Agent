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

    .main-title {
        font-size: 38px !important;
        font-weight: 700 !important;
        color: #1E293B !important;
        margin-top: 10px !important;
        margin-bottom: 20px !important;
        letter-spacing: -0.5px !important;
        display: block !important;
    }

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

    section[data-testid="stFileUploader"] {
        padding: 20px;
        background-color: #F8FAFC;
        border: 1px dashed #CBD5E1;
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }

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

# ================= 4. 主标题与特性标签 =================
st.markdown('<div class="main-title">📊 上市公司财务报告智能分析</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<div class="feature-tag">📂 多格式解析</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="feature-tag">🤖 多步推理</div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="feature-tag">🔍 可追溯日志</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ================= 5. 上传区域 =================
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
            st.info("📄 正在使用 PDF 解析引擎（图片型 PDF 会自动启动 OCR，可能较慢）...")

st.markdown("---")

# ================= 6. 主区域逻辑 =================
if uploaded_file is not None:
    file_suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name

    logger = TraceLogger(output_path="trace_web.jsonl")
    logger.log_file_access(tmp_file_path)

    with st.spinner(f"正在解析 {file_suffix} 文件（图片型 PDF 会自动启动 OCR，可能需要3-5分钟）..."):
        raw_text = extract_text_from_file(tmp_file_path)

    # 文本清洗
    raw_text = re.sub(r'\n+', '\n', raw_text)
    raw_text = re.sub(r' +', ' ', raw_text)

    # 创建扁平化副本用于关键词查找
    flat_text = re.sub(r'\s+', '', raw_text)

    # 关键词列表（简繁双覆盖 + 各类财报命名）
    possible_keywords = [
        "主要会计数据",
        "财务摘要", "財務摘要",
        "综合收益表", "綜合收益表",
        "合并利润表", "合併利潤表",
        "利润表", "利潤表",
        "综合财务状况表", "綜合財務狀況表",
        "合并资产负债表", "合併資產負債表",
        "资产负债表", "資產負債表",
        "综合现金流量表", "綜合現金流量表",
        "合并现金流量表", "合併現金流量表",
        "现金流量表", "現金流量表",
        "现金流量分析",
        "经营活动产生的现金流量",
        "财务报表附注", "財務報表附註",
        "合并财务报表", "合併財務報表",
        "财务报表", "財務報表",
    ]

    MAX_CHARS = 30000
    financial_text = ""
    found_keyword = None

    for keyword in possible_keywords:
        flat_keyword = re.sub(r'\s+', '', keyword)
        if flat_keyword in flat_text:
            flat_idx = flat_text.find(flat_keyword)
            count = 0
            orig_idx = 0
            for i, ch in enumerate(raw_text):
                if not ch.isspace():
                    if count == flat_idx:
                        orig_idx = i
                        break
                    count += 1

            financial_text = raw_text[orig_idx: orig_idx + MAX_CHARS]
            found_keyword = keyword
            st.info(f"✅ 已定位到 '{keyword}' 章节，提取前 {len(financial_text)} 个字符进行分析。")
            break

    if not found_keyword:
        financial_text = raw_text[:MAX_CHARS]
        st.warning(f"⚠️ 未识别到标准财报章节，已自动截取前 {MAX_CHARS} 个字符进行分析。")

    query = f"""
请分析以下上市公司财务报告片段，完成以下任务：

1. 从中提取营业收入、净利润、经营现金流（如果原文中存在）
2. 计算同比增速（如果原文中包含上期数据）
3. 识别非经常性损益项目（如果原文中有列示）
4. 检测净利润与经营现金流是否存在背离
5. 输出结构化的 Markdown 分析报告

⚠️ 重要要求：
- 最终输出必须是一份干净的报告，严禁出现"第X步"、"让我确认"、"我需要"等推理过程性语言。
- 报告结构固定为：## 一、核心财务数据提取；## 二、同比增速计算；## 三、非经常性损益识别；## 四、净利润与经营现金流背离检测；## 五、综合分析结论。
- 如果某项数据（如经营现金流）在原文片段中确实缺失，请在对应位置明确写"该数据未在本次提取的文本中披露"，不要编造数字，也不要强行计算。
- 金额单位统一注明（千元/百万元）。
- 请在"## 一、核心财务数据提取"里用标准化的字段名列出数据，例如：
  **营业收入：XXX（百万元）**
  **净利润：XXX（百万元）**
  **经营现金流：XXX（百万元）**

财务报告原文：
{financial_text}
"""

    st.info("🤖 智能体正在分析中，这可能需要 30 秒左右...")

    with st.spinner("正在进行多步推理和工具调用..."):
        result = run_agent(query, tools=tools, tool_functions=TOOL_FUNCTIONS)

    if "final_answer" in result:
        st.success("分析完成！")
        report_text = result["final_answer"]

        # ============ 优化后的指标提取（两层：报告优先，原文兜底） ============
        def extract_metric(keyword, source_texts):
            """
            从多个来源（智能体报告 + 原始财报文本）提取指标。
            source_texts 是个列表，按优先级排列。
            """
            # 每种指标对应的正则模式列表（从精确到宽泛）
            if "现金流" in keyword:
                patterns = [
                    r"经营活动产生的现金流量净额[^\d\-]*?([\d,]+\.?\d*)",
                    r"经营活动所得现金[^\d\-]*?([\d,]+\.?\d*)",
                    r"经营活动现金流量净额[^\d\-]*?([\d,]+\.?\d*)",
                    r"经营现金流[^\d\-]*?([\d,]+\.?\d*)",
                ]
            elif "营业收入" in keyword:
                patterns = [
                    r"\*{0,2}营业收入\*{0,2}[：:]\s*([\d,]+\.?\d*)",
                    r"营业收入[^\d\-]*?([\d,]+\.?\d*)",
                    r"营业总收入[^\d\-]*?([\d,]+\.?\d*)",
                    r"\*{0,2}总收入\*{0,2}[：:]\s*([\d,]+\.?\d*)",
                    r"(?:^|\n)\s*收入[^\d\-]*?([\d,]+\.?\d*)",
                ]
            elif "净利润" in keyword:
                patterns = [
                    r"归属于?母公司?股?东?的?净利润[^\d\-]*?([\d,]+\.?\d*)",
                    r"归母净利润[^\d\-]*?([\d,]+\.?\d*)",
                    r"归属于?普通股股?东?的?净利润[^\d\-]*?([\d,]+\.?\d*)",
                    r"\*{0,2}净利润\*{0,2}[：:]\s*([\d,]+\.?\d*)",
                    r"净利润[^\d\-]*?([\d,]+\.?\d*)",
                    r"年度盈利[^\d\-]*?([\d,]+\.?\d*)",
                ]
            else:
                patterns = [rf"{keyword}[^\d\-]*?([\d,]+\.?\d*)"]

            # 遍历所有来源文本，依次尝试所有模式
            for source in source_texts:
                if not source:
                    continue
                for pattern in patterns:
                    for match in re.finditer(pattern, source):
                        val = match.group(1).strip().rstrip(".").rstrip(",")
                        try:
                            num = float(val.replace(",", ""))
                            # 跳过年份
                            if 2020 <= num <= 2030 and "," not in val and "." not in val:
                                continue
                            # 跳过太小的值（可能是附注编号）
                            if num < 100:
                                continue
                            return val
                        except ValueError:
                            continue
            return "--"

        # 优先从智能体报告提取，报告提取不到就从原始财报文本提取
        source_texts = [report_text, financial_text]

        st.markdown("### 📊 核心财务指标")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">营业收入</div>
                <div style="font-size: 36px; font-weight: 700; color: #1E293B;">{extract_metric("营业收入", source_texts)}</div>
                <div style="font-size: 14px; color: #16A34A; background-color: #DCFCE7; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 10px;">↑ 同比详见报告</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">归母净利润</div>
                <div style="font-size: 36px; font-weight: 700; color: #1E293B;">{extract_metric("净利润", source_texts)}</div>
                <div style="font-size: 14px; color: #16A34A; background-color: #DCFCE7; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-top: 10px;">↑ 同比详见报告</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-size: 18px; font-weight: 600; color: #475569; margin-bottom: 8px;">经营现金流</div>
                <div style="font-size: 36px; font-weight: 700; color: #1E293B;">{extract_metric("现金流", source_texts)}</div>
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
