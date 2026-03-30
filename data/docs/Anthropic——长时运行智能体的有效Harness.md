# 长时运行智能体的有效Harness

> 来源：[Anthropic Engineering](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Justin Young, 2025-11-26

---

## 核心问题

复杂任务跨越多个上下文窗口时，智能体面临"换班工程师"困境——每个新session对之前发生的一切完全失忆。Compaction不够：它不总能传递足够清晰的指令给下一个session。

**两个典型失败模式**：
1. **一次性尝试（one-shotting）**：试图在单次context中完成整个应用 → context耗尽 → 半成品无文档 → 下一个session猜测+修复
2. **过早宣布完成**：看到已有进展 → 声称任务完成

---

## 解决方案：双智能体架构

### 初始化智能体（Initializer Agent）

仅在第一次session运行，职责：
- 将用户的高层prompt展开为**结构化feature清单**（JSON格式，200+条，每条初始标记为failing）
- 创建 `init.sh`（启动开发服务器+基础端到端测试）
- 创建 `claude-progress.txt`（跨session进度日志）
- 初始git commit

**为什么用JSON而非Markdown**：模型不太会意外修改/覆盖JSON文件中的内容。Feature清单用 `"passes": false` 字段，coding agent只被允许将其改为true。

### 编码智能体（Coding Agent）

每个后续session，执行固定启动序列：
```
1. pwd → 确认工作目录
2. 读取 git log + claude-progress.txt → 理解当前状态
3. 读取 feature_list.json → 选择最高优先级的未完成feature
4. 运行 init.sh → 启动服务器 + 基础验证（捕捉遗留bug）
5. 实现一个feature → git commit + 更新progress → 退出
```

**关键设计决策**：
- **每次只做一个feature**（解决one-shotting）
- **session结束时必须留下干净状态**（可合并级别的代码）
- **用git做版本回退**（而非尝试修复烂代码）
- **用浏览器自动化做端到端测试**（Puppeteer MCP），不只是curl/单元测试

---

## 失败模式与对策矩阵

| 问题 | 初始化智能体对策 | 编码智能体对策 |
|------|-----------------|---------------|
| 过早宣布项目完成 | 创建feature清单（全部标failing） | 每次session读取清单，选一个做 |
| 留下bug/未文档化进度 | 初始化git仓库+progress文件 | 开始时读progress+git log+跑基础测试；结束时commit+更新progress |
| 未充分测试就标完成 | 配置feature清单 | 用浏览器自动化自验所有feature |
| 不知道怎么跑应用 | 写init.sh | 开始时读init.sh |

---

## 未解决问题

1. **单智能体 vs 多智能体**：是否应有专门的测试agent、QA agent、清理agent？
2. **领域泛化**：当前方案针对全栈Web开发优化，科学研究/金融建模等领域是否适用？
3. **视觉局限**：Claude无法通过Puppeteer看到浏览器原生alert弹窗，依赖这些的feature更容易出bug

---

## 与库内文档的连接

- **双智能体架构** 是 `HARNESS_ENGINEERING_GUIDE` 的直接理论来源——feature清单、progress.txt、init.sh、单feature原子性在两篇文档中完全同构
- **feature清单用JSON** 是对 `HARNESS_ENGINEERING_GUIDE` 中 `features.json` 的直接解释
- **过早宣布完成** 对应 `Sprint1_根因地图` 中 R4（自我验证盲区）+ 代偿行为（看起来完成了但实际没有）
- **跨session状态外化** 验证了 `61局限` 中 #2（跨session遗忘）的工程对策：不要依赖模型记忆，把状态写到文件里
- OpenAI的文章（同文件夹）将这些原则推到了更大规模——增加了渐进式披露、架构强制、自动垃圾回收
