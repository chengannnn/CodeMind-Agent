from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from state import AgentState
from utils.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

llm = ChatOpenAI(
    model = "deepseek-chat",
    api_key = DEEPSEEK_API_KEY,
    base_url = DEEPSEEK_BASE_URL,
    max_tokens = 2048,
    temperature = 0.3
)

def reviewer_node(state: AgentState):
    """reviewer node: 负责审查代码，并指出问题"""
    current_code = state.get("current_code", "")
    plan = state.get("plan", [])

    # 格式化 plan ,以便放入 prompt
    plan_text = "\n".join([f"- {step}" for step in plan]) if plan else "暂无明确计划，请全面审查。"

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个极其严谨的高级代码审查员 (Code Reviewer)。\n"
                "你的任务是仔细阅读用户提供的代码，并根据 Manager 制定的【审查计划】找出潜在的 Bug、性能瓶颈和不规范之处。\n"
                "请给出清晰的 Markdown 格式审查报告，不需要修改代码，只需要指出问题和修改建议。"),
        ("user", "【Manager 制定的计划】:\n{plan_text}\n\n"
                 "【待审查的代码】:\n{current_code}\n\n"
                 "请开始你的代码审查 (Code Review)：")
    ])

    chain = prompt | llm

    print("\n [reviewer] 正在审查代码中...")
    response = chain.invoke({
        "plan_text": plan_text,
        "current_code": current_code
    })

    print("\n [reviewer] 审查完成！已生成审查报告。")

    return {"messages": [AIMessage(content = f"[reviewer 审查报告]\n{response.content}")]}


