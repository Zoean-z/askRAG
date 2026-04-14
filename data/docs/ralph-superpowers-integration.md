---

## 核心理解：Ralph 和 Superpowers 分别是什么

| | Ralph | Superpowers |
|--|--|--|
| 角色 | **引擎** — 自动循环调用 Claude CLI | **方法论** — 在每次调用中指导 Claude 怎么工作 |
| 解决什么问题 | "持续跑"：自动循环、速率限制、退出检测、熔断器 | "跑得好"：brainstorm、TDD、debugging、code review |
| 没有对方会怎样 | 有引擎但没纪律，Claude 可能瞎干 | 有纪律但得你手动开一次次会话 |

**1+1 > 2 的关键：Ralph 当司机持续开车，Superpowers 当导航确保方向正确。**

---

## 第一步：安装 Ralph

你在 Win11 上用的是 Git Bash / WSL，在 ralph-claude-code 目录下：

```bash
cd /d/toffee-study-with-ai/ralph-claude-code
bash install.sh
```

安装后确认：
```bash
ralph --help
```

如果 `ralph` 命令找不到，把 `~/.local/bin` 加到 PATH：
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## 第二步：在你的项目中启用 Ralph

```bash
cd /d/你的项目目录
ralph-enable
```

这会创建 `.ralph/` 目录，包含 PROMPT.md、fix_plan.md、AGENT.md 等。

---

## 第三步（关键）：让 PROMPT.md 利用 Superpowers

这是 **1+1 > 2** 的核心。编辑 `.ralph/PROMPT.md`，在 "Key Principles" 部分加入 superpowers 的使用指令：

```markdown
## Superpowers Integration (MANDATORY)

You have superpowers skills installed. You MUST use them:

### Before implementing any feature:
1. Use `superpowers:brainstorming` skill to explore requirements and design
2. Use `superpowers:writing-plans` to create an implementation plan
3. Use `superpowers:test-driven-development` to write tests first

### During implementation:
4. Use `superpowers:systematic-debugging` when encountering bugs
5. Use `superpowers:dispatching-parallel-agents` for independent tasks

### After implementation:
6. Use `superpowers:requesting-code-review` to review completed work
7. Use `superpowers:verification-before-completion` before claiming done

### Rule: Never skip brainstorming or TDD. Ralph loops are expensive — 
### doing it right the first time saves loops.
```

---

## 第四步：配置 .ralphrc

在项目根目录创建 `.ralphrc`：

```bash
# Claude CLI command
CLAUDE_CODE_CMD="claude"

# 每小时最大调用次数
MAX_CALLS_PER_HOUR=50

# 每次 Claude 执行的超时时间（分钟）
CLAUDE_TIMEOUT_MINUTES=20

# 输出格式
CLAUDE_OUTPUT_FORMAT=json

# 启用 session continuity（让 Claude 记住上一轮做了什么）
CLAUDE_USE_CONTINUE=true

# 工具权限
CLAUDE_ALLOWED_TOOLS="Write,Read,Edit,Bash(git add *),Bash(git commit *),Bash(git diff *),Bash(git log *),Bash(git status),Bash(npm *),Bash(npx *)"

# 熔断器自动恢复
CB_COOLDOWN_MINUTES=30
CB_AUTO_RESET=false
```

---

## 第五步：编写 fix_plan.md

把你的实际任务写进 `.ralph/fix_plan.md`：

```markdown
# Fix Plan

## High Priority
- [ ] 实现用户认证模块
- [ ] 创建 API 路由层

## Medium Priority
- [ ] 添加错误处理中间件
- [ ] 编写集成测试

## Completed
- [x] 项目初始化
```

---

## 第六步：启动

```bash
# 推荐用 tmux 监控模式
ralph --monitor

# 或者不用监控
ralph
```

---

## 协同工作流程图

```
Ralph Loop 启动
  │
  ├─ 读取 fix_plan.md → 选择最高优先级任务
  │
  ├─ Claude CLI 被调用（带 superpowers）
  │   │
  │   ├─ brainstorming skill → 理解需求
  │   ├─ writing-plans skill → 制定计划
  │   ├─ TDD skill → 先写测试
  │   ├─ 实现功能
  │   ├─ systematic-debugging → 修 bug
  │   ├─ verification → 验证完成
  │   └─ 输出 RALPH_STATUS 状态块
  │
  ├─ Ralph 分析响应
  │   ├─ 检查退出信号
  │   ├─ 更新熔断器状态
  │   └─ 检查速率限制
  │
  └─ 下一轮循环（或退出）
```

**没有 Superpowers 时**：Ralph 跑 10 轮，3 轮在瞎折腾，2 轮在重复测试
**有了 Superpowers 时**：每轮都有纪律 — brainstorm 先想清楚，TDD 先写测试，review 确认质量。**可能 5 轮就完成原来 10 轮的工作。**

