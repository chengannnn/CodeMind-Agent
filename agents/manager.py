from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import PydanticOutputParser  # 【新增】引入解析器
import sys
import os

# 确保能找到根目录的模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from state import AgentState
from utils.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

# 1. 定义期望的结构化输出数据模型
class TaskPlan(BaseModel):
    thoughts: str = Field(description="在制定计划前的思考过程，分析代码现状、历史经验以及当前执行进度")
    steps: List[str] = Field(description="拆解出的具体步骤列表，例如：['审查代码是否存在内存泄漏', '重构冗余的循环逻辑']")
    next_worker: str = Field(description="下一步应该将任务交给谁：'reviewer' (负责代码审查), 'fixer' (负责修改代码), 或者 'FINISH' (所有任务已完成)")

# 2. 初始化 DeepSeek 模型
llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    max_tokens=2048,
    temperature=0.1
)

# 初始化 Pydantic 解析器，取代 with_structured_output，用于将json变为想要的格式化输出
parser = PydanticOutputParser(pydantic_object=TaskPlan)

def manager_node(state: AgentState):
    """Manager 节点：负责分析当前状态，制定计划并决定下一步路由"""
    current_code = state.get("current_code", "")
    long_term_context = state.get("long_term_context", "无相关历史经验。")
    messages = state.get("messages", [])
    match_status = state.get("match_status", "NONE")  # 获取匹配程度，用于决定不同流向

    user_request = messages[0].content if messages else "请审查并修复这段代码"  # 提取用户请求

    # 提取历史记录摘要，让 manager 知道之前发生了什么
    execution_history = "暂无执行记录，目前为第一步。"  # 默认值
    if len(messages) > 1:
        # 把除第一条用户请求外的后续消息（reviewer或fixer的输出）拼接起来
        history_list = []
        for msg in messages[1:]:
            role = "reviewer" if "审查报告" in msg.content else "fixer" if "修复结果" in msg.content else "unknown"  # 看消息中是否有硬编码的特定字符串
            history_list.append(f"[{role} 的输出]: \n{msg.content[:150]}...")
        
        execution_history = "\n\n".join(history_list)  # 将消息列表拼接，以便给 manager 读取

    # 3. 构建 Manager 的系统提示词，通过SOP让llm更好的执行任务
    # 【修改记录】重构 SOP 规则，加入短路逻辑，并修复冗余思考问题
    prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个资深的研发经理 (Manager)。你的任务是接收用户的代码处理需求，并制定清晰的执行计划。
                        你有两个下属：reviewer (负责代码审查) 和 fixer (负责代码修复)。

                        【关键决策参考】
                        历史记忆匹配状态: {match_status} (IDENTICAL:完全一致, SIMILAR:高度相似, NONE:无匹配或不相关)
                        相关历史经验: {long_term_context}
                        当前执行进度: 
                        {execution_history}

                        【严格 SOP 路由规则 (状态机判断)】
                        请务必根据【当前执行进度】的最新状态，严格按照以下规则决定 next_worker：

                        ▶ 状态 A (流程收尾)：
                        判断条件：如果【当前执行进度】中已经出现了 [fixer 的输出] 或修复结果。
                        动作：任务已彻底完成。不要检查原始代码，必须直接输出 'FINISH'。

                        ▶ 状态 B (审查后修复)：
                        判断条件：如果【当前执行进度】中已经有了 [reviewer 的输出]（审查报告），但还没有 fixer 的输出。
                        动作：问题已查明，现在必须安排修复。输出 'fixer'。

                        ▶ 状态 C (任务初始启动)：
                        判断条件：如果【当前执行进度】显示为"暂无执行记录"。
                        动作：请根据 match_status 决定路线：
                        - 若为 'IDENTICAL'：说明历史记录完美命中，无需下属干预，直接输出 'FINISH'。
                        - 若为 'SIMILAR'：存在高度相似经验，跳过审查以提升效率，直接输出 'fixer'。
                        - 若为 'NONE'：全新代码，按标准流程先进行排查，输出 'reviewer'。

                        【极其重要】你必须严格按照以下格式输出：
                         {format_instructions}"""),
            ("user", "【用户需求】: {user_request}\n\n"
                    "【待处理的代码】:\n{current_code}\n\n"
                    "请开始你的规划，严格根据SOP状态机决定 next_worker。")
    ])

    # 4. 执行调用链：Prompt -> LLM -> Parser 解析
    chain = prompt | llm | parser
    
    # 将所需变量传入 chain (chain过程所需的所有输入)
    result: TaskPlan = chain.invoke({
        "user_request": user_request,
        "long_term_context": long_term_context,
        "match_status": match_status,
        "execution_history": execution_history,
        "current_code": current_code,
        "format_instructions": parser.get_format_instructions()
    })

    print("\n")
    print(f"👨‍💼 [Manager] 内部思考: {result.thoughts}")
    print(f"👨‍💼 [Manager] 计划拆解: {result.steps}")
    print(f"👨‍💼 [Manager] 下一步指派: {result.next_worker}")
    print("\n")

    # 如果匹配状态是完全一致，并且决定直接 FINISH，Manager 亲自输出历史方案
    if match_status == "IDENTICAL" and result.next_worker == "FINISH":
        manager_announcement = (
            f"**[Manager] 直接应用历史经验**\n\n"
            f"{long_term_context}\n\n"
            f"*(系统提示：已跳过 Reviewer 和 Fixer，直接根据历史经验进行修复)*"
        )
        # 在终端直接打印出来方便观察
        print(f"📢 {manager_announcement}\n")

    # 5. 返回更新后的 State
    return {
        "messages": [AIMessage(content = "[manager]\n manager 节点处理完成。")],
        "plan": result.steps,
        "next_worker": result.next_worker
    }

# --- 测试代码 ---
if __name__ == "__main__":
    # 模拟一个从第一天传过来的测试状态
    mock_state = AgentState(
        messages=[HumanMessage(content="帮我看看这段代码有没有性能问题，并修复它。")],
        summary="",
        long_term_context="💡 [长期记忆检索] 发现类似的历史问题：\n历史修复方案：在遍历列表时修改其长度会导致 IndexError。建议使用倒序遍历。",
        current_code="for i in range(len(my_list)):\n    if my_list[i] == 0:\n        my_list.pop(i)",
        plan=[],
        next_worker=""
    )
    
    print("正在呼叫 Manager 制定计划...")
    new_state = manager_node(mock_state)