import os
import sys
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser

from state import AgentState
from utils.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# 定义期待的结构化输出
class FixResult(BaseModel):
    fixed_code: str = Field(description="修复后的完整的代码。不要包含任何markdown代码块标记（如 ```python ），只输出纯文本代码本身。")
    explanation: str = Field(description="对所作修改的简要文字说明。")

# 初始化llm
llm = ChatOpenAI(
    model = "deepseek-chat",
    api_key = DEEPSEEK_API_KEY,
    base_url = DEEPSEEK_BASE_URL,
    max_tokens = 2048,
    temperature = 0.1
)

# 初始化解析器
parser = PydanticOutputParser(pydantic_object=FixResult)

def fixer_node(state: AgentState):
    """fixer node: 根据审查意见修改代码"""
    current_code = state.get("current_code", "")
    messages = state.get("messages", [])

    #  获取检索到的长期记忆，当进入 similar 分支时，通过查看历史修改记录直接进行修改
    long_term_context = state.get("long_term_context", "无相关历史经验。")

    recent_context = "暂无近期讨论。"
    if messages:  # 提取最近的上下文（只提取最后三条）
        recent_context = "\n\n".join([msg.content for msg in messages[-3:]])

    # 【修改记录】：优化prompt，需要同时参考历史经验和近期审查意见。
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个实战经验丰富的代码修复专家 (Code Fixer)。\n"
                   "你的任务是阅读【相关历史经验】和【近期的审查意见】，并据此重写和修复【原始代码】。\n"
                   "如果只有历史经验而没有审查意见，请直接模仿历史经验中的修复手法。\n"
                   "请务必提供完整修复后的代码以及修改说明。\n\n"
                   "【极其重要】你必须严格按照以下的格式输出：\n"
                   "{format_instructions}"),
        ("user", "【相关历史经验】:\n{long_term_context}\n\n"
                 "【近期的审查意见】:\n{recent_context}\n\n"
                 "【需要修复的原始代码】:\n{current_code}\n\n"
                 "请给出修复后的最终代码：")
    ])

    chain = prompt | llm | parser  # 直接在链中加入解析器，输出会被自动解析成 FixResult 对象

    print("\n [fixer] 正在分析并修改代码...")
    response = chain.invoke({
        "long_term_context": long_term_context,
        "recent_context": recent_context,
        "current_code": current_code,
        "format_instructions": parser.get_format_instructions()
    })

    print("\n [fixer] 代码修复完成！")

    formatted_message = f"**修复说明:**\n{response.explanation}\n\n**最终代码:**\n```\n{response.fixed_code}\n```"

    return {
        "messages": [AIMessage(content = f"[fixer 修复结果]\n{formatted_message}")],
        "current_code": response.fixed_code
        }