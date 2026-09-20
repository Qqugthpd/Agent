import streamlit as st
import os
import tempfile
from dotenv import load_dotenv

# 导入你写好的智能体核心代码
# 需要确保 agent_full.py 里的 run_agent 函数可以被导入
from agent_full import run_agent, tools, TOOL_FUNCTIONS
from pdf_parser import extract_text_from_pdf
from trace_logger import TraceLogger

load_dotenv()

st.set_page_config(page_title="金融AI智能体 - 年报分析", layout="wide")

st.title("📊 上市公司财务报告智能分析")
st.markdown("上传一份上市公司年度报告 PDF，智能体将自动提取数据、计算同比、识别非经常性损益并生成分析报告。")

# 侧边栏：上传文件
with st.sidebar:
    st.header("操作面板")
    uploaded_file = st.file_uploader("选择年报 PDF 文件", type=["pdf"])
    
    if uploaded_file is not None:
        st.success(f"已上传: {uploaded_file.name}")

if uploaded_file is not None:
    # 把上传的文件保存到临时目录
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_pdf_path = tmp_file.name
    
    logger = TraceLogger(output_path="trace_web.jsonl")
    logger.log_file_access(tmp_pdf_path)
    
    # 解析 PDF（提取前15页）
    with st.spinner("正在解析 PDF 文本..."):
        raw_text = extract_text_from_pdf(tmp_pdf_path, max_pages=15)
    
    # 定位核心财务数据
    target_keyword = "主要会计数据"
    if target_keyword in raw_text:
        start_idx = raw_text.find(target_keyword)
        financial_text = raw_text[start_idx : start_idx + 4500]
    else:
        financial_text = raw_text[:4500]
    
    query = f"""
    请分析以下上市公司财务报告的核心财务数据片段，完成以下任务：
    1. 从中提取营业收入、净利润、经营现金流（注意单位是千元）
    2. 计算同比增速（如果文本中包含上期数据）
    3. 识别非经常性损益项目
    4. 检测净利润与经营现金流是否存在背离
    5. 输出结构化的分析报告（Markdown格式）

    财务报告原文：
    {financial_text}
    """
    
    st.info("智能体正在分析中，这可能需要 30 秒左右...")
    
    # 调用核心智能体（需要传入 tools 列表）
    # 注意：run_agent 内部需要用到 tools 和 TOOL_FUNCTIONS
    # 建议把 agent_full.py 里的 tools 和 TOOL_FUNCTIONS 也一并导入
    from agent_full import tools, TOOL_FUNCTIONS
    
    with st.spinner("智能体正在进行多步推理和工具调用..."):
        result = run_agent(query, tools=tools, tool_functions=TOOL_FUNCTIONS)
    
    st.success("分析完成！")
    
    # 展示最终报告
    st.markdown("### 📝 最终分析报告")
    st.markdown(result["final_answer"])
    
    # 提供日志下载
    with open("trace_web.jsonl", "rb") as f:
        st.download_button(
            label="📥 下载执行日志 (trace.jsonl)",
            data=f,
            file_name="trace.jsonl",
            mime="application/json"
        )