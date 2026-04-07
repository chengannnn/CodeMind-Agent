import os
import sys
from langchain_core.messages import HumanMessage

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from state import AgentState

def user_input_node(state: AgentState):
    """User Input 节点：负责接收用户输入并更新状态, 支持多行输入"""
    print("\n" + "-" * 25)
    print("   请粘贴需要审查和修复的 Python 代码。")
    print("   (支持多行输入。输入完成后，请在新的一行输入 'EOF' 并按回车结束)")
    print("-" * 25 + "\n")

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "EOF":
                break
            lines.append(line)
        except EOFError:
            break

    user_code = "\n".join(lines).strip()

    user_request = "请帮我审查这段代码中的 Bug 并修复它，并提高代码的健壮性，最后给我一份正确的代码。"

    return {
        "messages": [HumanMessage(content=user_request)],
        "user_input_code": user_code,
        "current_code": user_code
    }