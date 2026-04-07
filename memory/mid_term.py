# memory/mid_term.py
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, RemoveMessage
from langchain_openai import ChatOpenAI
from state import AgentState

load_dotenv()

# 初始化 DeepSeek (请在环境变量中设置 DEEPSEEK_API_KEY)
llm = ChatOpenAI(
    model="deepseek-chat", 
    api_key=os.getenv("DEEPSEEK_API_KEY"), 
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
    max_tokens=1024
)

def summarize_memory_node(state: AgentState):
    """
    LangGraph 节点：用于生成和更新中期记忆摘要
    当 messages 列表过长时调用此节点
    """
    messages = state["messages"]
    summary = state.get("summary", "")
    
    # 假设我们设定：当消息超过 6 条时触发摘要压缩
    if len(messages) <= 6:
        return {"messages": []} # 不做任何操作
    
    # 提取需要被总结的早期消息 (排除最近的 2 条消息以保持短期上下文鲜活)
    messages_to_summarize = messages[:-2]
    
    # 构建摘要 Prompt
    summary_prompt = (
        f"这是之前的对话摘要：{summary}\n\n"
        "请将以下新的对话内容融入摘要中，并输出一个精简的、包含核心技术细节和已解决问题的最新摘要："
    )
    
    summary_messages = [
        SystemMessage(content=summary_prompt)
    ] + messages_to_summarize
    
    # 调用 DeepSeek 生成新摘要
    response = llm.invoke(summary_messages)
    new_summary = response.content
    
    # 返回新的摘要，并且使用 RemoveMessage 指令从 State 中删除已经被总结的早期消息
    delete_messages = [RemoveMessage(id=m.id) for m in messages_to_summarize]
    
    return {
        "summary": new_summary,
        "messages": delete_messages
    }