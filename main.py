# 启动入口与 langgraph 工作流图的定义

import os
import sys
from typing import Literal

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

# 导入组件
from state import AgentState
from agents.manager import manager_node
from agents.reviewer import reviewer_node
from agents.fixer import fixer_node
from memory.mid_term import summarize_memory_node
from memory.long_term import retrieve_long_term_memory_node, save_experience_node
from nodes.user_input import user_input_node
from nodes.clear import clear_node

# 定义路由逻辑
# 根据 manager 在 state["next_worker"] 中的值，决定下一步的节点。（输出的是严格的字符串，用于后续的节点匹配）
def router(state: AgentState) -> Literal["reviewer", "fixer", "summarize"]:
    next_worker = state.get("next_worker", "FINISH")

    if next_worker == "reviewer":
        return "reviewer"
    if next_worker == "fixer":
        return "fixer"
    else:
        return "save_experience"

def continue_router(state: AgentState) -> Literal["user_input", "clear"]:
    """循环路由逻辑：询问用户是否继续"""
    while True:
        choice = input("\n 是否需要继续输入下一个待修改代码？(y/n): ").strip().lower()
        if choice == 'y':
            print("\n🔄 系统正在重置，准备迎接新任务...")
            return "user_input"
        elif choice == 'n':
            print("\n👋 感谢使用，系统安全退出！\n")
            return "__end__"
        else:
            print("❌ 无效输入，请输入 y 或 n。")

# 构建 langgraph 图结构
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("user_input", user_input_node)  # 用户输入节点，作为工作流的入口节点，负责接收用户输入的代码
workflow.add_node("retrieve_memory", retrieve_long_term_memory_node)
workflow.add_node("manager", manager_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("fixer", fixer_node)
workflow.add_node("save_experience", save_experience_node)
workflow.add_node("summarize", summarize_memory_node)
workflow.add_node("clear", clear_node)

# 添加边
workflow.set_entry_point("user_input")  # 先从用户输入节点开始
workflow.add_edge("user_input", "retrieve_memory")  # 先检索长期记忆
workflow.add_edge("retrieve_memory", "manager")  # 进入manager节点，生成plan
workflow.add_conditional_edges(
    "manager",
    router, # 路由函数，返回的是字符串，根据router的返回值，找到对应的节点
    {
        "reviewer": "reviewer",
        "fixer": "fixer",
        "save_experience": "save_experience"
    }
)

# worker nodes 执行完成之后，回到 manager 进行“汇报”，并由 manager 决定下一步(结束还是继续进入其他节点)
workflow.add_edge("reviewer", "manager")
workflow.add_edge("fixer", "manager")
workflow.add_edge("save_experience", "summarize")
workflow.add_edge("summarize", "clear")

# clear 之后决定是结束还是继续输入
workflow.add_conditional_edges(
    "clear",
    continue_router,
    {
        "user_input": "user_input",  # 如果 y，切回开头
        "__end__": END  # 如果 n，结束工作流
    }
)

app = workflow.compile()  # 实例化工作流

# 主程序入口
if __name__ == "__main__":
    
    # 定义初始状态
    initial_state = AgentState(
        messages = [],
        current_code = "",
        user_input_code = "",
        summary = "",
        long_term_context = "",
        plan = [],
        next_worker = "",
        match_status = ""
    )

    print("="*50, "\n")
    print("🚀 系统开始运行...\n")
    print("="*50)

    # 流式输出，观察agent执行过程
    for event in app.stream(initial_state):
        for node_name, node_output in event.items():
            if node_name != "user_input":
                print(f"\n--- [{node_name}执行完毕] ---")

            # 打印出 reviewer 和 fixer 节点的最后一条消息，观察它们的输出结果。
            if node_output and node_name in ["reviewer", "fixer"] and "messages" in node_output:
                last_message = node_output["messages"][-1].content
                print(f"  => {last_message}")
    
    print("\n 系统运行结束！")
