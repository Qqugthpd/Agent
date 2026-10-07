import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# ============ 1. 工具函数 ============

def calculate_yoy(current, previous):
    """计算同比增速，内置数字清洗"""
    try:
        if isinstance(current, str):
            current = float(current.replace(",", "").replace(" ", "").replace("，", ""))
        if isinstance(previous, str):
            previous = float(previous.replace(",", "").replace(" ", "").replace("，", ""))
    except (ValueError, TypeError):
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
        "其他符合非经常性损益定义的损益项目",
        "非流动性资产处置损益",
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
    """检测净利润与经营现金流是否背离"""
    if net_profit == 0:
        return {"flag": False, "reason": "净利润为零，无法计算"}
    if operating_cashflow < 0:
        return {
            "flag": True,
            "divergence_ratio": 1.0,
            "reason": f"净利润为正({net_profit})，但经营现金流为负({operating_cashflow})，存在严重的纸面利润风险",
            "net_profit": net_profit,
            "operating_cashflow": operating_cashflow
        }
    divergence = abs(net_profit - operating_cashflow) / abs(net_profit)
    if divergence > threshold and net_profit > operating_cashflow:
        return {
            "flag": True,
            "divergence_ratio": round(divergence, 2),
            "reason": f"净利润高于经营现金流，差异达{divergence:.1%}，需核查应收账款、存货变动及非现金项目",
            "net_profit": net_profit,
            "operating_cashflow": operating_cashflow
        }
    return {"flag": False, "divergence_ratio": round(divergence, 2), "reason": "利润与现金流匹配良好，盈利质量较高"}


# ============ 2. 工具映射表 ============

TOOL_FUNCTIONS = {
    "calculate_yoy": calculate_yoy,
    "identify_non_recurring": identify_non_recurring,
    "check_cashflow_divergence": check_cashflow_divergence,
}


# ============ 3. 工具定义 ============

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


# ============ 4. ReAct 循环 ============

def run_agent(user_query, tools, tool_functions, max_steps=10):
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个上市公司财务报告分析智能体。"
                "你可以调用工具完成数据计算和异常检测。"
                "请逐步推理，每次只调用一个工具，观察结果后再决定下一步。\n\n"
                "⚠️ 最终输出要求（非常重要）：\n"
                "1. 最终回复必须是一份干净、结构化的 Markdown 分析报告，"
                "严禁出现‘第X步’、‘让我确认’、‘我需要’、‘现在我来’等任何推理过程性语言。\n"
                "2. 报告结构必须为：## 一、核心财务数据提取；## 二、同比增速计算；"
                "## 三、非经常性损益识别；## 四、净利润与经营现金流背离检测；## 五、综合分析结论。\n"
                "3. 如果某项数据（如经营现金流）在原文片段中确实缺失，"
                "请在对应位置明确写‘该数据未在本次提取的文本中披露’，不要编造数字，也不要强行计算。\n"
                "4. 金额单位统一用‘千元’或‘百万元’，并在报告开头注明。"
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
            temperature=0.1
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

        if not message.tool_calls:
            print("模型最终输出：", message.content)
            return {"final_answer": message.content, "trace": trace_log}

        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"调用工具：{func_name}({func_args})")

            if func_name in tool_functions:
                try:
                    result = tool_functions[func_name](**func_args)
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

    return {"final_answer": "达到最大步数，未能完成任务。", "trace": trace_log}
