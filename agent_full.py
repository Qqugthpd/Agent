import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# ============ 1. 定义工具函数 ============

def calculate_yoy(current, previous):
    # 智能清洗：如果是字符串，去掉逗号和空格
    try:
        if isinstance(current, str):
            current = float(current.replace(",", "").replace(" ", ""))
        if isinstance(previous, str):
            previous = float(previous.replace(",", "").replace(" ", ""))
    except ValueError:
        return {"error": "无法解析数字，请检查输入是否为纯数字"}
    
    if previous == 0:
        return {"error": "基期值为零，无法计算同比"}
    yoy = ((current - previous) / abs(previous)) * 100
    return {
        "yoy_percent": round(yoy, 2),
        "current": current,
        "previous": previous,
        "formula": f"({current} - {previous}) / |{previous}| * 100"
    }

def identify_non_recurring(items):
    """识别非经常性损益项目"""
    NON_RECURRING_KEYWORDS = [
        "非流动资产处置损益", "政府补助", "债务重组损益",
        "企业取得子公司投资成本小于取得投资时应享有被投资单位可辨认净资产公允价值产生的收益",
        "除上述各项之外的其他营业外收入和支出",
        "单独进行减值测试的应收款项减值准备转回",
        "持有交易性金融资产产生的公允价值变动损益",
    ]
    non_recurring = []
    uncertain = []
    for item in items:
        project = item.get("project", "")
        if any(kw in project for kw in NON_RECURRING_KEYWORDS):
            non_recurring.append(item)
        else:
            uncertain.append(item)
    return {
        "non_recurring": non_recurring,
        "uncertain": uncertain,
        "total_non_recurring": sum(i.get("amount", 0) for i in non_recurring)
    }

def check_cashflow_divergence(net_profit, operating_cashflow, threshold=0.3):
    if net_profit == 0:
        return {"flag": False, "reason": "净利润为零，无法计算"}
    if operating_cashflow < 0:
         return {"flag": True, "divergence_ratio": 1.0, "reason": f"净利润为正({net_profit})，但经营现金流为负({operating_cashflow})，存在严重纸面利润风险", "net_profit": net_profit, "operating_cashflow": operating_cashflow}
    divergence = abs(net_profit - operating_cashflow) / abs(net_profit)
    if divergence > threshold and net_profit > operating_cashflow:
        return {"flag": True, "divergence_ratio": round(divergence, 2), "reason": f"净利润高于经营现金流，差异达{divergence:.1%}，需核查", "net_profit": net_profit, "operating_cashflow": operating_cashflow}
    return {"flag": False, "divergence_ratio": round(divergence, 2), "reason": "利润与现金流匹配良好，盈利质量较高"}

# ============ 2. 工具定义（告诉模型有哪些工具） ============

tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate_yoy",
            "description": "计算同比增长率。输入本期值和上期值，返回百分比。",
            "parameters": {
                "type": "object",
                "properties": {
                    "current": {"type": "number", "description": "本期数值"},
                    "previous": {"type": "number", "description": "上期数值"}
                },
                "required": ["current", "previous"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "identify_non_recurring",
            "description": "识别非经常性损益项目。输入利润表项目列表，返回分类结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "project": {"type": "string"},
                                "amount": {"type": "number"}
                            }
                        },
                        "description": "利润表项目列表"
                    }
                },
                "required": ["items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_cashflow_divergence",
            "description": "检测净利润与经营现金流是否背离。",
            "parameters": {
                "type": "object",
                "properties": {
                    "net_profit": {"type": "number"},
                    "operating_cashflow": {"type": "number"}
                },
                "required": ["net_profit", "operating_cashflow"]
            }
        }
    }
]


TOOL_FUNCTIONS = {
    "calculate_yoy": calculate_yoy,
    "identify_non_recurring": identify_non_recurring,
    "check_cashflow_divergence": check_cashflow_divergence,
}



# ============ 3. ReAct 循环 ============
# 工具映射表（把函数名和实际函数对应起来，必须放在 run_agent 之前）
def run_agent(user_query, tools, tool_functions, max_steps=10):
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个上市公司财务报告分析智能体。"
                "你可以调用工具完成数据计算和异常检测。"
                "请逐步推理，每次只调用一个工具，观察结果后再决定下一步。"
                "最终输出必须包含数据来源和计算过程。"
            )
        },
        {"role": "user", "content": user_query}
    ]
    
    trace_log = []
    
    for step in range(max_steps):
        print(f"\n--- Step {step + 1} ---")
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            temperature=0.1 # 低温度，保证结果稳定
        )
        
        message = response.choices[0].message
        messages.append(message)
        
        trace_log.append({
            "step": step + 1,
            "tool_calls": [
                {"name": tc.function.name, "arguments": tc.function.arguments}
                for tc in (message.tool_calls or [])
            ]
        })
        
        # 如果没有工具调用，说明模型给出了最终回答
        if not message.tool_calls:
            print("模型最终输出：", message.content)
            return {"final_answer": message.content, "trace": trace_log}
        
        # 执行模型要求的工具
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            
            print(f"调用工具：{func_name}({func_args})")
            
            if func_name in tool_functions:
                try:
                    result = TOOL_FUNCTIONS[func_name](**func_args)
                except Exception as e:
                    result = {"error": str(e)}
            else:
                result = {"error": f"未知工具：{func_name}"}
            
            print(f"结果：{result}")
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })
    
    return {"final_answer": "达到最大步数", "trace": trace_log}

# ============ 4. 运行 ============

if __name__ == "__main__":
    from pdf_parser import extract_text_from_pdf
    from trace_logger import TraceLogger
    
    logger = TraceLogger()
    pdf_path = "data/annual_report.pdf"
    
    # 1. 记录文件访问（比赛要求可追溯）
    logger.log_file_access(pdf_path)
    
    # 2. 解析 PDF 的前 15 页
    raw_text = extract_text_from_pdf(pdf_path, max_pages=15)
    
    # 3. 精准定位“主要会计数据”章节
    target_keyword = "主要会计数据"
    if target_keyword in raw_text:
        start_idx = raw_text.find(target_keyword)
        # 截取 4500 个字符，覆盖主要财务指标表和非经常性损益表
        financial_text = raw_text[start_idx : start_idx + 4500]
    else:
        financial_text = raw_text[:4500]

    # 4. 构建给智能体的真实任务指令
    query = f"""
    请分析以下宁德时代2025年年度报告的核心财务数据片段，完成以下任务：
    1. 从中提取营业收入、净利润、经营现金流（注意单位是千元，如“423,701,834”）
    2. 计算营收、净利润、经营现金流的同比增速（如果文本中包含2024年数据）
    3. 识别非经常性损益项目（文本中有非经常性损益项目及金额表格）
    4. 检测净利润与经营现金流是否存在背离
    5. 输出结构化的分析报告（Markdown格式）

    财务报告原文：
    {financial_text}
    """
    
    result = run_agent(query)
    print("\n" + "="*50)
    print("最终结论：", result["final_answer"])
    
    # 保存日志（比赛要求：记录完整执行过程）
    with open("trace.jsonl", "w", encoding="utf-8") as f:
        for entry in result["trace"]:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print("\n执行日志已保存到 trace.jsonl")