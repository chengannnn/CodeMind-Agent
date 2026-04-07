import os
import sys
from langchain_core.messages import RemoveMessage

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from state import AgentState

def clear_node(state: AgentState):
    """
    清除节点：在任务结束后、开启下一轮或退出前，彻底清空状态缓存
    """
    print("\n🧹 [清除节点] 正在清空系统状态缓存...")

    messages = state.get("messages", [])

    # 清空消息列表(在 LangGraph 中清空消息列表，必须对现有的每条消息发送 RemoveMessage 指令)
    delete_messages = [RemoveMessage(id = m.id) for m in messages]

    return {
        "messages": delete_messages,
        "current_code": "",
        "user_input_code": "",
        "summary": "",
        "long_term_context": "",
        "plan": [],
        "next_worker": "",
        "match_status": ""
    }