#  CodeMind Agent — 基于 LangGraph 的自动化代码审查与修复多智能体系统

> 一个具备**自我进化记忆能力**的多智能体代码审查引擎，通过严格的状态机路由、三层记忆架构与向量语义匹配，实现从「接收代码 → 智能分发 → 审查诊断 → 自动修复 → 经验沉淀」的完整自动化闭环。

---

## 📑 目录

- [项目简介](#-项目简介)
- [核心特性](#-核心特性)
- [系统架构与运行流程](#-系统架构与运行流程)
- [项目结构与模块说明](#-项目结构与模块说明)
- [快速开始](#-快速开始)
- [技术栈](#-技术栈)
- [架构设计理念](#-架构设计理念)

---

## 📖 项目简介

**CodeMind Agent** 是一个基于 **LangGraph** 构建的 Multi-Agent 代码审查与修复系统。传统代码审查工具往往只做静态分析或单次 LLM 调用，而本系统将大语言模型的推理能力与**有状态图工作流**深度结合，带来了以下差异化价值：

| 维度 | 传统方案 | CodeMind Agent |
|:---|:---|:---|
| 审查深度 | 单轮 LLM 调用 | Manager 规划 → Reviewer 审查 → Fixer 修复，多轮迭代 |
| 经验复用 | 无 | ChromaDB 向量检索，历史相似 Bug 的修复方案可被直接复用 |
| 持续对话 | 每次独立 | 摘要压缩 + 状态隔离，支持多轮连续审查任务 |
| 流程控制 | 线性或无 | 严格 SOP 状态机路由，避免无限循环与资源浪费 |

系统的核心理念是：**审查一个 Bug 的经验，应该成为修复下一个 Bug 的资产**。通过向量化的长期记忆，系统能够在遇到相似问题时"秒级响应"，真正实现越用越聪明的自我进化能力。

---

## ✨ 核心特性

### 🔄 状态机路由架构 (State Machine Routing)

系统摒弃了 LLM 自由发散的调用模式，采用 **MECE（Mutually Exclusive, Collectively Exhaustive）** 原则设计的严格 SOP 路由策略。Manager 节点根据当前执行阶段（`execution_history`）和长期记忆匹配状态（`match_status`）进行确定性的下一跳决策：

- **状态 A — 流程收敛**：已有 Fixer 输出 → 判定任务完成，流转至 `FINISH`
- **状态 B — 先审后修**：已有 Reviewer 输出但无 Fixer 输出 → 派发至 `fixer`
- **状态 C — 冷启动**：根据 `match_status` 决策
  - `IDENTICAL` → 直接 `FINISH`，历史方案即为答案
  - `SIMILAR` → 派发 `fixer`，参照历史经验直接修复
  - `NONE` → 派发 `reviewer`，从零开始完整审查

这种设计确保了**每个节点只执行一次**，杜绝了 LangGraph 工作流中常见的无限循环问题。

### 🧠 三层记忆机制 (Three-Tier Memory)

| 层级 | 载体 | 容量策略 | 作用 |
|:---|:---|:---|:---|
| **短期记忆** | `state["messages"]` (add_messages Reducer) | LangGraph 原生消息队列 | 承载当前审查任务的完整对话上下文 |
| **中期记忆** | `state["summary"]` (LLM 摘要) | 消息 > 6 条时触发压缩 | 防止上下文膨胀，保留任务关键信息 |
| **长期记忆** | ChromaDB 向量库 (`chroma_db/`) | 持久化磁盘存储 | 跨任务复用历史 Bug 的审查结论与修复方案 |

### 🎯 向量查重与捷径匹配 (Vector Matching & Short-circuit)

长期记忆检索不是简单的"相关与否"二分判断，而是通过 **代码精确比对 + 向量距离阈值** 实现三态匹配：

```
用户输入代码 ──► ChromaDB similarity_search_with_score(k=1)
                     │
                     ├── 完全匹配 (page_content.strip() == input.strip())
                     │      └──► IDENTICAL ──► 历史修复方案即为答案，直接秒杀
                     │
                     ├── L2 距离 < 0.2
                     │      └──► SIMILAR ──► 存在高度相似的修复经验，模仿修复
                     │
                     └── 其余情况
                            └──► NONE ──► 全新问题，启动完整审查流程
```

- **IDENTICAL（完全一致）**：代码去重命中，直接输出历史修复方案，**跳过 Reviewer 和 Fixer**，零 LLM 调用消耗
- **SIMILAR（高度相似）**：向量距离 `< 0.2`，检索到的历史修复方案作为 Few-shot 提示注入 Fixer，实现**经验迁移**
- **NONE（全新问题）**：无相关历史，启动标准的 Reviewer → Fixer 完整链路，并在任务结束后将新经验入库

### ♻️ 优雅的内存回收 (Graceful Garbage Collection)

LangGraph 的 `add_messages` Reducer 天然支持消息累加，但在多轮连续对话场景下会导致：

- 上一个任务的审查意见"泄漏"到下一个任务
- `current_code` 等状态字段残留，造成逻辑混乱
- 消息队列无限膨胀，上下文窗口快速耗尽

`clear` 节点通过双重清理机制解决此问题：

1. **消息级清理**：遍历所有 `messages`，为每条消息构造 `RemoveMessage(id=m.id)`，利用 Reducer 的反向语义删除旧消息
2. **状态级清理**：将所有业务字段（`current_code`、`summary`、`plan` 等）重置为初始值

清理完成后，系统通过 `continue_router` 与用户交互，选择继续下一个任务或安全退出，形成 **CLI 闭环**。

---

## 🏗️ 系统架构与运行流程

### 整体数据流图

```
                    ┌──────────────┐
                    │  user_input  │ ◄── 用户输入带 Bug 的代码 (EOF 终止)
                    └──────┬───────┘
                           │
                    ┌──────▼──────────────┐
                    │  retrieve_memory    │ ◄── ChromaDB 向量检索，打上 match_status 标签
                    │  (IDENTICAL/SIMILAR │     (三种状态决定后续路由走向)
                    │   /NONE)            │
                    └──────┬─────────────┘
                           │
                    ┌──────▼──────────────┐
                    │     manager         │ ◄── 大脑节点：生成审查计划 + 决策下一跳
                    │  (Plan-Act + SOP)   │     基于 match_status + execution_history
                    └──────┬──────────────┘
                           │
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
       ┌──────────┐ ┌──────────┐   ┌──────────────┐
       │ reviewer │ │  fixer   │   │save_experience│
       │ (审查)   │ │ (修复)   │   │ (经验入库)    │
       └────┬─────┘ └────┬─────┘   └──────┬───────┘
            │            │                │
            └────────────┘                │
                 │                        │
            回传 manager                  │
                 │                        │
                 └────────────────────────┘
                           │
                    ┌──────▼───────┐
                    │  summarize   │ ◄── 对话摘要压缩 (消息 > 6 时触发)
                    │   (mid-term) │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │    clear     │ ◄── 状态清零，隔离脏数据
                    │  (GC 清理)   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │continue_router│ ◄── 询问用户是否继续
                    │  (y → loop)  │
                    │  (n → END)   │
                    └──────────────┘
```

### 单轮任务执行详解

**1. `user_input` 接收代码**

用户以多行形式粘贴待审查代码，输入 `EOF` 终止。节点将代码同时写入 `current_code`（工作副本）和 `user_input_code`（原始快照，防止后续被修改导致记忆污染）。

**2. `retrieve_memory` 向量检索**

将 `current_code` 通过 BAAI/bge-m3 模型编码为向量，在 ChromaDB 的 `historical_bug_fixes` 集合中检索最相似的 1 条记录。根据代码精确匹配度和 L2 距离，产出 `match_status` 标签（`IDENTICAL` / `SIMILAR` / `NONE`）。

**3. `manager` 大脑决策**

读取当前 `messages` 中的执行历史，判断 Reviewer/Fixer 是否已执行。结合 `match_status` 标签，通过 LLM + Pydantic 结构化输出，产出：
- `plan`：审查/修复步骤列表
- `next_worker`：下一个执行节点（`reviewer` / `fixer` / `FINISH`）

**4. `reviewer` 审查 / `fixer` 修复**

- **Reviewer**：基于 Manager 的审查计划，对 `current_code` 进行深度代码审查，输出结构化审查报告
- **Fixer**：基于历史经验 + 近期审查意见 + 原始代码，使用 Pydantic `FixResult` 模型输出修复后的代码和说明，**物理更新** `state["current_code"]`

**5. `save_experience` 经验沉淀**

从消息历史中提取 Fixer 的修复结果。通过**代码去重拦截**检查：相同代码不重复入库。将 `<代码, 修复方案>` 作为 Document 持久化至 ChromaDB。

**6. `summarize` 摘要压缩**

当 `messages` 数量超过 6 条时，触发 LLM 摘要压缩。将旧消息浓缩为 `summary` 字段，同时用 `RemoveMessage` 删除原始消息。

**7. `clear` 状态清零**

彻底清空所有状态字段，为下一轮任务提供"白纸"状态。

**8. `continue_router` 闭环交互**

询问用户是否继续输入下一个待审查代码。`y` → 回到 `user_input` 开始新一轮；`n` → 系统安全退出。

---

## 📁 项目结构与模块说明

```
code_reviewer_agent/
├── main.py                          # 入口文件 & LangGraph StateGraph 编排
├── state.py                         # 全局状态定义 (TypedDict)
├── requirements.txt                 # Python 依赖清单
├── .gitignore                       # Git 忽略规则
├── .env                             # 环境变量配置 (API Keys, 不提交至 Git)
├── agents/                          # 智能体模块 (Worker Nodes)
│   ├── manager.py                   # Manager 大脑：规划 + SOP 路由决策
│   ├── reviewer.py                  # Reviewer 审查员：代码审查报告
│   └── fixer.py                     # Fixer 修复专家：代码修复 + 结构化输出
├── memory/                          # 三层记忆模块
│   ├── short_term.py              # 短期记忆：滑动窗口工具类 (独立组件)
│   ├── mid_term.py                # 中期记忆：对话摘要压缩节点
│   └── long_term.py               # 长期记忆：ChromaDB 向量读写核心
├── nodes/                           # 工作流节点
│   ├── user_input.py              # 用户输入接收节点
│   └── clear.py                   # 状态清理与 GC 节点
├── utils/                           # 工具类
│   └── config.py                  # 环境变量加载与校验
├── chroma_db/                       # ChromaDB 持久化存储目录 (已忽略)
│   └── chroma.sqlite3             # 向量数据库文件 (运行时自动生成)
└── __pycache__/                     # Python 字节码缓存 (已忽略)
```

### 模块详细说明

#### `state.py` — 全局状态定义

定义 LangGraph 工作流的共享状态，采用 `TypedDict` 声明：

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `messages` | `Annotated[Sequence[BaseMessage], add_messages]` | 短期记忆消息队列，LangGraph 原生 Reducer 自动管理追加/删除 |
| `summary` | `str` | 中期记忆：对话摘要，由 `summarize` 节点维护 |
| `long_term_context` | `str` | 从 ChromaDB 检索到的历史经验，注入给 Manager 和 Fixer |
| `current_code` | `str` | 当前正在处理的代码副本，Fixer 会物理修改此字段 |
| `user_input_code` | `str` | 用户原始输入快照，**永不修改**，用于 `save_experience` 时保证存入的是原始代码 |
| `plan` | `list[str]` | Manager 生成的审查/修复步骤列表 |
| `next_worker` | `str` | Manager 决策的下一跳节点名 |
| `match_status` | `str` | 长期记忆匹配状态：`IDENTICAL` / `SIMILAR` / `NONE` |

> **设计亮点**：`user_input_code` 与 `current_code` 的分离是关键设计。Fixer 节点会覆盖 `current_code`，但经验沉淀必须使用原始代码作为索引键——如果存入修复后的代码，下次相似问题时将无法正确匹配。

---

#### `main.py` — 工作流编排核心

- 定义 LangGraph `StateGraph`，注册所有节点和边
- **条件边 (Conditional Edges)** 实现动态路由：
  - `manager → router` 决定派发至 `reviewer`、`fixer` 或 `save_experience`
  - `clear → continue_router` 决定循环或退出
- 使用 `app.stream()` 以流式方式执行工作流，实时打印每个节点的输出

---

#### `agents/manager.py` — 大脑节点

Manager 是整个系统的决策中枢，职责包括：

1. **上下文聚合**：从 `state["messages"]` 中提取执行历史，识别 Reviewer/Fixer 的执行状态
2. **LLM 规划**：通过 `ChatPromptTemplate` 构建 SOP 提示词，驱动 LLM 输出 `TaskPlan`（Pydantic 结构化输出）
3. **路由决策**：基于执行历史和匹配状态的笛卡尔组合确定 `next_worker`

**SOP 路由规则 (MECE)**：

```
IF fixer 已执行过:
    → FINISH (流程终结)
ELIF reviewer 已执行过:
    → fixer (先审后修)
ELSE:
    IF match_status == "IDENTICAL":
        → FINISH (历史方案直接输出)
    ELIF match_status == "SIMILAR":
        → fixer (参照历史经验修复)
    ELSE:
        → reviewer (从零开始完整审查)
```

---

#### `agents/reviewer.py` — 审查节点

- 接收 Manager 制定的 `plan` 和 `current_code`
- 以 `temperature=0.3` 的 LLM 进行深度代码审查
- 输出格式化的审查报告，以 `AIMessage` 形式追加至消息队列
- 审查意见会包含在后续 Fixer 的上下文中，形成 **Review → Fix 的信息传递链**

---

#### `agents/fixer.py` — 修复节点

- 接收三重上下文：长期记忆经验 + 近期审查意见 + 原始代码
- 使用 **Pydantic `FixResult` 模型**约束 LLM 输出结构：`fixed_code`（修复后的完整代码）+ `explanation`（修改说明）
- 通过 `PydanticOutputParser` 实现结构化解析，避免 LLM 自由文本导致的解析失败
- **物理更新** `state["current_code"]`，确保最终输出的是修复后的代码

---

#### `memory/long_term.py` — 长期记忆核心

整个系统"自我进化"能力的技术底座：

- **向量存储**：ChromaDB 持久化于 `chroma_db/` 目录，集合名 `historical_bug_fixes`
- **Embedding 模型**：通过 SiliconFlow API 调用 `BAAI/bge-m3`（支持多语言、高质量语义表征）
- **写入流程**：先执行相似度查重 → 精确匹配则跳过入库（代码去重拦截） → 否则以 `<代码内容, 修复方案元数据>` 格式入库
- **检索流程**：对输入代码进行 Top-K 向量检索 → 三态判定（IDENTICAL / SIMILAR / NONE） → 返回格式化的上下文字符串 + 状态标签

---

#### `memory/mid_term.py` — 中期记忆节点

- **触发条件**：`messages` 数量 > 6 条时激活
- **压缩策略**：将历史消息（排除最近 2 条，保留近期上下文）送入 LLM 进行摘要融合
- **清理策略**：生成新摘要后，用 `RemoveMessage` 删除已被压缩的原始消息，释放上下文窗口

---

#### `memory/short_term.py` — 短期记忆工具类

- 基于 `collections.deque` 的滑动窗口实现
- 当前工作流中未直接调用，`state["messages"]` 的 `add_messages` Reducer 天然实现了短期记忆功能
- 作为独立组件保留，可在需要更精细窗口控制的场景中替换原生 Reducer

---

#### `nodes/user_input.py` — 用户输入节点

- 采用循环 `input()` 接收多行代码，以 `EOF` 作为终止标记
- 将代码同时写入 `user_input_code`（原始快照）和 `current_code`（工作副本）
- 附加标准化的用户需求提示词

---

#### `nodes/clear.py` — 状态清理节点

解决 LangGraph 多轮对话的核心痛点：

- **消息清理**：为所有消息构造 `RemoveMessage`，利用 `add_messages` Reducer 的反向语义彻底清空队列
- **状态重置**：将所有业务字段归零，确保下一个任务从"白纸"状态开始
- **脏状态隔离**：防止上一个任务的审查意见和代码污染下一个任务

---

#### `utils/config.py` — 配置管理

- 统一加载 `.env` 文件中的环境变量
- 提供 `get_env_var()` 校验函数，缺失变量时抛出明确异常
- 导出全局常量：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`

---

## 🚀 快速开始

### 环境要求

- Python >= 3.9
- 有效的 API Key（见下方环境变量配置）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件，填入以下配置：

```env
# DeepSeek LLM (用于 Manager / Reviewer / Fixer 的推理)
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com

# SiliconFlow Embedding API (用于 BAAI/bge-m3 向量编码)
EMBEDDING_API_KEY=your_siliconflow_api_key_here
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
```

> **说明**：向量 Embedding 服务通过 SiliconFlow 平台调用 `BAAI/bge-m3` 模型，需单独申请 API Key。

### 3. 运行系统

```bash
python main.py
```

系统启动后，按提示粘贴待审查的代码，以 `EOF` 结束输入即可开始自动化审查与修复流程。

### 使用示例

```
==================================================

🚀 系统开始运行...

==================================================
(请在此粘贴你的代码，最后一行输入 EOF)

def cal_average(numbers):
    total = 0
    for n in numbers:
        total = total + n
    result = total / len(numbers)
    return result
EOF

--- [retrieve_memory执行完毕] ---
--- [manager执行完毕] ---
--- [reviewer执行完毕] ---
  => ## 代码审查报告
     1. ZeroDivisionError: 当 numbers 为空列表时...
     2. ...
--- [manager执行完毕] ---
--- [fixer执行完毕] ---
  => 修复说明: 添加了空列表校验和类型注解...

 是否需要继续输入下一个待修改代码？(y/n):
```

---

## 🛠️ 技术栈

| 组件 | 技术选型 | 作用 |
|:---|:---|:---|
| **编排框架** | [LangGraph](https://github.com/langchain-ai/langgraph) | 有状态图工作流、条件边、Reducer 状态管理 |
| **LLM 推理** | [LangChain](https://github.com/langchain-ai/langchain) | Prompt 模板、输出解析器、消息管理 |
| **大语言模型** | DeepSeek (`deepseek-chat`) | Manager 规划、Reviewer 审查、Fixer 修复、摘要压缩 |
| **向量数据库** | [ChromaDB](https://github.com/chroma-core/chroma) | 长期记忆的持久化向量存储，支持相似度检索 |
| **Embedding 模型** | BAAI/bge-m3 (via SiliconFlow) | 多语言代码语义向量化，L2 距离相似度计算 |
| **数据校验** | [Pydantic](https://github.com/pydantic/pydantic) | LLM 结构化输出 (`TaskPlan`, `FixResult`) |
| **环境管理** | python-dotenv | `.env` 文件加载与变量注入 |

---

> *Built with LangGraph & DeepSeek — Making Code Review Intelligent, Memory-Driven, and Self-Evolving.*
