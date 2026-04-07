# memory/long_term.py  包涵“检索与写入”双向功能

import os
import sys
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma  # langchain 集成的 Chroma 向量数据库
from langchain_core.documents import Document

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from utils.config import EMBEDDING_API_KEY, EMBEDDING_BASE_URL
from state import AgentState

class LongTermMemory:
    def __init__(self):
        # 初始化 siliconflow 的embedding 模型
        self.embeddings = OpenAIEmbeddings(
            api_key = EMBEDDING_API_KEY,
            base_url = EMBEDDING_BASE_URL,
            model = "BAAI/bge-m3",
            check_embedding_ctx_length = False
        )

        # 初始化 chroma 向量数据库
        # 确保数据库文件稳定保存在 chroma_db 文件夹中
        db_path = os.path.join(parent_dir, "chroma_db")  # chroma_db文件夹的绝对路径
        self.vector_store = Chroma(  # 初始化 Chroma 向量数据库
            collection_name = "historical_bug_fixes",
            embedding_function = self.embeddings,
            persist_directory = db_path
        )

    def add_experience(self, code_snippet: str, fix_explanation: str, language: str = "python"):
        """将成功的修复经验存入长期记忆，并包含查重机制，防止存入大量重复数据"""

        # 查重机制（检索出最相似的一条记录，对比它们的文本内容是否高度一致。）
        # 使用 similarity_search_with_score 可以同时返回匹配的文档和相似度分数
        results = self.vector_store.similarity_search_with_score(code_snippet, k = 1)

        if results:
            best_match_doc, score = results[0]
            # 精确对比, 如果完全相同就不放进去
            if best_match_doc.page_content.strip() == code_snippet.strip():
                print("\n [LongTermMemory] 查重拦截：该 Bug 的修复经验已存在！")
                return  # 直接返回，终止后续的保存流程
            # # 相似度分数对比
            # if score < 0.1:
            #     print(f"\n [LongTermMemory] 查重拦截：发现高度相似的代码 (距离:{score:.4f})，跳过保存。")
            #     return

        # 进行存储
        doc = Document(
            page_content = code_snippet,
            metadata = {"fix": fix_explanation, "language": language}
        )
        self.vector_store.add_documents([doc])  # 将文档添加到向量数据库
        print("\n [LongTermMemory] 已将修复经验存入长期记忆库！")

    def retrieve_experience(self, current_code: str, top_k: int = 1) -> str:  # topk设置为1，表示只返回最相关的一个修复经验
        """检索与当前代码最相似的历史修复经验，并返回匹配状态"""
        results = self.vector_store.similarity_search_with_score(current_code, k=top_k)  # 获取相关经验和相似度分数

        if not results:
            return "长期记忆库为空。", "NONE"

        best_match_doc, score = results[0]  # 最相关的历史修复经验, 和相似度分数
        historical_code = best_match_doc.page_content
        fix_solution = best_match_doc.metadata.get("fix", "无相关修复方案。")

        print(f" => 与最相似历史代码的 L2 距离: {score:.4f}")

        context = (
            f"[长期记忆检索]-发现类似代码片段：\n"
            f"历史代码：{historical_code}\n"
            f"对应的修复方案：{fix_solution}"
        )

        # 增加匹配状态判断逻辑
        if best_match_doc.page_content.strip() == current_code.strip():
            status = "IDENTICAL"
        elif score < 0.2:  # 高度相似
            status = "SIMILAR"
        else:
            status = "NONE"
        
        if status == "NONE":
            context = "无相关历史经验。"

        return context, status
    
# 实例化长期记忆函数
ltm = LongTermMemory()

# 定义长期记忆节点（记忆一般都是靠节点实现，因为节点可以直接访问state，可以在其中存储和检索记忆）
"""长期记忆节点有两个：检索节点 & 保存节点，分别用于实现不同功能"""
def retrieve_long_term_memory_node(state:AgentState):
    """检索节点：在任务开始前调用，检索历史经验"""
    current_code = state.get("current_code", "")
    if not current_code:
        return {"match_status": "NONE"}  # 返回空字符串，让state知道没有进行任何操作，比起返回空值更加安全

    print("[长期记忆节点] 正在检索相关记忆...")  # 当前字符串不空时，进入节点开始检索
    experience, status = ltm.retrieve_experience(current_code)  # 通过长期记忆函数检索相关经验

    if status == "IDENTICAL":
        print("[长期记忆节点] 找到完全相同的历史经验。")
    elif status == "SIMILAR":
        print("[长期记忆节点] 找到高度相似的历史经验。")
    else:
        print("[长期记忆节点] 未找到相关历史经验。")

    return {
        "long_term_context": experience,
        "match_status": status
    }

def save_experience_node(state:AgentState):
    """保存节点：在任务结束前调用，将本次的Bug和修复方案存入记忆"""
    current_code = state.get("user_input_code", "")  # 存入用户原始输入的代码
    messages = state.get("messages", [])  # 要在message列表中找到当前修复方案的记录

    # 提取修复方案：从后往前查找，找到第一条或倒数几条包含“修复方案”的消息，即为当前代码对应的修复记录。
    fix_explanation = "无修复方案记录。"  # 默认值
    for msg in reversed(messages):
        # "[fixer 修复结果]" 是在fixer节点硬编码在 response.content 前面的，所以可以通过message中
        # 是否存在"[fixer 修复结果]"这个字段，来判断是不是fixer节点的输出
        # 而且，fixer节点的返回在messages列表中的信息被设定为AIMessage，所以'msg.type == "ai"'可以确定message的类型
        if msg.type == "ai" and "[fixer 修复结果]" in msg.content:
            # 截取修复结果的核心部分存入向量库
            fix_explanation = msg.content.strip()
            break
    
    ltm.add_experience(code_snippet = current_code, fix_explanation = fix_explanation)
    return {}  # 只负责保存，并不改变state中的任何值，所以返回一个空字典，表示没有对state进行更新

# --测试--
if __name__ == "__main__":
    print("测试长期记忆")
    test_code = "print(1/0)"
    ltm.add_experience(test_code, "ZeroDivisionError。除数不能为0，需增加 if 判断。")
    print(ltm.retrieve_experience(test_code))

