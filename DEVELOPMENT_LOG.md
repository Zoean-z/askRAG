# 开发记录

## 一、项目目标

做一个 3 天内可以完成的最小 RAG Demo，用来补充实习里的 RAG / LangChain 相关关键词。

技术栈：

- Python
- LangChain
- Chroma
- FastAPI
- 大模型 API

目标能力：

- 读取本地文档
- 对文档进行切分
- 构建本地向量索引
- 检索相关文本片段
- 基于检索结果生成答案
- 提供 `/ask` 接口
- 返回 `answer` 和 `sources`

## 二、阶段计划

### 阶段 1：初始化项目

目标：

- 设计一个小而清晰的项目结构
- 准备依赖文件和基础工程文件

当前状态：

- 已完成

### 阶段 2：文档读取与切分

目标：

- 从 `data/docs` 读取本地文档
- 使用简单可靠的文本切分器切分文档
- 打印切分结果，确认流程正确

当前状态：

- 已完成

### 阶段 3：构建向量索引

目标：

- 选择合适的 embedding 模型
- 将切分后的文档写入本地 Chroma
- 验证 indexing 是否成功

当前状态：

- 已完成

### 阶段 4：实现检索逻辑

目标：

- 给定 query，检索 top-k 文档片段
- 打印检索结果，方便验证

当前状态：

- 已完成

### 阶段 5：实现 RAG 问答链路

目标：

- 将 query 和检索上下文一起交给模型
- 返回最终 answer
- 如果上下文不足，提示用户无法可靠回答

当前状态：

- 已完成

### 阶段 6：封装 FastAPI 接口

目标：

- 实现 `/ask`
- 请求体包含 `question`
- 返回 `answer` 和 `sources`

当前状态：

- 已完成

### 阶段 7：整理 README 与项目说明

目标：

- 整理 README 结构
- 总结项目亮点、局限和简历描述

当前状态：

- 已完成

## 三、当前项目结构

```text
askRAg/
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ rag.py
│  └─ schemas.py
├─ data/
│  ├─ chroma/
│  └─ docs/
├─ .env.example
├─ .gitignore
├─ README.md
├─ requirements.txt
├─ test_api.http
└─ DEVELOPMENT_LOG.md
```

## 四、阶段 1 完成情况

已创建的文件和目录：

- `app/`
- `data/docs/`
- `data/chroma/`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `README.md`
- `test_api.http`

当前各文件职责：

- `app/main.py`：FastAPI 入口
- `app/schemas.py`：请求体和响应体的数据模型
- `app/rag.py`：RAG 核心逻辑
- `data/docs/`：本地知识库原始文档
- `data/chroma/`：本地向量库目录

这样设计的原因：

- 体量小，适合学生 demo
- API 层和 RAG 逻辑分开，结构更清楚
- 后面写 README、讲项目、写简历会更方便

## 五、阶段 2 完成情况

目前 `app/rag.py` 中已经实现：

- `load_documents()`
- `split_documents()`
- `print_chunk_preview()`
- `run_split_demo()`

当前实现的功能：

- 从 `data/docs` 读取 `.txt` 和 `.md` 文件
- 为每个文档补充 `source` 元数据
- 使用 `RecursiveCharacterTextSplitter` 进行切分
- 打印 chunk 数量和内容预览

当前切分参数：

- `chunk_size = 150`
- `chunk_overlap = 30`

验证命令：

```powershell
.\.venv\Scripts\python.exe -m app.rag
```

验证结果：

- 成功读取文档数：`1`
- 成功切分 chunk 数：`5`

这一步的意义：

- 说明 RAG 的前半段流程已经打通
- 可以直接观察切分结果，而不是把切分当成黑盒
- 为后面的向量索引准备好了输入数据

## 六、当前风险与说明

- 当前环境使用的是 Python `3.14`
- LangChain 在 Python `3.14+` 下会出现兼容性警告
- 当前阶段 2 到阶段 5 已能跑通，但如果想让这个 demo 更稳，建议后续使用 Python `3.11` 或 `3.12`
- DashScope 的 embeddings 接口与 `langchain_openai.OpenAIEmbeddings` 在当前环境下不完全兼容，因此项目里改成了自定义的轻量封装 `CompatibleEmbeddings`

## 七、下一步

进入阶段 6：封装 FastAPI 接口。

下一步要做的事情：

- 在 `app/main.py` 中实现 `/ask`
- 接收 `question`
- 调用现有 `answer_question()`
- 返回 `answer` 和 `sources`

## 六点五、阶段 3 完成情况

阶段 3 目标：

- 将切分后的 chunks 写入本地 Chroma
- 成功完成向量化和持久化

当前实现：

- 在 `app/rag.py` 中增加了 `build_vector_store()`
- 使用 `Chroma` 作为本地向量库
- 向量库目录为 `data/chroma/`
- 每个 chunk 都补充了：
  - `chunk_index`
  - `chunk_id`
  - `source`

为什么需要 `chunk_id`：

- 便于重复执行 indexing 时按 id 删除旧数据后重建
- 避免同一批 chunk 重复写入

关键问题与定位过程：

- 一开始尝试使用 `langchain_openai.OpenAIEmbeddings`
- 真实调用后发现 DashScope 官方 OpenAI 兼容 embeddings 接口与该封装不完全匹配
- 官方最小示例可以成功调用，但 LangChain 封装会触发 `input.contents` 参数格式错误
- 因此改成了自定义 `CompatibleEmbeddings`，底层直接使用 `OpenAI(...).embeddings.create(...)`

验证命令：

```powershell
.\.venv\Scripts\python.exe -m app.rag index
```

验证结果：

- `Indexed chunks: 5`
- `Collection count: 5`

结果说明：

- 当前 1 篇测试文档被切成 5 个 chunk
- 这 5 个 chunk 都已完成向量化并写入本地 Chroma
- `data/chroma/` 下已经生成 `chroma.sqlite3` 和对应的索引目录

## 六点六、阶段 4 完成情况

阶段 4 目标：

- 给定 query，检索 top-k 文本片段
- 打印检索结果，确认检索是否符合预期

当前实现：

- 在 `app/rag.py` 中实现了：
  - `get_vector_store()`
  - `retrieve_documents()`
  - `print_retrieval_results()`
  - `run_retrieve_demo()`

验证命令：

```powershell
.\.venv\Scripts\python.exe -m app.rag search "What is Chroma used for?"
```

验证结果：

- 成功返回 3 条结果
- 第 1 条结果就是与 Chroma 最相关的 chunk

这一步的意义：

- 证明本地向量索引不只是“写进去了”
- 而是真的可以根据 query 做语义检索

## 六点七、阶段 5 完成情况

阶段 5 目标：

- 将 query 和检索到的上下文交给聊天模型
- 返回最终 answer
- 如果上下文不足，则拒绝不可靠回答

当前实现：

- 在 `app/rag.py` 中实现了：
  - `build_context()`
  - `is_context_insufficient()`
  - `answer_question()`
  - `run_ask_demo()`

当前策略：

- 先检索 top-k chunks
- 如果最佳检索结果分数过差，则直接返回：
  - `根据当前知识库内容，我暂时无法可靠回答这个问题。`
- 如果上下文足够，再将 query 和 context 一起发给聊天模型

验证命令 1：

```powershell
.\.venv\Scripts\python.exe -m app.rag ask "What is Chroma used for?"
```

验证结果 1：

- 成功输出基于知识库内容的答案
- 成功返回 `sources`

验证命令 2：

```powershell
.\.venv\Scripts\python.exe -m app.rag ask "Who is the CEO of Microsoft?"
```

验证结果 2：

- 返回拒答信息：
  - `根据当前知识库内容，我暂时无法可靠回答这个问题。`

这一步的意义：

- 项目已经具备了最小 RAG 闭环
- 不是单纯检索，也不是单纯聊天
- 而是“检索增强后再回答”

## 八、今日阶段总结（2026-03-26）

今天实际完成的核心进展：

- 跑通了本地向量索引
- 跑通了语义检索
- 跑通了最小 RAG 问答链路
- 定位并解决了 DashScope embeddings 与 LangChain 默认封装的不兼容问题

当前项目已经具备的能力：

- 读取本地文档
- 将文档切成 chunk
- 为 chunk 添加 metadata
- 调用 embedding 模型完成向量化
- 将向量写入 Chroma
- 根据 query 检索相关 chunk
- 基于检索结果生成 answer
- 返回来源文件 `sources`

明天继续时的起点：

- 不需要再改索引和检索主流程
- 直接进入阶段 7，整理 README 和项目说明

## 九、阶段 6 完成情况

阶段 6 目标：

- 实现 `POST /ask`
- 接收请求体中的 `question`
- 调用现有 `answer_question()`
- 返回 `answer` 和 `sources`

当前实现：

- 在 `app/main.py` 中增加了 `POST /ask`
- 使用 `AskRequest` / `AskResponse` 作为请求与响应模型
- 对输入问题做了 `strip()`，避免纯空白字符串请求
- 将 RAG 层和上游模型层的常见异常转换成明确的 HTTP 错误响应

接口行为：

- 正常情况下返回 `answer` 和 `sources`
- 当本地索引为空、环境变量缺失等本地问题发生时，返回 `400`
- 当上游模型认证失败、请求参数错误、限流、连接失败时，返回 `502` 或 `503`

联调文件更新：

- `test_api.http` 中补充了 `POST /ask` 示例
- `README.md` 中补充了索引命令、启动命令和接口示例

这一阶段完成后：

- 项目已经具备可直接演示的 API 入口
- 命令行版本和 FastAPI 版本共用同一套 RAG 核心逻辑

## 十、阶段 1（简单对话界面）完成情况

阶段目标：

- 增加一个简单可演示的对话页面
- 复用现有 `/ask` 接口，不改动核心 RAG 流程
- 展示回答内容和来源文件

当前实现：

- 在 `app/frontend/` 下增加了静态前端页面、样式和脚本
- 将 `/` 改为前端页面入口
- 新增 `/health` 作为健康检查接口
- 页面可发送问题到 `POST /ask`
- 页面会展示：
  - 用户问题
  - 助手回答
  - `sources` 来源标签
  - 请求中的加载状态与错误提示

当前边界：

- 这是“显示层面的聊天界面”
- 前端会保留聊天记录，但后端仍然按单轮 RAG 处理
- 还未实现上传文件和真多轮对话

这一阶段的意义：

- 项目从“可调用 API”升级成“可直接演示的网页应用”
- 为下一阶段的上传入口和多轮对话界面打好了 UI 基础

## 十一、阶段 2（上传文档入库）完成情况

阶段目标：

- 支持在页面中上传 `.txt` / `.md`
- 用 md5 判断文件是否重复
- 新文件切分后增量写入 Chroma
- 在界面里展示已入库文件列表

当前实现：

- 新增 `app/documents.py` 负责：
  - 文件校验
  - md5 计算
  - 重复检测
  - 文档注册表维护
  - 新文档增量向量化
- 新增 `GET /documents`
- 新增 `POST /documents/upload`
- 前端页面中增加了：
  - 文件上传入口
  - 上传状态提示
  - 已入库文件列表
- 上传支持的格式为：
  - `.txt`
  - `.md`

当前行为：

- 如果 md5 已存在，则返回 `duplicate`
- 如果是新文件，则保存到 `data/docs/` 并写入向量库
- 如果向量化过程中失败，会回滚刚写入的文件，避免文档目录和向量库状态不一致

这一阶段完成后：

- 知识库不再是纯静态目录
- 项目已经具备“上传文档 -> 切分 -> 向量化 -> 问答”的完整演示链路

## 十二、阶段 3（流式回答）完成情况

阶段目标：

- 将聊天回答改成流式输出
- 保留原有 `/ask` 作为非流式兜底接口
- 让前端在回答生成过程中逐段显示内容

当前实现：

- 在 `app/rag.py` 中增加了 `stream_answer_question()`
- 在 `app/main.py` 中新增 `POST /ask/stream`
- 流式接口采用 `text/event-stream`
- 事件类型包括：
  - `sources`
  - `delta`
  - `done`
  - `error`
- 前端聊天页默认改为调用 `/ask/stream`
- 页面会先创建一个空的助手消息，再随着 `delta` 事件不断追加文本

当前行为：

- 如果检索结果不足以可靠回答，会快速返回拒答文本，并仍按流式事件格式结束
- 如果上游模型或本地检索发生错误，前端会收到错误信息并在聊天区显示
- 原有 `POST /ask` 保持不变，仍可用于调试和兜底

这一阶段完成后：

- 页面交互从“等待整段答案后一次性出现”升级成“边生成边显示”
- 聊天体验明显更接近真实产品形态

## 十三、页面结构调整完成情况

本次调整：

- 将首页固定为聊天页
- 新增 `/library` 作为知识库管理页
- 顶部增加页面切换导航
- 语言切换在两个页面中保持一致

调整结果：

- `/` 只保留流式对话相关内容
- `/library` 只保留上传和文件列表管理
- 页面职责更清晰，后续继续加多轮或总结功能时不容易把界面做乱

## 十四、阶段 4（基础多轮对话）完成情况

阶段目标：

- 让聊天页支持最近几轮上下文承接
- 在后端先做问题改写，再做检索和回答
- 明确限制历史只用于补全语义，不用于继承用户行为指令

当前实现：

- 在 `app/schemas.py` 中为 `AskRequest` 增加了 `history`
- 在 `app/main.py` 中为 `/ask` 和 `/ask/stream` 接收并清洗最近对话历史
- 在 `app/rag.py` 中增加了：
  - `normalize_history()`
  - `format_history()`
  - `build_rewrite_messages()`
  - `rewrite_question()`
  - `prepare_answer_material()`
- 检索改为优先使用“改写后的独立问题”
- 最终回答阶段会同时拿到：
  - 原始当前问题
  - 改写后的检索问题
  - 最近对话历史
  - 检索到的上下文

当前边界：

- 前端当前只在内存里保留最近 4 轮对话并随请求发送
- 没有做会话持久化、会话切换和历史摘要
- 历史中的“以后都回答收到”这类行为指令会被显式忽略，只用来解析“它”“这个方法”这类语义承接

这一阶段完成后：

- 聊天页已经具备基础真多轮能力
- 追问类问题会先被补全再检索，比直接拿原句做检索更稳

## 十五、知识库删除功能完成情况

本次新增：

- 后端增加 `DELETE /documents?source=...`
- 知识库页为每个文件增加删除按钮
- 删除时会同步移除：
  - `data/docs/` 下的原文件
  - `document_registry.json` 中的注册信息
  - Chroma 中该 `source` 对应的向量记录

当前行为：

- 删除前会在前端弹确认框
- 删除成功后文件列表会立即刷新
- 删除失败时会在知识库页显示错误信息

这一阶段完成后：

- 知识库页面已经具备增删管理的基本能力
- 适合后续继续补“重建索引”或“文档总结”等管理功能

## 十六、聊天触发的文档总结功能完成情况

本次新增：

- 聊天接口支持识别“总结/概括/摘要 + 文件名”类请求
- 命中后不再走普通 RAG 检索问答，而是改走文档总结链路
- 流式接口会继续返回：
  - `sources`
  - `delta`
  - `done`

当前实现：

- 在 `app/rag.py` 中增加了文档总结意图识别
- 会根据问题里的文件名匹配 `data/docs/` 中的文档
- 文档较短时直接全文总结
- 文档较长时预留了分段总结再汇总的路径

当前能力：

- 支持在当前问题中直接写文件名来触发总结
- 也支持只说“总结这个文件”，再从最近一轮历史中回推目标文档
- 目标文档优先从 `sources` 字段定位，不够时再从最近历史正文中回捞文件名
- 总结链路目前没有单独页面，直接复用现有聊天界面

## 十七、依赖上下文的文档总结说法补充完成情况

本次补充：

- 支持在聊天里直接说“总结这个文件”或类似表达
- 后端会优先使用最近一轮回答中的 `sources` 来定位目标文档
- 如果上一轮没有显式 `sources`，会继续从最近历史正文里回捞文件名

本次意义：

- 文档总结体验和聊天页的多轮交互更一致
- 不需要每次都重复输入完整文件名
- 对真实演示更自然，尤其适合连续追问场景

## 十八、文档总结追问改写能力补充完成情况

本次补充：

- 支持“再压缩成3点”“再简短一点”这类依赖上一轮总结结果的说法
- 只要最近一轮助手消息仍然带有目标文档的 `sources`，后端就会继续走文档总结链路
- 这类追问不会退回普通 RAG 检索问答，而是继续针对原文档重新生成更符合新要求的总结

本次意义：

- 文档总结能力从“能触发一次”扩展成“能连续追问改写”
- 聊天页里的总结体验更接近真实助手，而不是一次性功能
- 适合演示把同一份文档逐步压缩成更短、更结构化版本

## 十九、今日进度记录（2026-03-26 补充）

今天继续完成了文档总结相关的两轮增强：

- 补上了依赖上下文的文档定位，支持“总结这个文件”这类说法
- 总结请求现在会优先读取最近一轮助手消息中的 `sources`
- 如果最近历史里没有 `sources`，会继续从最近消息正文里回捞文件名
- 进一步补上了总结追问改写，支持“再压缩成3点”“再简短一点”这类继续加工上一轮总结结果的说法
- 这类追问会继续走文档总结链路，不会退回普通 RAG 检索问答

今天同步完成的收尾工作：

- 更新了 `test_api.http`，补上依赖上下文的总结请求示例和总结追问示例
- 更新了 `README.md`，把总结能力的最新边界写清楚
- 本地验证了：
  - `resolve_summary_document()` 能从 `sources` 和历史正文中定位目标文档
  - `再压缩成3点` 能被识别为总结追问
  - `/ask` 接口能正常接收并透传带 `sources` 的历史
  - `python -m compileall app` 通过

当前状态：

- 聊天页里的文档总结已经支持“首次总结 + 上下文定位 + 连续追问改写”这三层体验
- 下一步如果继续做，比较自然的是补更细的总结风格控制，例如“一句话版”“面试表达版”“更口语化一点”


## 二十、轻量 Hybrid Retrieval 与性能优化完成情况（2026-03-27）

本轮主要目标：

- 不推倒现有 LangChain / Chroma / FastAPI 项目
- 在当前仓库基础上升级成“轻量 hybrid retrieval”版本
- 把路由、检索、总结路径从原先集中在 `app/rag.py` 的状态中拆出来
- 优先实现 parent-document summary path
- 控制复杂度，不引入 agent loop、GraphRAG、重型 parent-child 基础设施

本轮完成的结构调整：

- 新增 `app/router.py`
  - 负责对输入产出明确的 `RouteDecision`
  - 采用“规则优先 + LLM 补判”策略
  - 当前支持的 route 包括：
    - `direct_answer`
    - `local_chunk`
    - `local_summary`
    - `web_search`（仅预留枚举位）
- 新增 `app/validators.py`
  - 负责检索结果强度校验
  - 负责 parent candidate 强度校验
  - 负责判断 `local_chunk` 是否允许 fallback 到 `local_summary`
- 新增 `app/retrievers/chunk_retriever.py`
  - 抽离普通 chunk hybrid 检索逻辑
  - 统一封装：
    - 向量检索
    - 关键词检索
    - merge
    - neighbor expand
    - chunk answer material 准备
- 新增 `app/retrievers/parent_retriever.py`
  - 抽离 summary path 的父文档定位逻辑
  - 支持：
    - 文件名/历史 `sources` 直接定位
    - 检索子块后按 `source` 聚合父文档
- 新增 `app/pipeline.py`
  - 统一接管主流程编排
  - 当前主路径包括：
    - `direct_answer`
    - `local_chunk`
    - `local_summary`
    - `local_chunk -> local_summary -> refusal`

本轮完成的能力升级：

- summary path 已升级为轻量 parent-document 方案
  - 不是只靠文件名硬匹配
  - 而是支持“检索子块，返回父文档”
- 普通问答保留现有 hybrid chunk retrieval
  - 向量检索 + 关键词检索合并
- 扩大了 `direct_answer` 的边界
  - 除寒暄外，也支持翻译、润色、改写等安全的非知识库任务
- `direct_answer` 响应现在会显式提示：
  - ` [direct_answer] 以下回答未使用知识库。`
- 聊天前端支持 Markdown 显示
  - 助手输出中的标题、列表、加粗会正常渲染
- 长文 summary 的流式路径增加了 `progress` 事件
  - 可显示“正在拆分长文档”“正在处理第 N 段”“正在汇总最终总结”等状态
- summary intent 扩展到了：
  - `总结`
  - `概括`
  - `摘要`
  - `评价`
  - `分析`
  - `点评`
  - `解读`

本轮完成的性能优化：

- `load_documents()/split_documents()` 已增加缓存
  - 基于 `data/docs` 文件签名自动失效
  - 避免 keyword search、neighbor expand、parent summary 选择反复重新读盘和切块
- `local_chunk -> local_summary` fallback 已复用已有 child results
  - fallback 到 summary 时不再重复跑一轮 child 检索
  - 而是直接复用 `local_chunk` 阶段已经拿到的 `merged_results`
- 长文 summary 的 chunk 参数已调大
  - 减少 map-reduce 类长文总结时的模型调用次数

当前已明确的系统边界：

- 当前不做：
  - agent loop
  - GraphRAG
  - 多轮 autonomous planning
  - 重型 parent-child docstore 基础设施
  - 真正联网的 `web_search`
- 当前保留的最小可行版本是：
  - 单个本地 Chroma child-chunk 索引
  - parent = 原始文档文件
  - router 以规则为主，LLM 只做补判
  - 失败链路固定为：
    - `local_chunk -> local_summary -> refusal`

本轮验证结果：

- `python -m compileall app tests` 通过
- `python -m unittest discover -s tests -v` 通过
- 当前测试总数：`13`
- 已覆盖的新增点包括：
  - router 规则分流
  - parent-document summary path
  - summary progress 事件
  - direct answer debug notice
  - corpus cache 命中
  - fallback 复用已有 child results

当前仍然存在的已知说明：

- 当前环境仍是 Python `3.14`
- LangChain 仍会给出 Pydantic V1 兼容性 warning
- 这不影响本轮功能验证通过，但后续如果要长期稳定维护，仍建议迁移到 Python `3.11` 或 `3.12`

下一步建议：

- 优先继续优化 `rewrite_question()` 的调用策略
- 当前 `local_chunk` 路径在“存在 history”时会先调用问题改写模型
- 下一步应增加跳过条件，只在明显需要补全指代和上下文承接时才调用改写
- 优先考虑的规则包括：
  - 没有 history 时不改写
  - 当前问题里没有“它 / 这个 / 上面 / 刚才 / 那个方法”之类代词时不改写
  - 当前问题本身已经较完整时不改写

这样做的目标：

- 再减少一次不必要的模型调用
- 进一步缩短普通 `local_chunk` 问答的整体时延
- 在不明显增加复杂度的前提下继续提升演示体验

## 二十一、工具路由、联网搜索与性能问题记录（2026-03-28）

本轮主要目标：

- 把原先“按 route 分支”的流程升级成“按工具计划执行”的流程
- 在现有本地知识库问答与总结能力之外，补上真正可执行的 `web_search`
- 继续收紧普通问答链路中的不必要模型调用
- 记录在实际体验中暴露出来的时延问题，并形成明确优化方案

### 1. 本轮结构升级

本轮新增或重构的核心模块：

- `app/tool_router.py`
  - 新增统一工具路由层
  - 当前工具集合包括：
    - `direct_answer`
    - `local_doc_query`
    - `local_doc_summary`
    - `web_search`
- `app/pipeline.py`
  - 从原先“按 route 执行”改为“按 `ToolPlan` 执行”
  - 承担工具级分发、fallback 和流式输出
- `app/router.py`
  - 保留兼容层，旧的 route 语义仍可继续映射到新的工具路由

这一步完成后，项目从“路径路由”升级成了“工具路由”，后续接更多工具时结构会更稳。

### 2. 已完成的能力更新

#### 2.1 工具路由落地

当前系统已经不是简单的：

- `direct_answer`
- `local_chunk`
- `local_summary`

而是统一路由到：

- `direct_answer`
- `local_doc_query`
- `local_doc_summary`
- `web_search`

当前策略仍然保持：

- 规则优先
- LLM 只做少量模糊补判
- 默认落到本地文档查询

这样做的意义：

- 保持了速度和可控性
- 为后续多工具编排预留了稳定入口

#### 2.2 真正接入网页查询

此前 `web_search` 只是预留位，本轮已改成真实可执行能力。

当前实现：

- 接入阿里百炼 `qwen3.5-plus`
- 使用 OpenAI 兼容的 Responses API
- 已支持：
  - 联网搜索
  - 网页抓取
  - 来源提取
  - 流式返回

当前行为：

- 路由命中 `web_search` 时，会真正调用 Responses API
- 返回内容会统一成现有前端可以直接消费的：
  - `answer`
  - `sources`
  - `progress`

#### 2.3 前端体验补充

本轮前端也做了几项直接影响演示体验的调整：

- 聊天页改成更明确的对话式布局
  - 用户消息在右侧
  - 助手消息在左侧
  - 输入框固定在底部
- `sources` 展示语义调整为“主来源”
  - 不再把所有检索到的陪跑文件都展示出来
- 修复右上角“简体中文”语言切换文案的乱码问题
- 增加工具调用状态展示
  - 例如：
    - 正在联网搜索
    - 联网搜索失败
    - 正在汇总总结结果

### 3. 本轮已完成的性能优化

#### 3.1 普通问答不再默认先打一轮 LLM 路由

本轮排查后发现，普通文档问答此前经常会多一次无必要的 LLM 分类调用。

问题表现：

- 规则只覆盖了少数场景
- 大多数普通知识库问题都会先打一轮 LLM 路由
- 这会给几乎所有常规问题固定增加一次时延

解决方式：

- 将默认路由改为 `local_doc_query`
- 只有少数模糊能力类问题才允许 LLM 补判

优化结果：

- 普通知识库问答少了一次固定模型调用
- 普通请求的首包等待时间更短

#### 3.2 `rewrite_question()` 改为按需触发

此前的行为是：

- 只要请求里带了 history
- `local_doc_query` 基本就会先改写问题

问题在于：

- 很多问题本身已经是完整句子
- 但仍然会额外走一轮“问题改写”模型

解决方式：

- 增加 `should_rewrite_question()`
- 只在以下场景触发改写：
  - 明显代词承接
  - 省略式短追问
  - 很短的上下文依赖问题

优化结果：

- 普通多轮追问不再因为“顺手带了 history”就一律加一次模型调用
- 检索路径整体时延继续下降

#### 3.3 回答阶段收紧 history 注入

此前的行为是：

- 已经拿到了 `standalone_question`
- 但回答阶段仍然把整段 history 一起发给回答模型

问题在于：

- 改写和 history 语义有重复
- token 成本更高
- 历史提示注入面更大

解决方式：

- 先判断这次改写是否“真正完成转化”
- 只有当：
  - 原问题确实需要改写
  - 改写结果与原问题有实质差异
  - 改写后不再残留明显指代
  才允许回答阶段省略完整 history

优化结果：

- 回答阶段上下文更紧凑
- 保留了安全边界，避免“改写没改干净”就盲目丢历史

#### 3.4 `sources` 改成只返回高置信主来源

此前的行为是：

- 只要进入最终上下文构建的文件都会出现在 `sources`
- 即使答案主要只依赖其中一个文件，也会把其它陪跑文件一起展示出来

问题在于：

- 用户会误以为答案同时引用了多个文件
- 对总结和追问场景的文档定位也会造成干扰

解决方式：

- `sources` 只从高置信主结果中选 `top source`
- 不再使用邻居扩展后的结果集合来汇总来源

优化结果：

- 来源显示更符合用户直觉
- 总结追问和后续文档定位更稳定

### 4. 新发现的关键优化问题：总结后再联网确认时延偏长

在实际使用中，发现了一个更贴近真实演示的耗时问题：

- 先让系统总结一份文档
- 再基于上下文要求它联网搜索确认这个文档内容
- 整体等待时间明显偏长

当前问题的根因已经基本明确：

#### 4.1 现有 `web_search` 过于粗放

目前网页查询链路更接近“通用联网搜索”，而不是“针对上一轮文档总结做事实确认”。

问题主要体现在：

- 搜索请求默认是宽泛的网页查询
- 尚未把上一轮总结结果压缩成明确的验证 query
- 还没有形成“总结后确认”这种专用轻量执行链路

#### 4.2 网页查询默认同时打开搜索和网页抓取

当前网页查询链路默认倾向于：

- 先搜
- 再抓网页正文

问题在于：

- 对很多“只需要确认一个事实”的问题来说，这个成本偏高
- 简单确认问题本来不一定需要抓正文

#### 4.3 Thinking 开关过于激进

当前联网搜索链路倾向于使用较重的推理配置。

问题在于：

- 简单“确认一下是否属实”并不需要重推理
- 复杂配置会进一步拉长响应时间

### 5. 针对该问题的明确优化方案

为了解决“总结后再联网确认太慢”这个问题，当前已经形成了明确的后续优化方向：

#### 5.1 增加确认型搜索改写

目标：

- 当用户上一轮刚做过文档总结
- 这一轮又说“确认一下 / 核实一下 / 搜一下是否属实”
- 不直接把原问题当成宽泛网页查询

方案：

- 读取最近一轮助手总结
- 提炼成更短、更聚焦的验证 query
- 让联网搜索只核实最关键的 1 到 3 个事实

预期收益：

- 搜索范围更小
- 结果更聚焦
- 平均等待时间更短

#### 5.2 将网页抓取改成按需触发

目标：

- 先走轻量网页搜索
- 只有在：
  - 搜索结果不够回答
  - 缺少可靠来源
  - 需要正文证据
  时才追加网页抓取

预期收益：

- 对简单确认类问题显著减少平均耗时
- 把正文抓取成本只留给真正需要它的场景

#### 5.3 将 thinking 改成条件开启

目标：

- 简单确认类联网问题默认关闭或弱化 thinking
- 只有复杂分析、对比、趋势类联网问题再开启

预期收益：

- 降低简单联网问题的首包和总耗时
- 把重推理预算留给真正复杂的问题

### 6. 当前关于多工具执行的判断

目前系统已经具备：

- 单主工具执行
- 主工具失败后的顺序 fallback

但还不具备：

- 一次请求内显式串行执行多个独立工具
- 例如：
  - `local_doc_summary -> web_search`
  - `local_doc_query -> web_search`

当前判断：

- 如果只是实现“固定两步链路”的多工具编排，复杂度是可控的
- 现有 `tool_router + pipeline` 已经具备演进基础
- 不需要上升到通用 agent executor

当前最值得优先做的多工具方向是：

- `summary_then_web_verify`

也就是：

- 先总结文档
- 再基于总结结果做轻量联网确认

### 7. 当前项目状态总结

到目前为止，项目已经从最初的最小 RAG Demo，演进为一个较完整的本地知识库问答 Web 应用：

- 支持文档上传、删除和知识库管理
- 支持流式问答和基础多轮对话
- 支持普通文档问答
- 支持父文档级总结
- 支持网页查询
- 支持工具级路由
- 支持工具进度展示

当前最重要的后续优化重点已经比较明确：

- 优先优化“总结后联网确认”链路
- 先做轻量确认型搜索优化
- 再考虑是否需要升级成固定两步多工具编排
