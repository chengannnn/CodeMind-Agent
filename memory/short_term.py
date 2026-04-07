# 只是用python实现一个简单的滑动窗口记忆模块，这个agent系统不去调用这个方法。
# state["messages"]本身就是一个短期记忆模块，并且在mid_term_memory_node中有自动截断和总结的功能。

from collections import deque

class SlidingWindowMemory:
    def __init__(self, window_size: int = 5):
        """
        初始化一个基于滑动窗口的短期记忆模块。
        :param window_size: 记忆中保留的最大对话轮数（一问一答算2条消息）
        """
        # 使用 deque (双端队列) 可以非常方便地实现固定长度的滑动窗口
        self.messages = deque(maxlen=window_size)
    
    def add_message(self, role: str, content: str):
        """添加新消息，如果超过 window_size，最老的消息会自动被挤出"""
        self.messages.append({"role": role, "content": content})
        print(f"[ShortTermMemory] 记录消息: {role}. 当前记忆长度: {len(self.messages)}")

    def get_context(self) -> list:
        """获取当前所有的短期上下文"""
        return list(self.messages)

# --- 测试代码 ---
if __name__ == "__main__":
    memory = SlidingWindowMemory(window_size=3)
    
    # 模拟多轮对话
    memory.add_message("user", "你好，帮我看看这段 Python 代码。")
    memory.add_message("assistant", "好的，请发送代码。")
    memory.add_message("user", "代码是: print(1/0)")
    
    print("\n当前记忆流:", memory.get_context())
    
    # 再添加一条消息，触发滑动窗口，最早的 "你好..." 将会被丢弃
    memory.add_message("assistant", "这段代码会引发 ZeroDivisionError。")
    print("\n触发截断后的记忆流:", memory.get_context())