# 天璇 Merak：AI 群友 · 社交记忆人设系统

一个长期活在真实多人 QQ 群里、以固定/可切换人设参与聊天的机器人。
核心目标：**角色一致性**——把静态人设、世界观约束、动态演化的长期记忆统一起来。

> 💡 **第一次用？** 请看 [《天璇 Merak 使用说明书》](docs/USER_GUIDE.md)——面向零基础用户的完整上手指南（含 QQ 接入）。
> 下面这份 README 面向开发者/想快速了解的人。

## 差异化定位

论文都在解决"单个 AI 怎么记住单个人"，工程实现停留在"人设 prompt + 向量库"。
本项目聚焦空白点：**社交记忆人设**——面向真实多人群聊，多角色按 ID 隔离记忆空间，
成员社会关系图 + 好感度 + 群黑话 + 事件记忆统一成可检索的身份锚点。

## 核心机制

- **记忆四层**：静态核心（不可变人设）/ 社交演化层（好感度/称呼/互动风格）/ 事件记忆（带关键词钩子）/ 近期上下文
- **关键词钩子**：对话后提取 hooks（实体/事件/情绪），新消息用 hook 匹配召回历史记忆——可解释的检索主轴，向量仅兜底
- **人设锚定**：每次生成把静态核心完整注入，召回的记忆经一致性过滤（taboo 拦截），防止演化记忆污染核心人设
- **结构化沉淀**：对话超窗后，用 LLM function calling 产出事件记忆 + 社交更新，全部按 character_id 隔离

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置模型（config.yaml）
#    base_url 可切 DeepSeek/通义/Kimi/OpenAI/Ollama，key 用环境变量注入
set YOUNCHAT_API_KEY=your_key

# 3. 验证内核（无需 API key，用 Mock LLM 跑 5 个验证目标）
python -m youchat.tests.verify

# 4. 一键启动（NapCat + Web UI 串起来跑）
python start.py

# 5. 启动图形化控制台（Web / Desktop / TUI 三形态可切换）
python -m youchat                 # 按上次保存的模式启动
python -m youchat --mode web      # Web 界面（浏览器，推荐首次）
python -m youchat --mode desktop  # 桌面窗口（需 pywebview，缺省降级浏览器）
python -m youchat --mode tui      # 终端菜单（唯一能直接聊天的形态）

# 6. 命令行直达本地群聊模拟
python -m youchat.adapters.local_shell --role laomao
# 输入 `阿伟: 今天好冷` 发消息；`!switch <角色>` 切角色；`!members` 看好感度
```

`start.py` 会：检查 NapCat（缺失反向 WS 时给 WebUI 配置引导）→ 启动 NapCat → 读 settings 自动连 QQ 机器人 → 启动 Web UI 并自动开浏览器。

## 控制台 UI（配置 / 角色 / 启动）

三种界面共享同一套业务核心（`console/controller.py`），在界面里可切换模式（下次启动生效）：

| 功能 | 说明 |
|---|---|
| **配置** | 可视化编辑 config.yaml 六段（模型/存储/引擎/检索/预算/一致性），保存时校验 |
| **角色** | 角色列表 + 编辑表单，taboos 嵌套编辑器（text/keywords/examples） |
| **启动** | 选角色启动引擎（可用 Mock LLM 试跑），查看运行状态 |

TUI 形态下 `3 启动` 会进入真实群聊模拟；Web/Desktop v1 只到"启动"，聊天面板后续迭代。

## 角色定义

`youchat/characters/*.yaml`，一个文件一个角色：

```yaml
character_id: laomao
name: 老猫
personality: 外冷内热，爱吐槽，嘴硬心软
speech_style: 短句，爱用反问，偶尔毒舌
background: 群里的元老成员
worldview: 用吐槽化解一切，从不承认自己在意别人
taboos:
  - text: 绝不承认自己熬夜
    keywords: [熬夜, 通宵, 熬]      # 三层判定 L1 同义词
    examples:                       # L2 少样本参考（"也算违规"的表述）
      - 老猫说自己昨晚通宵打游戏
      - 老猫顶着黑眼圈说没事
```

taboos 支持两种格式：dict（text/keywords/examples）或纯字符串（只做子串判定）。

## 接入 QQ

机器人通过 NapCat（OneBot11 协议）接入 QQ：`python start.py` 一键启动（检查/启动 NapCat → 引导配置反向 WS → 自动连机器人 → 开 Web UI）。

- **反向 WS**：适配器监听 `ws://127.0.0.1:6700`，NapCat 反向 WebSocket 连过来
- **触发**：@ 才回复，未@只进记忆（不刷屏）；群里不开放命令
- **文档**：[NapCat 安装指引](docs/qq-napcat-setup.md)、[使用说明书](docs/USER_GUIDE.md)

## 目录结构

```
YOUchat/
├── start.py          # 一键启动脚本（NapCat + Web UI）
├── NapCat/           # QQ 连接器（launcher.bat 启动）
├── memory/           # 每个角色的记忆沉淀库（.txt）
├── docs/             # 使用说明书 + NapCat 安装指引
├── youchat/
│   ├── core/         # 记忆/人设内核（与接入无关）
│   │   ├── models.py # 数据模型
│   │   ├── storage.py# SQLite 持久化，按 character_id 隔离
│   │   ├── extraction.py # 结构化沉淀 + hooks 提取
│   │   ├── retrieval.py  # 关键词钩子 + 向量检索
│   │   ├── anchoring.py  # 上下文组装 + 一致性过滤
│   │   ├── embeddings.py # Embedding 抽象层（本地 bge / 云端）
│   │   ├── vector_index.py # 内存余弦向量索引
│   │   ├── scheduling.py   # 分层记忆预算调度
│   │   └── persona.py      # 人设加载校验
│   ├── adapters/      # 消息接入（local_shell + qq_napcat）
│   ├── console/       # Web/Desktop/TUI 三形态控制台
│   ├── llm.py         # OpenAI 兼容抽象层（openai/httpx 双后端）
│   ├── engine.py      # 聊天引擎：收消息→检索→锚定→生成→沉淀
│   ├── config.yaml    # 配置
│   └── characters/    # 角色定义
```

## 参考文献与关联项目

天璇 Merak 站在巨人肩膀上。向以下论文与开源项目致敬：

### 学术论文

| 方向 | 论文 | 借鉴 |
|---|---|---|
| 记忆分层 | [MemGPT: Towards LLMs as Operating Systems](https://ar5iv.labs.arxiv.org/html/2310.08560) | 长期/短期记忆分层调度的思想 |
| 动态记忆 | [A-MEM: Agentic Memory for LLM Agents](https://papers.neurips.cc/paper_files/paper/2025/hash/19909c36f51abc4856b4560aff3d36d6-Abstract-Conference.html) | 由 LLM 驱动的动态记忆结构 |
| 人设一致性 | [Test-Time Matching: Decouple Personality, Memory, and Linguistic Style](https://arxiv.org/abs/2507.16799v1) | 人格 / 记忆 / 语言风格解耦 |
| 动态人设 | [Dynamic Persona Coherence in LLM Role-Playing](https://aclanthology.org/2026.acl-long.1336/) | 人设随交互动态演化 |
| 语义锚定 | [Semantic Anchoring in Agentic Memory](https://ar5iv.labs.arxiv.org/html/2508.12630) | 关键词钩子检索的可解释性思路 |

### 开源项目

| 项目 | 致敬 |
|---|---|
| [NapCatQQ](https://github.com/NapNeko/NapCatQQ) | 本项目 QQ 接入的基石（OneBot 11 协议） |
| [OpenClaw 社区](https://github.com/openclaw) | 群聊机器人生态的启发 |
| [Ollama](https://github.com/ollama/ollama) | 本地大模型运行支持 |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | 本地语义 embedding 实现参考 |

> 本项目聚焦论文与工程都未充分覆盖的**社交记忆人设**：真实多人群聊中，多角色隔离记忆、成员社会关系演化与角色一致性的统一。
