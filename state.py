# 全局状态 state 的定义

from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # 短期记忆：原生消息队列
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # 中期记忆：历史对话摘要
    summary: str
    # 长期记忆：检索到的相关历史 Bug/修复经验
    long_term_context: str
    # 当前处理的代码片段
    current_code: str
    # 用户输入的代码片段(用于保存最初的代码)
    user_input_code: str
    # Manager 生成的规划任务列表
    plan: list[str]
    # 记录 Manager 决定下一步交给谁执行
    next_worker: str
    # 记录长期记忆的匹配状态：'IDENTICAL' (完全一致), 'SIMILAR' (高度相似), 'NONE' (无匹配)
    match_status: str
