# Assignment 1：构建 Agent Harness（重点中文版）

> 根据原作业说明提取并翻译。重点保留：**作业目标、要求、TODO、运行命令、实验、评分、提交物**。

## 一、作业整体目标

本作业实现一个基于 **ReAct（Reasoning + Acting）** 的 Agent Harness，让 LLM 能够：

1. 观察环境；
2. 根据任务和历史信息进行推理；
3. 调用工具执行动作；
4. 获得 observation 后继续循环，直到任务完成。

三部分关系：

```text
Part 1：CodeAgent
LLM → ReAct Loop → Terminal Tools → 修复 Chess App

Part 2：Context Compaction
长 ReAct History → Working Memory → 控制 Context 长度

Part 3：ChessAgent
LLM → Chess Tools → simulate / programmatic tools → 下棋
```

---

# 二、环境与基本要求

## 1. 安装

项目使用 `uv`：

```bash
make setup
```

配置 Modal：

```bash
uv run modal setup
```

配置环境：

```bash
cp .env.example .env
```

主要变量：

```dotenv
OPENAI_BASE_URL=<OpenAI-compatible base URL>
OPENAI_API_KEY=...
OPENAI_MODEL=deepseek/deepseek-v4-flash-0731
OPENAI_MAX_RETRIES=5
```

默认模型：

```text
deepseek/deepseek-v4-flash-0731
```

## 2. Billable

Modal 和 LLM API 的运行会消耗额度。

运行真正的 Agent 前先：

```bash
make doctor
```

检查是否有遗留 Modal Sandbox：

```bash
modal container list
```

异常时：

```bash
modal container stop <container ID>
```

## 3. Public Tests

```bash
make test
```

快速、离线、不消耗额度。

**通过 public tests 不代表作业完全正确**；private tests 还会检查 cleanup、malformed skills、并行 chess calls、transport errors、patch replay、真实 Modal integration 等。

---

# 三、必须遵守的规则

不要修改：

```text
tests/
tasks/
chess_app/
```

另外：

- 不要修改项目提供的 logging / cleanup；
- 不要在子类中复制共享的 ReAct loop；
- 不要硬编码题目的答案；
- Agent 应自行生成 patch / chess moves；
- **绝对不要暴露、记录或提交 API keys 等 credentials**；
- 不同 Agent 只能使用作业规定的工具。

---

# Part 1：实现 Coding Agent 并修复 Chess App

目标：实现通用 `Agent` ReAct Loop，再让 `CodeAgent` 在 terminal 环境中修复 Chess App 的 Bug。

## 1. Prompt Construction

核心方法：

```python
Agent.build_prompt()
```

消息基本结构：

```text
system
↓
user
↓
assistant
↓
tool
↓
assistant
↓
tool
...
```

需要正确维护：

- system instructions；
- task specification；
- 历史 reasoning；
- actions；
- tool observations。

### TODO 1.1.a

实现 Agent 状态维护，并构造完整 prompt。

要求：

- 包含 standing instructions；
- 包含 task specification；
- 包含历史 interaction；
- 包含 observations、reasoning、actions；
- 必须是 **domain-agnostic**，不能只针对 CodeAgent。

### TODO 1.1.b

构造 `CodeAgent` 的 system prompt 和 task prompt。

system prompt **必须包含**：

```text
<system_information>
{
  "machine": <machine>,
  "release": <release>,
  "system": <system>,
  "version": <version>
}
</system_information>
```

这些值来自环境。

---

# Part 1.2：实现 ReAct Loop

核心：

```python
Agent.run()
```

### TODO 1.2

实现：

```text
构造 Prompt
↓
请求 LLM
↓
获取 assistant action
↓
解析 tool calls
↓
执行 tools
↓
获得 observations
↓
进入下一轮
```

必须：

- 正确判断任务是否完成；
- 设置 `Agent.finished`；
- 超过 `step_limit` 时抛出 `StepLimitError`。

---

# Part 1.3：执行 Coding Tools

CodeAgent 支持：

```text
execute
send_message
```

工具执行必须通过：

```python
Environment.execute()
```

确保代码运行在正确的 Modal Sandbox。

### TODO 1.3

需要：

1. 让两个工具可被 Agent 调用；
2. 解析每个 tool call；
3. 执行工具；
4. 每个 call 返回一个 observation：

```python
{
    "role": "tool",
    "tool_call_id": "...",
    "content": "..."
}
```

一次 assistant response **可能包含多个 tool calls**，必须全部处理。

对于 malformed JSON、unknown tools：

> 不要直接抛异常；要转换成可恢复的 observation，让 Agent 自己处理。

---

# Part 1.4：Skill Discovery

项目使用 Skill 告诉 Agent 如何提交 solution。

提交协议要求 Agent 最终生成：

```text
patch.txt
```

Skill 位于：

```text
tasks/code-skills/submit-task
```

这里训练的是 **Progressive Disclosure**：

```text
System Prompt
↓
Skill 名称 + description
↓
Agent 调用 invoke_skill
↓
获取完整 SKILL.md
```

### TODO 1.4

实现：

- 验证 `skills_path`；
- 遍历 child directories；
- 找到每个 `SKILL.md`；
- 解析 YAML frontmatter；
- 按 `name` 建立 mapping；
- 保存 metadata；
- 保存完整 skill content；
- duplicate names 必须报错；
- malformed / missing frontmatter 必须报错。

如果存在 Skill，要把 description / metadata 放入 system prompt。

---

# Part 1.5：运行 CodeAgent

```bash
make run-code-agent
make check-part1
```

Agent 处理：

```text
tasks/chess-terminal-move/problem_statement.md
```

在：

```text
/testbed
```

中：

1. reproduce failure；
2. 修复；
3. 验证；
4. 生成 patch。

产生：

```text
artifacts/fix.patch
artifacts/part1-trajectory.json
```

`make check-part1` 会把 patch 应用到新的 testbed，并运行 regression + chess-app tests。

**不要直接修改 `chess_app/`。**

---

# Part 2：Context Compaction

长 ReAct transcript 会导致：

- token 成本增加；
- context window 被占满；
- Agent 后期无法有效利用历史信息。

因此需要将旧历史压缩成 working memory。

## TODO 2.1：`compact_context`

核心：

```python
Agent.compact_context()
```

要求模型生成简洁、事实性的 working memory。

总结应保留：

- objective；
- constraints；
- files；
- commands；
- edits；
- concrete results；
- failed approaches；
- tests；
- blockers；
- next action。

必须保留：

- 原始 system message；
- 原始 task message；
- 至少最新完整 assistant action；
- 该 action 对应的全部 tool observations。

压缩后必须真正减少 `build_prompt()` 输出的 prompt 长度。

**不要修改：**

```python
api_prompt
api_responses
```

它们用于 bookkeeping / evaluation。

## TODO 2.2：自动触发

在每次新的 action request 前调用：

```python
maybe_compact_context()
```

---

# Part 2.3：SWE-bench 实验

使用 6000 token threshold：

```bash
COMPACT_THRESHOLD=6000 SWEBENCH_PATCH=artifacts/django__django-15368.patch SWEBENCH_TRAJECTORY=artifacts/django__django-15368-trajectory.json make run-swebench-agent INSTANCE=django__django-15368
```

检查：

```bash
make check-swebench INSTANCE=django__django-15368
```

还需要运行 no-compaction baseline：

```bash
COMPACT_THRESHOLD=0 SWEBENCH_PATCH=artifacts/django__django-15368-baseline.patch SWEBENCH_TRAJECTORY=artifacts/django__django-15368-baseline-trajectory.json make run-swebench-agent INSTANCE=django__django-15368
```

最终要求：

- compacted run 至少触发一次 compaction；
- active context 必须明显减少；
- patch 必须通过 `check-swebench`；
- 比较 compaction / no-compaction 的 token usage；
- 写入：

```text
artifacts/token-usage-analysis.md
```

解释两种方法的 context usage 趋势和 trade-offs。

---

# Part 3：实现 ChessAgent

复用 Part 1 / Part 2 的 Agent Loop。

ChessAgent：

- 执 White；
- server 的 deterministic bot 执 Black；
- 每次合法 White move 后，server 自动回复 Black。

---

# Part 3.1：`play_move`

定义 OpenAI function tool：

```text
play_move
```

### TODO 3.1.a

必须只有：

```text
move: string
```

一个 required 参数。

使用 UCI notation，例如：

```text
e2e4
e7e8q
```

不允许额外参数。

### TODO 3.1.b

实现：

```python
_play_move()
```

请求：

```text
POST /api/move
```

body：

```json
{
  "move": "<uci move>"
}
```

错误必须返回：

```text
<chess_error>...</chess_error>
```

需要处理：

- malformed JSON；
- arguments 不是 object；
- 缺失 / 非 string 的 fen；
- 非 string move；
- server 拒绝 position；
- server 拒绝 move；
- transport failure。

成功后：

- `format_state`；
- 更新 `last_state`；
- 根据 `game_over` 更新 `finished`；
- observation 使用原始 `tool_call_id`。

### 并行调用

由于一次 move 会改变棋盘：

> 一组 parallel calls 最多执行一个 `play_move`，其余必须 recoverably reject。

初始 / 成功后的 observation 已包含：

- board；
- Black reply；
- next legal moves。

不需要单独的 board-reading tool。

---

# Part 3.2：运行 ChessAgent

```bash
make run-chess-agent
```

产生：

```text
artifacts/part3-trajectory.json
artifacts/game-result.json
```

输出的 HTTPS URL 可以查看棋盘。

---

# Part 3.3：Observation A/B Experiment

比较两种 observation：

### No Legal Moves

只给 board。

### Legal Moves

给 board + legal moves。

分别测试：

```text
DeepSeek
GPT-OSS
```

共四次：

```bash
make run-obs-deepseek-no-legal
make run-obs-deepseek-legal
make run-obs-gpt-oss-no-legal
make run-obs-gpt-oss-legal
```

每次记录：

- `play_move` 总调用次数；
- illegal calls 数量；
- invalid-move rate；
- 是否达到 `game_over: true`。

报告：

```text
artifacts/observation-experiment.md
```

**评分重点是实验和证据，不要求 Agent 一定赢棋。**

---

# Part 3.4：`simulate_move`

目的：

> 模拟走棋，但不改变真实棋盘。

接口：

```text
POST /api/simulate
```

两种用法：

```text
simulate_move(fen)
simulate_move(fen, move)
```

只传 FEN：返回该位置和合法 moves。

传 FEN + move：模拟一 ply。

返回 JSON 应包含可供 Python 使用的：

```text
fen
squares
turn
legal_moves
terminal-result fields
```

### TODO 3.3.a

定义：

```text
SIMULATE_MOVE_TOOL
```

### TODO 3.3.b

实现：

```python
_simulate_move()
```

需要：

- 解析参数；
- 调用 `/api/simulate`；
- 返回 serialized JSON；
- 错误包装成 `<chess_error>`。

处理：

- malformed JSON；
- 非 object 参数；
- missing / non-string fen；
- non-string move；
- server rejection；
- transport failure。

必须使用：

```python
ChessAgent.chess_client
```

---

# Part 3.5：`run_python`

这是程序化 Tool Calling。

Agent 可以：

```text
run_python(code)
```

代码中调用：

```python
simulate_move(...)
play_move(...)
```

从而执行复杂规划。

### TODO 3.4

实现：

```text
RUN_PYTHON_TOOL
_run_python()
```

**模型生成的 Python 不能在本地 Agent process 执行。**

必须通过 Sandbox：

```text
python /opt/assignment/sandbox_python.py <port> <base64-code>
```

返回：

```json
{
  "stdout": "...",
  "stderr": "...",
  "error": "..."
}
```

直接返回这个 JSON 字符串。

如果 sandbox command 本身失败，返回：

```text
<chess_error>...</chess_error>
```

如果只是模型代码抛 Python exception，则属于正常 sandbox execution，保留在 `error` 字段。

### 重要：执行后刷新状态

因为 Python 代码可能已经调用：

```python
play_move(...)
```

所以每次 `run_python` 后必须：

1. 重新读取 live board；
2. 更新 `last_state`；
3. 更新 `finished`；
4. 将最新 state 加入 observation。

否则 Agent 可能重复执行已经完成的 move。

运行：

```bash
uv run assignment-play-chess --programmatic-tools
```

---

# Part 3.6：Chess Skill

项目提供：

```text
tasks/chess-skills/select-move
```

目标是让 Agent 使用：

```text
Skill
↓
simulate_move
↓
搜索 / 分析
↓
选择 move
↓
play_move
```

ChessAgent 需要实现：

```python
_invoke_skill(skills, arguments)
```

并且只有 skills 加载成功时才注册：

```text
INVOKE_SKILL_TOOL
```

### TODO 3.5

解析 `invoke_skill` 参数并返回对应 skill 的完整内容。

错误：

```text
<chess_error>{message}</chess_error>
```

运行：

```bash
uv run assignment-play-chess   --programmatic-tools   --skills-path tasks/chess-skills   --trajectory artifacts/part3-python-skill-trajectory.json
```

trajectory 必须体现：

```text
invoke_skill
↓
run_python
↓
simulate_move
↓
搜索 / 选择
↓
play_move
```

其中 `play_move` 应由 `run_python` 中的代码执行。

不要求游戏结束，也不要求赢棋。

---

# 四、评分重点

总分：**100 分**

## Part 1

| 内容 | 分值 |
|---|---:|
| Prompt construction / action-observation history | 6 |
| ReAct lifecycle / recovery / step limit / cleanup / trajectory | 6 |
| Coding-tool dispatch / errors / patch submission | 6 |
| Chess patch 正确应用并通过测试 | 8 |
| Skill discovery / invoke_skill | 4 |

## Part 2

| 内容 | 分值 |
|---|---:|
| Compaction trigger + model-generated summary | 6 |
| 保留原始 instructions + 最新完整 tool step | 6 |
| Context 明显减少且可审计 | 4 |
| Token usage analysis | 4 |
| SWE-bench patch 通过 FAIL_TO_PASS / PASS_TO_PASS | 8 |

## Part 3

原评分表包含：

| 内容 | 分值 |
|---|---:|
| `play_move` schema / registration | 4 |
| `play_move` state update / errors | 6 |
| 基础 chess trajectory 达到 terminal state | 4 |
| 四组 Observation A/B 实验 | 4 |
| Observation A/B report | 4 |
| `simulate_move` | 6 |
| `run_python` sandbox / state refresh / errors | 6 |
| Skill + programmatic search + live move trajectory | 6 |

> 注：原作业表中 Part 3 行项目分值之和与其标注的 Part 3 总分存在不一致；这里保留原始分项，不自行修改。

另外：

```text
Complete, parseable, rule-compliant submission = 2 分
```

---

# 五、最终提交内容

提交一个 ZIP，包含：

```text
src/
artifacts/
AI_USAGE.md
```

## `src/`

提交：

```text
src/assignment/agent/
```

中的修改文件。

如果修改了：

```text
src/assignment/prompts.py
```

才提交它。

## `artifacts/`

必须包含：

```text
fix.patch
part1-trajectory.json

django__django-15368.patch
django__django-15368-trajectory.json
token-usage-analysis.md

part3-trajectory.json
game-result.json

part3-no-legal-moves-deepseek.json
part3-no-legal-moves-deepseek-result.json
part3-legal-moves-deepseek.json
part3-legal-moves-deepseek-result.json

part3-no-legal-moves-gpt-oss.json
part3-no-legal-moves-gpt-oss-result.json
part3-legal-moves-gpt-oss.json
part3-legal-moves-gpt-oss-result.json

observation-experiment.md
part3-python-skill-trajectory.json
```

## 不要提交

```text
.env
API keys / credentials
tests/
tasks/
submodule contents
instructor files
```

## `AI_USAGE.md`

说明：

- 使用了哪些 AI 工具；
- 每个工具如何用于本作业。

虽然该文件本身不计分，但课程会通过 quiz 检查你是否真正理解提交的代码。

---

# 六、整份作业最核心的知识链

可以把作业压缩成下面这条链：

```text
                 ┌──────────────┐
                 │     LLM      │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ ReAct Loop   │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ Tool Calling │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ Environment  │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ Observation  │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ Context/Mem. │
                 └──────┬───────┘
                        │
                        └────→ LLM
```

三部分分别解决：

- **Part 1：Agent 怎么行动？**
- **Part 2：Agent 怎么在长任务中管理上下文？**
- **Part 3：Agent 怎么通过工具、模拟和程序执行进行更复杂的规划？**

最终训练的是一个完整 Agent Harness 的工程能力，而不仅仅是写一个“会下棋”的程序。
