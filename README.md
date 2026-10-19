# nooa-patterns

NOOA 之上的轻量协作模式与组合库，工作名暂定 `nooa-patterns`。
本项目是独立 Python 扩展包，通过 NOOA 的公开 API 调用 Agent。
NOOA 负责 Agent 执行、策略、模型调用、对象状态、原生校验和事件历史；
本项目负责成员调用边界、显式参数桥接与普通 Python 协作逻辑。

## 当前里程碑：M1

M1 提供两个手写顺序流程、`TeamMember` / `Pattern` 协议及基线测试。
下文描述首版的完整执行契约：`as_member` 与 `Sequential` 在 M2 实现，`Team` 在 M3 实现；
组合示例、等价测试及真实 NOOA Agent 集成在 M4 完成。当前包仅导出两个协议。

完整的 [M0–M4 实施计划与验收基线](docs/IMPLEMENTATION_PLAN.md)
记录了交付物、测试命令、当前进度和逐阶段用户确认规则；review 前请先阅读。
M1 已完成并经 reviewer 复审通过，目前等待用户确认进入 M2。

## 核心抽象

采用“两个角色 + 一个递归规则 + 一个正交维度”：

- **Agent（叶子角色）**：使用现有 NOOA Agent 实例的业务能力，本项目不定义同名 Agent 基类。
  NOOA Agent 基类没有 `execute`；若具体 Agent 未实现成员协议，需通过显式异步桥接函数和
  `as_member` 适配为 `TeamMember`。普通 Python 对象满足成员协议也可以参与。
- **Team（容器角色）**：普通 Python 容器，持有成员和 Pattern，自身实现
  `execute(task, context)`，因此可以作为其他 Team 的成员，递归嵌套且保留各自的 Pattern。
- **递归规则**：概念上 `Team = [Agent | Team] × Pattern`；调用边界上
  `Team = [TeamMember] × Pattern`，其中叶子已满足协议或经过显式适配，子 Team 自身满足协议。
- **Pattern（正交维度）**：定义成员之间如何协作，与“谁包含谁”的结构分开。
  可以保留成员结构、更换 Pattern，但仍须检查业务输入输出兼容性，不保证任意替换。

Team 的 `execute` 委托以下入口，并直接返回其业务结果：

```python
async def run(self, members: Sequence[TeamMember], task: Any, context: Any) -> Any: ...
# 调用方式：await pattern.run(members, task, context)
```

Pattern 提供 `run`，TeamMember 提供 `execute`；满足 Pattern 协议不代表满足成员协议。
Pattern 复用下文的数据、引用、异常与副作用约定，不是 TeamMember 的子类型。
M1 只定义这两个协议；上述适配与容器行为由后续里程碑实现。

## 运行手写基线与测试

需要 Python 3.12 或 3.13。手写示例只使用标准库：

```powershell
python examples/manual_flows.py
```

使用 uv 创建隔离环境，从 `pyproject.toml` 安装 M1 的开发依赖并运行。
缓存保存在本项目的 `.uv-cache` 中：

```powershell
uv --cache-dir .uv-cache venv --python 3.12
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe --group dev
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe --no-deps --editable .
.venv/Scripts/python.exe examples/manual_flows.py
.venv/Scripts/python.exe -m pytest
```

M1 使用 `--no-deps` 验证本地包构建与导入，暂不安装 NOOA 运行时。
pytest 配置会加入 `src` 和项目根目录，以便验证标准库协议与手写基线。
`pyproject.toml` 已声明 NOOA 的 Git 依赖；
后续 NOOA 集成里程碑将安装并验证该依赖。完整开发环境使用 `uv sync`。

Windows 管道输出中文时可使用 `python -X utf8 examples/manual_flows.py`。
若 pytest 缓存目录不可写，可用 `python -m pytest -p no:cacheprovider` 完成测试，
该选项仅关闭测试缓存，不改变测试收集或断言。

## 两个手写顺序流程

| 流程 | 入口输入 | 第一步产物 | 最终业务结果 | 共享 context |
| --- | --- | --- | --- | --- |
| A：资料分析 → 报告生成 | 资料字符串 | `Analysis(summary, evidence)` | 报告字符串 | 读者、来源名称、调用记录 |
| B：变更方案 → 审查意见 | 变更目标字符串 | `ChangePlan(goal, steps)` | `ReviewOpinion(accepted, comment)` | 审查要求、调用记录 |

实现位于 `examples/manual_flows.py`。两个流程都直接写两个 `await`：
等待第一步，把返回值作为第二步的输入，传递同一 context，返回第二步结果。
fake 函数使用固定测试数据，不访问模型。流程 B 的不通过意见也只是业务结果。
`events` 由业务函数主动写入，是本示例的观察记录，不是库注入的 NOOA 历史。

它们证明存在重复的顺序协调逻辑；是否值得继续扩展独立库，仍需组合原型和应用验证。

## 执行契约 v0

### 1. 调用签名与弱类型边界

成员提供可等待的方法：

```python
async def execute(self, task: Any, context: Any) -> Any: ...
```

**这是弱类型协议，兼容性由调用者和测试保证，不继承 NOOA 的类型校验契约。**

**通过适配器调用 NOOA 公开方法时，该方法原有校验仍生效。**
本协议不提供跨成员的类型推导、兼容性检查或自动转换。
业务函数仍应使用具体类型，`Any` 只表示组合边界暂未强制类型兼容。
协议也不承诺在运行前验证成员的完整签名或业务语义。
泛型协议和可选校验钩子留待实际需求证明必要后考虑。

### 2. task 与顺序交接

`task` 表示此次成员调用的业务输入。Sequential 的规则为：

```text
r₀ = task
rᵢ = await memberᵢ.execute(rᵢ₋₁, context)
返回 rₙ
```

第一个成员接收调用者传入的原始 task，后续成员接收前一个成员的返回值。
“原始”指入口收到的对象，不表示不可变快照。
库不对 task 序列化、复制或转换类型，也不禁止成员修改可变输入。
返回值可以与输入或 context 内的对象互为别名。
需要原始任务的后续成员，应由调用者显式通过 context 或业务产物提供；
保存引用本身不会创建快照。

### 3. 应用 context

context 是调用者创建、持有和管理的应用级对象，可以是字典、dataclass 或其他对象。
所有成员接收同一个 context 引用，成员修改对其他成员可见。
库不复制、不持久化它，也不自动注入 `last_result`、`history`、原始任务等字段。
业务成员和显式适配函数可以有意修改 context。

这里的 context 与 NOOA Agent 的 `agent.context`（提示词上下文）无关，不自动同步。
失败或取消时，context 上已经发生的修改不会回滚。

### 4. 返回值与递归调用边界

叶子成员与 Team 都返回“自身此次调用的业务结果”，处于同一成员调用边界。
这不要求相同的 Python 类型、数据形状或任务粒度。
Pattern 决定如何产生业务结果；Team 直接返回该结果，不额外包装统一执行状态对象。
业务结果可以是标量、对象或集合。

子 Team 的输出仍须满足外层后续成员的输入要求。
例如子 Team 内部是“资料字符串 → Analysis → 报告字符串”，
它对外就是“资料字符串 → 报告字符串”，下游不能继续将输出当作 Analysis。
相同调用签名不保证业务兼容，更换 Pattern 也不保证下游可以直接复用。

### 5. None

`None` 是普通业务结果，逐级原样传递；最后一步返回 `None`，Team 就返回 `None`。
它不表示跳过、提前结束、保留上一结果或错误。
某一步只修改 context 且希望继续传递当前输入时，应显式 `return task`。

### 6. 异常、取消与副作用

成员抛出的异常直接向上传播，库不吞异常、不包装为通用错误。
`CancelledError` 传播后不再启动后续成员。
库不额外重试整个流程，避免重复副作用；成员或 NOOA 策略自身的重试仍按其机制运行。

不回滚适用于 context、输入对象、Agent 状态及已发生的外部副作用。
取消是协作式的，库不能强制终止阻塞、屏蔽取消或自行创建后台任务的成员。
首版仅管理它直接等待的调用链。

### 7. 超时

首版没有内置超时参数。调用者可以用 `asyncio.timeout` 包裹整个调用，
或用显式适配函数限制单成员调用。底层 NOOA 调用自己的超时仍然有效。
超时不保证立即停止成员，也不会撤销副作用。

### 8. Pattern 无执行状态

Pattern 实例必须无执行状态、可复用。
当前输入、执行进度、临时结果和异常应保存在调用局部变量中，
不得写入 Pattern 字段或其他共享可变存储。
同一个 `Sequential()` 可以被多个 Team 共享。
未来固定配置与每次调用的可变执行状态应明确区分；首版 Sequential 不需要配置字段。
协议不能自动证明第三方 Pattern 无状态，实现者必须遵守该约定。

### 9. 成员快照、状态共享与并发

Team 在构造时将成员序列保存为 tuple 快照，成员对象本身按引用保留，不复制、不重置。
之后修改原始成员 list 不改变 Team；首版不提供动态增删成员接口。
同一个成员实例放入多个 Team，仍然是同一个有状态实例。
重复执行 Team 不会自动开启干净会话。

首版不承诺同一 Team 的并发调用安全。
Pattern 无状态也不意味着成员、Agent 或共享 context 并发安全。

### 10. 空成员与单成员

Team 构造时拒绝空成员列表，抛出 `ValueError`。
Team 保证传给 Pattern 的成员序列非空，直接调用 Pattern 的调用者也须满足此前提。
单成员 Sequential 返回该成员的业务结果，不复制或包装。

### 11. 递归边界

Team 可以包含叶子成员或子 Team，子 Team 保留自己的 Pattern，不扁平化执行。
允许复用同一叶子或子 Team，由此产生的状态共享由调用者负责。
不支持直接或间接调用自身造成无限递归；首版不提供完整图校验器。

### 12. 显式适配与 NOOA 可见性

已提供符合契约的 `execute(task, context)` 的对象可直接参与。
其他 NOOA 公开异步方法由显式函数桥接，再交给 `as_member`：

```python
async def analyze_bridge(task, context):
    return await analyst.analyze(task)
```

适配器只转交调用，不猜测方法名、参数意义或业务数据映射。
它不自动复制底层方法的具体签名与文档，也不自动同步两个 context。
普通 Python Team 和适配器不会自动获得 NOOA span 或完整组织树的 `doc(self)` 展开；
通过公开方法调用的 NOOA 叶子仍经过其原生调用链。
NOOA Strategy 控制单个生成方法的执行；Pattern 控制成员之间的协作，两者职责不同。

### 13. 资源归属

调用者管理 Agent、模型客户端、外部连接等资源的生命周期。
Team 不自动关闭、重置或持久化这些资源。

## 验证范围

M1 测试验证两个手写流程的业务结果、输入与产物交接、共享 context 引用和调用顺序。
协议保持标准库实现，不依赖真实模型。
M2 验证适配器与 Sequential；M3 验证递归 Team；
M4 验证手写/组合等价性，以及使用公开 `FakeLLMClient` 的真实 NOOA Agent 调用。
