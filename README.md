# askRAG

## 一句话描述

askRAG 把文档问答、任务记忆和可选联网放在同一条对话里，回答先依赖本地证据，再按需补充外部信息。

<img src="readmep/demo.gif" alt="README 演示" width="100%" />

> 演示素材来自本地真实运行快照。

## 页面预览

| 首页 | 知识库 | 记忆页 |
| --- | --- | --- |
| <img src="readmep/index.png" alt="首页" width="100%" /> | <img src="readmep/knowledge.png" alt="知识库页" width="100%" /> | <img src="readmep/memory.png" alt="记忆页" width="100%" /> |

> 三个页面都来自本地真实运行快照。

## 架构图

```mermaid
flowchart TB
    U[用户输入] --> G[路由判断]
    G -->|文档总结 / 文档问答| D[本地文档检索]
    G -->|明确联网 / 强制联网| W[直接联网搜索]
    G -->|任务 / 事实 / 偏好| M[记忆召回]

    D -->|证据足够| A[答案生成]
    D -->|证据不足| W
    M --> A
    W --> A

    A --> S[流式输出]
    A --> R[记忆写回]

    R --> M
```

## 核心设计决策

### 1. 文档和记忆分开，是为了让回答先有证据
文档回答看文件本身，记忆回答看用户的稳定状态。分开之后，系统才能判断一个问题是在查资料，还是在接着上次的任务继续聊。两者混在一起，最后只会让答案又慢又飘。

### 2. 先做便宜判断，是为了把耗时留给真正值得的请求
最常见、最明确的情况先分流，不让每个问题都压到完整检索和模型决策上。这样做不是为了“更聪明”，而是为了让对话更快、更稳。

### 3. 只保存会影响下一轮回答的内容
判断标准不是“说过没有”，而是“下一轮还用不用得上”。任务、事实、偏好优先保留；重复内容、噪音、临时信息不进长期层。记忆不筛选，只会越积越乱。

### 4. 主动写入和自动抽取分开，用户才知道自己存了什么
用户说“记住……”是明确写入；对话结束后的自动抽取更保守，也更容易回滚。两条路分开，系统才不会把“顺手整理”和“用户主动确认”混成一件事。

### 5. 删除要有边界，不能把长期事实一起误删
会话删掉后，相关的会话记忆应该一起清；但长期事实和偏好不能因为一条会话被误删。这个边界不说清楚，记忆越用越不可信。
## RFC 链接

- [RFC：项目总规划](PROJECT_PLAN.md)
- [RFC：当前执行计划](.project-loop/PLAN.md)
- [RFC：OpenViking 运行说明](openviking.md)

## 快速启动

### 1. 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 构建或刷新本地索引

```powershell
.\.venv\Scripts\python.exe -m app.rag index
```

### 3. 启动服务

```powershell
.\.venv\Scripts\python.exe app\main.py
```

### 4. 打开页面

```text
Chat:    http://127.0.0.1:8001/
Library: http://127.0.0.1:8001/library
```

### 5. 如果要完整体验记忆，再启动 OpenViking

<details>
<summary>展开查看 OpenViking 的完整安装与启动步骤</summary>

当前仓库里的文档问答可以单独跑；只有想体验长期记忆、任务状态回忆和 OpenViking-backed memory search 时，才需要把 OpenViking 一起装起来。

#### 5.1 安装 OpenViking

OpenViking 不在 `requirements.txt` 里，需要单独安装。最直接的做法是在当前虚拟环境里安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -U openviking
```

安装完成后，下面两个命令应该能找到：

```powershell
.\.venv\Scripts\openviking-server.exe --help
.\.venv\Scripts\ov.exe --help
```

如果你的环境里生成的是无扩展名命令，也可以改用：

```powershell
openviking-server --help
ov --help
```

#### 5.2 初始化配置目录

先创建 OpenViking 的默认配置目录：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.openviking" | Out-Null
New-Item -ItemType Directory -Force -Path ".\data\openviking_workspace" | Out-Null
```

推荐先尝试官方初始化向导：

```powershell
.\.venv\Scripts\openviking-server.exe init
```

这个命令会交互式生成 `ov.conf`。如果你的版本没有 `init`，就手动创建下面两个文件。

#### 5.3 准备 `ov.conf` 和 `ovcli.conf`

`ov.conf` 至少要告诉 OpenViking 工作目录放在哪里。最小示例可以是：

```json
{
  "storage": {
    "workspace": "D:/path/to/askRAG/data/openviking_workspace"
  }
}
```

把它保存到：

- `$env:USERPROFILE\.openviking\ov.conf`

然后创建 CLI 连接配置 `$env:USERPROFILE\.openviking\ovcli.conf`：

```json
{
  "url": "http://127.0.0.1:1933",
  "timeout": 60.0,
  "output": "table"
}
```

如果你已经用 `openviking-server init` 生成过 `ov.conf`，这里只需要确认里面的 `storage.workspace` 指向你当前仓库下的 `data/openviking_workspace`。

#### 5.4 设置环境变量并启动

```powershell
$env:OPENVIKING_CONFIG_FILE = "$env:USERPROFILE\.openviking\ov.conf"
$env:OPENVIKING_CLI_CONFIG_FILE = "$env:USERPROFILE\.openviking\ovcli.conf"
.\.venv\Scripts\openviking-server.exe
```

如果你想显式指定配置文件，也可以这样启动：

```powershell
.\.venv\Scripts\openviking-server.exe --config $env:OPENVIKING_CONFIG_FILE
```

#### 5.5 健康检查

另开一个终端，执行：

```powershell
$env:OPENVIKING_CLI_CONFIG_FILE = "$env:USERPROFILE\.openviking\ovcli.conf"
.\.venv\Scripts\ov.exe health
```

看到类似下面的结果，说明 OpenViking 已经可用：

- `status: ok`
- `healthy: true`

然后再启动 askRAG 主服务：

```powershell
.\.venv\Scripts\python.exe app\main.py
```

如果只想先验证本地文档问答，也可以先不启 OpenViking；`/library` 和聊天页本身仍然可以跑。

</details>

## 一些当前边界

- 文档证据和记忆上下文是分开的。
- 记忆写回是可控的，不是把每轮对话都当成长期事实。
- 联网是补充，不是默认主路由。
- 如果你只需要先验证本地文档问答，不必先把所有记忆相关服务都准备好。
