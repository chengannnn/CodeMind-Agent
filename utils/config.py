import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

def get_env_var(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"环境变量 {key} 未设置，请检查 .env 文件。")
    return value

# 导出需要的配置
DEEPSEEK_API_KEY = get_env_var("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = get_env_var("DEEPSEEK_BASE_URL")

EMBEDDING_API_KEY = get_env_var("EMBEDDING_API_KEY")
EMBEDDING_BASE_URL = get_env_var("EMBEDDING_BASE_URL")