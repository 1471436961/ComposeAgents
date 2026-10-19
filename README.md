# nooa-patterns

NOOA 之上的轻量协作模式与组合库，工作名暂定 `nooa-patterns`。
本项目是独立 Python 扩展包，通过 NOOA 的公开 API 调用 Agent。
NOOA 负责 Agent 执行、策略、模型调用、对象状态、原生校验和事件历史；
本项目负责成员调用边界、显式参数桥接与普通 Python 协作逻辑。

## 当前阶段：台阶一（技术复审通过，已提交推送）

M1 提供两个手写顺序流程、`TeamMember` / `Pattern` 协议及基线测试。
M2 已实现 `as_member` 与 `Sequential`；M3 已实现 `Team`。
M4 已完成组合示例、隔离等价测试与真实 NOOA Agent + FakeLLMClient 集成。

唯一的 [实施计划与验收基线](docs/IMPLEMENTATION_PLAN.md)
统一记录交付物、测试命令、当前进度和逐阶段用户确认规则；review 前请先阅读。
M1–M4 均已通过 reviewer 技术复审，M4 按 Linux / WSL 完整验收基线通过。
M3 已分次提交并推送，远程提交号已核验；M4 已按用户指示分次提交，交付记录见实施计划 §8.9。
M5 按授权先记录计划，再完成 Parallel 的设计、实现与验证，详见实施计划 §9。
M5 定向 22 项通过；WSL 禁网完整回归 57 项通过、无跳过。用户提供的 reviewer 报告结论为通过，无阻塞项；
独立复审结果见实施计划 §9.9；M5 已提交推送，交付记录见 §9.10。
M6 已按确认的契约实现并完成本地验证，定向 38 项、WSL 禁网全量 95 项通过，见 §10。
用户提供的 M6 reviewer 报告结论为通过、无阻塞项，独立测试结果见实施计划 §10.7。
M6 已提交推送，交付记录见实施计划 §10.8。M7 已按确认的六项契约实现并完成本地验证，见 §11。
用户提供的 M7 reviewer 报告结论为通过、无阻塞项，独立测试结果见实施计划 §11.7。
四种基础原语均已完成实现与技术复审；M7 已按用户指示分次提交并推送，交付记录见实施计划 §11.8。
台阶一的两个复合示例、手写对照与本地验证已完成：定向 21 项、WSL 禁网全量 157 项通过，见实施计划 §15。
用户提供的 reviewer 报告结论为通过、无阻塞项，独立测试结果见实施计划 §15.4。
台阶一已按用户指示分次提交并推送，交付记录见实施计划 §15.5。
当前停在台阶一，后续工作等待用户确认；真实 LLM 应用属于尚未授权的台阶二。
核心只保留四种基础原语，本轮不改库，也不进入真实 LLM 应用或角色库。

当前公共导出为 `TeamMember`、`Pattern`、`Members`、`as_member`、`Sequential`、`Parallel`、`Router`、`Loop`、`Team`。
`as_member(fn)` 接受 `(task, context) -> Awaitable[result]` 的显式桥接函数；
`await Sequential().run(members, task, context)` 逐级交接结果。
直接调用 Sequential 的 `run` 时，成员非空是调用前提；空序列调用不受支持，行为不保证。
Parallel 的 `run` 对空序列明确抛出 `ValueError`。
`Team(members, pattern)` 接受序列或名称映射，构造时拒绝空成员；`members` 是只读 Members 浅快照，成员保持原实例引用。
`await team.execute(task, context)` 委托 Pattern，子 Team 保留自己的 Pattern，业务结果原样返回。
`Team(members, Parallel())` 并发调用成员，按成员顺序返回结果列表；失败/取消时取消并等待未完成成员。
`Team({"name": member, ...}, Router(selector))` 按同步 selector 返回的名称执行一个成员；非映射输入在构造时拒绝。
`Team(members, Loop(until, max_iterations=3))` 执行完整顺序轮次，轮后检查 until，末结果作为下一轮入口。

## 复合示例（台阶一）

**复合模式以示例形式提供，不进入库的公开接口；需要时复制并按需修改。**
这些示例使用确定性 fake，不调用真实模型，也不构成文本质量或真实应用效率的验证。

| 示例 | 组合结构与业务数据流 |
| --- | --- |
| [EvaluatorOptimizer](examples/composites/evaluator_optimizer.py) | Loop 包含 Sequential 子 Team：Request → 生成 → Draft → 评估 → Evaluation → 反馈转换 → Request |
| [Debate](examples/composites/debate.py) | Loop 包含 Parallel 提案子 Team与普通裁决成员：State → 两份 Argument → 裁决 → State；后轮读取对手观点和裁决反馈 |

每个文件均提供 `manual`、`composed` 两版，复用相同业务成员；手写 Debate 对照包含失败取消与清理等待。
例中的 Outcome 是应用在正常返回后构造的观察结果，库的 Team 仍返回 Request / State 业务对象。
每次运行独立的观察闭包计算轮次与耗尽，失败 / 取消直接传播，不会被转换成耗尽结果。

```powershell
.venv/Scripts/python.exe -X utf8 examples/composites/evaluator_optimizer.py
.venv/Scripts/python.exe -X utf8 examples/composites/debate.py
.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_evaluator_optimizer.py tests/test_debate.py -v
```

两个文件也支持从项目根目录使用 `python -m examples.composites.evaluator_optimizer` / `python -m examples.composites.debate`。
跨轮类型转换、辩论消息内容与终止标准由应用定义；原语只负责调用控制。
同一组合至少在 3 个真实场景重复且契约稳定后，才考虑可选 composites 子包；当前两个 fake 示例不满足此条件。
本次定向 **21 passed in 0.19s**；Windows 全量 **154 passed, 1 skipped in 0.57s**（既有 NOOA fcntl 限制）；
WSL 禁网全量 **157 passed in 27.29s，无跳过**。脚本在两平台运行成功，Windows 模块入口也通过。
验证结果、表达不适与后续授权边界集中记录在[实施计划 §15](docs/IMPLEMENTATION_PLAN.md)。
台阶一已通过技术复审；实施与 reviewer 的独立运行分别保留在 §15.3、§15.4。

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
async def run(self, members: Members, task: Any, context: Any) -> Any: ...
# 调用方式：await pattern.run(members, task, context)
```

Pattern 提供 `run`，TeamMember 提供 `execute`；满足 Pattern 协议不代表满足成员协议。
Pattern 复用下文的数据、引用、异常与副作用约定，不是 TeamMember 的子类型。
M1 定义两个协议；M2 实现适配与 Sequential；M3 实现可递归的 Team；M5 增加 Parallel；M6 增加 Members 与 Router；M7 增加 Loop。

## 运行手写基线与测试

需要 Python 3.12 或 3.13。手写示例只使用标准库：

```powershell
python examples/manual_flows.py
```

使用 uv 创建隔离环境，从 `pyproject.toml` 安装开发依赖并运行。
缓存保存在本项目的 `.uv-cache` 中：

```powershell
uv --cache-dir .uv-cache venv --python 3.12
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe --group dev
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe --no-deps --editable .
.venv/Scripts/python.exe examples/manual_flows.py
.venv/Scripts/python.exe -m pytest
```

M1–M3 及 M5–M7 的纯 Python 编排验证可使用 `--no-deps` 安装本地包，暂不安装 NOOA 运行时。
pytest 配置会加入 `src` 和项目根目录，以便验证标准库协议与手写基线。
`pyproject.toml` 已声明 NOOA 的 Git 依赖；
`uv.lock` 锁定此次解析的 NOOA 提交与依赖版本，完整开发环境使用 `uv sync --locked`。

Windows 管道输出中文时可使用 `python -X utf8 examples/manual_flows.py`。
若 pytest 缓存目录不可写，可用 `python -m pytest -p no:cacheprovider` 完成测试，
该选项仅关闭测试缓存，不改变测试收集或断言。

### M4 完整验证环境：Linux / WSL

当前锁定的 NOOA 为 `0.0.11.dev433`，提交
`1454b78c8f0a85c97eab1c6a91cc8cfc95b34de5`。该上游版本的 SQLite 模块直接导入
Unix `fcntl`，原生 Windows 上 `import nooa` 会失败；依赖检查通过不代表运行时可导入。
Windows 可运行本库的普通 Python 测试，NOOA 集成模块会明确报告平台跳过；
完整 M4 验收必须在 Linux / WSL 运行且无跳过，不修改或替换 NOOA 核心模块。

在 Linux / WSL 的项目根目录执行（需已安装 Linux 版 uv，Python 3.12）：

```bash
UV_PROJECT_ENVIRONMENT=.uv-cache/wsl-venv uv --cache-dir .uv-cache/wsl-packages sync --locked --python python3.12
uv --cache-dir .uv-cache/wsl-packages pip check --python .uv-cache/wsl-venv/bin/python
.uv-cache/wsl-venv/bin/python -X utf8 examples/composed_flows.py
.uv-cache/wsl-venv/bin/python -X utf8 -m pytest -p no:cacheprovider -v
```

两种系统使用独立虚拟环境，WSL 环境和缓存都放在已忽略的 `.uv-cache/` 中。
集成测试通过公开 `enable_tracing(exporters=[])` 关闭自动 viewer 探测与网络导出，
使用本地模型元数据和严格响应耗尽的 `FakeLLMClient`，并拒绝测试中的 IP 连接。

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

Parallel 与 Sequential 的交接规则不同：所有成员并发收到入口的同一个 task/context，
不把前一结果作为下一输入。正常完成时返回新建 list，按成员顺序排列，元素保持原业务对象身份；
不按完成顺序排序，不展开子列表或过滤 None。下游须明确接收结果列表，不能把它当作其中某个成员的单个结果。

Router 每次调用一次 `selector(task, context)` 并执行一个选中成员；两者接收相同的入口引用，
返回选中成员的原业务结果。selector 签名为 `Callable[[Any, Any], str]`。
selector 应是纯函数式的同步决策，不应调用 LLM 或做 I/O；模型决策应由前置异步成员完成，selector 只读其产物。
不支持异步 selector 或运行时双协议兼容；selector 的纯度是调用者责任，不由库检查或隔离。

Loop 至少执行一轮，每轮完整按 Sequential 语义执行所有成员，然后调用一次 until。
首轮入口是 task，之后每轮入口是上一轮末结果；不提前检查入口，不自动恢复原任务或转换类型。
`Loop(until, *, max_iterations)` 的上限无默认值且为必需关键字参数，只接受正整数：
非整数或 bool 抛 TypeError，零 / 负数抛 ValueError。
until 签名为 `Callable[[Any, Any], bool]`，应是纯函数式同步判断，不应调用 LLM 或做 I/O；
返回非 bool 抛 TypeError，不隐式取真值。最后一轮 until 为 True 算正常终止；满上限仍 False 则返回末结果，不因耗尽抛异常。
本轮末结果必须能作为下一轮入口；转换由应用显式成员负责，库不提供 feedback_adapter。

### 3. 应用 context

context 是调用者创建、持有和管理的应用级对象，可以是字典、dataclass 或其他对象。
所有成员接收同一个 context 引用，成员修改对其他成员可见。
库不复制、不持久化它，也不自动注入 `last_result`、`history`、原始任务等字段。
业务成员和显式适配函数可以有意修改 context。

这里的 context 与 NOOA Agent 的 `agent.context`（提示词上下文）无关，不自动同步。
失败或取消时，context 上已经发生的修改不会回滚。

Parallel 不保护 task/context 的并发读写，**调用者负责共享对象的并发安全**。
task 同样是共享活引用；并发不保证 CPU 并行，阻塞代码也可能阻碍失败处理与取消。

Loop 不自动写 loop_exhausted 或任何其他字段，不自动累计轮次 / 历史，首版不提供 on_exhausted 回调。
这保持 context 的应用所有权，避免固定状态字段在重复 / 嵌套运行中产生清除与覆盖问题；耗尽判定属于应用语义。
应用可每次创建新的 until 观察闭包，计数 rounds 并保存 last_ok，在正常返回后计算
`exhausted = (rounds == max_iterations and not last_ok)`。观察计数不改变纯业务判断；
同一个有状态观察闭包不应共享给独立并发调用。异常 / 取消正常传播，不执行上述正常返回后的耗尽计算。

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

`None` 是普通业务结果。Sequential 中逐级原样传递，最后一步返回 `None` 时 Team 返回 `None`；
Parallel 将它保留为结果列表中的对应元素，不影响其他成员的调用。
Router 选中成员返回 None 时也原样返回，不切换到其他分支。
Loop 的 None 末结果原样交给 until，必要时作为下一轮输入。
它不表示跳过、提前结束、保留上一结果或错误。
某一步只修改 context 且希望继续传递当前输入时，应显式 `return task`。

### 6. 异常、取消与副作用

成员抛出的异常直接向上传播，库不吞异常、不包装为通用错误。
Sequential 在异常或 `CancelledError` 传播后不再启动后续成员。
库不额外重试整个流程，避免重复副作用；成员或 NOOA 策略自身的重试仍按其机制运行。

不回滚适用于 context、输入对象、Agent 状态及已发生的外部副作用。
取消是协作式的，库不能强制终止阻塞、屏蔽取消或自行创建后台任务的成员。
首版仅管理它直接等待的调用链。

Parallel 仅使用固定的快速失败策略：观察到首个异常后，向尚未结束的兄弟任务发出取消请求，
等待本次直接子任务全部结束并取走异常，再传播原先触发失败的同一个异常对象。
多个同时异常不保证按成员顺序选取；不包装 ExceptionGroup、不返回部分结果或异常结果列表。
其他成员取消清理时的异常不会覆盖原业务异常；外层取消保持 CancelledError，
即使某个成员的取消清理抛错。清理过程中另一次外层取消仍可优先传播。

外层被取消或某个成员自行取消时，中止本次汇集，取消并等待其他未完成成员。
已经完成的成员不会追溯取消，成员吞掉取消后返回的值也不会把被取消的整次调用改为成功。
快速失败指及时请求取消，不保证立即返回；异步清理或拒绝结束的成员可能延长等待，库不内置超时。

Router 中 selector 或成员抛出的异常直接传播，取消传到被选成员，不自动执行其他分支。
selector 返回非字符串时抛 TypeError；未命中抛 LookupError，消息包含返回名称和可用名称列表，
例如 `selector returned 'unknown', available: ['security', 'architecture', 'quick']`，没有默认分支。
Loop 中成员失败即停止本轮，until 失败即停止后续轮次；异常和取消直接传播，不重试、不回滚、不记录为耗尽。

### 7. 超时

首版没有内置超时参数。调用者可以用 `asyncio.timeout` 包裹整个调用，
或用显式适配函数限制单成员调用。底层 NOOA 调用自己的超时仍然有效。
超时不保证立即停止成员，也不会撤销副作用。
Loop 的 max_iterations 只限制轮数，不是总耗时或强制终止保证。

### 8. Pattern 无执行状态

Pattern 实例必须无执行状态、可复用。
当前输入、执行进度、临时结果和异常应保存在调用局部变量中，
不得写入 Pattern 字段或其他共享可变存储。
同一个 Sequential、Parallel、Router 或 Loop 可以被多个 Team 共享。
固定配置与每次调用的可变执行状态应明确区分；Router 保存 selector，Loop 保存 until / max_iterations，
本次选择、轮次、当前结果均为调用局部状态；库不重置调用者的闭包、成员或资源。
Pattern 的类声明 `requires_named_members` 默认 False，Router 声明 True；Sequential、Parallel、Loop 不要求命名。
Protocol 不会给普通结构类型自动添加属性，未声明该属性的既有自定义 Pattern 按默认 False 处理。
协议不能自动证明第三方 Pattern 无状态，实现者必须遵守该约定。

### 9. 成员快照、状态共享与并发

Team 接受 `Sequence[TeamMember] | Mapping[str, TeamMember]`，构造时浅拷贝并统一保存为 Members，
保留输入顺序及原成员引用，不复制、不重置成员。之后修改原始 list/dict 不改变 Team；没有动态增删接口。
`Team.members` 自 M6 起返回 Members，取代原 tuple；该属性只读。
Members 支持 `__iter__`、`__len__`、`__getitem__(int | str)`、`has_name(name)` 和只读 `names` 元组。
迭代总是得到成员对象；映射按输入顺序排列，序列不自动生成名称。整数访问支持负索引，
越界抛 IndexError，未知名称抛 KeyError，不支持切片；映射的名称必须为字符串。
同一个成员实例放入多个 Team，仍然是同一个有状态实例。
重复执行 Team 不会自动开启干净会话。

首版不承诺同一 Team 的并发调用安全。
Pattern 无状态也不意味着成员、Agent 或共享 context 并发安全。
同一个有状态成员在 Parallel 多个位置出现也不获得重入安全保证。

### 10. 空成员与单成员

Team 构造时拒绝空成员序列或映射，抛出 `ValueError`；Members 本身允许空快照。
如果 Pattern 声明要求命名，但传给 Team 的输入不是 Mapping，在构造时抛 ValueError；
Router 的消息为 `Router requires named members`，不会等待前置分析产生副作用后再发现该结构错误。
Team 保证传给 Pattern 的成员序列非空，直接调用 Pattern 的调用者也须满足此前提。
单成员 Sequential 返回该成员的业务结果，不复制或包装。
单成员 Parallel 返回单元素列表，None 也保留该位置。直接调用 Parallel.run 时也对空序列抛 ValueError；
这不改变 Sequential 对直接空序列调用不作保证的既有边界。
Router 的直接 run 同样要求非空命名 Members；只有一个名称时仍执行 selector 并检查返回名称。
直接 Loop.run 同样拒绝空成员；单成员也执行完该成员后才调用 until。

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
M6 验证 Members 快照与命名、构造时检查、Router 单分支执行及完整评审案例。
M7 验证有界整轮执行、显式反馈、应用侧耗尽观察、异常 / 取消及嵌套和复用。

M2 定向验收命令：

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_adapters.py tests/test_sequential.py -v
```

M2 评审后增加适配器异步类方法与单成员结果身份测试，当时实际结果为 M2 定向测试
**15 passed in 0.19s**，M1+M2 全量回归 **18 passed in 0.17s**。
初始实施与 reviewer 的 13/16 项结果作为历史记录单独保留。
`python -I` 隔离模式下公共 API 导入与适配器/Sequential 联合调用已在首次实施和 reviewer 验证中通过。
完整命令、断言与阶段记录见实施计划 §6.4–6.6。

M3 定向验收命令：

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_team.py -v
```

M3 实施时定向测试 **11 passed in 0.20s**，M1–M3 全量回归 **29 passed in 0.21s**。
`python -I` 下公开 Team API 的递归调用也通过。共享 Pattern、子 Team 保留自身 Pattern、
异构结果交接等具体断言见实施计划 §7.4；M4 的集成与等价测试结果见下节。

用户提供的 M3 reviewer 报告结论为通过，无阻塞项；其独立运行结果为定向测试
**11 passed in 0.15s**、全量回归 **29 passed in 0.21s**，隔离导入与递归调用通过。
这与实施时运行分别记录，详见实施计划 §7.5；后续用户授权与提交安排见 §7.6。

### M4 结果与对照

[组合示例](examples/composed_flows.py) 用 Team + Sequential + as_member 替换两个手写流程的
顺序协调，继续调用同一份业务函数。输入、中间 Analysis / ChangePlan、最终报告 / ReviewOpinion
以及业务 context 的含义保持不变；不通过的审查意见仍直接返回，不触发修改或重审。

- [等价测试](tests/test_equivalence.py)：3 项通过。每次运行重新创建 context 和有状态 fake；
  跨运行比较结果、顺序与 context 业务值，引用身份只在各次运行内部检查。
- [真实 NOOA 适配测试](tests/test_nooa_adapter.py)：3 项通过。公开 PredictStrategy 驱动真实 Agent，
  FakeLLMClient 提供全部响应；验证输出 schema、原生 Task / LLMResponse 事件、输入拒绝、输出拒绝，
  以及直接调用与 Team 适配调用的校验行为一致。
- WSL Ubuntu 24.04 / Python 3.12.3 / pytest 9.1.1：禁网运行完整回归，
  **35 passed in 46.14s，无跳过**。两种示例与隔离包导入均通过。
- 原生 Windows：**32 passed, 1 skipped in 0.36s**；跳过的是因上游 fcntl 导入失败而无法运行的
  NOOA 集成模块，不能代替上述 Linux 完整验收。

完整原始输出见 [M4_PYTEST.txt](docs/validation/M4_PYTEST.txt)，安装与验证命令、具体断言见
[实施计划 §8.5–8.8](docs/IMPLEMENTATION_PLAN.md)。M4 未修改生产库 API 或 NOOA 参考源码。

用户提供的 M4 reviewer 报告结论为通过，无当前基线的阻塞项。其独立运行记录为：
WSL 禁网回归 **35 passed in 59.00s，无跳过**，Windows 回归
**32 passed, 1 skipped in 0.22s**，Windows 等价测试 **3 passed in 0.05s**。
这些结果与上述实施运行分别保留，详见实施计划 §8.8。原生 Windows 的 NOOA 限制仍然存在，
本次复审不代表已实现原生 Windows NOOA 支持或已授权后续扩展。

M4 当时的判断是保留薄组合内核，继续用真实应用验证；两步流程的手写 await 本来更短，
这些微型示例本身不能证明完整应用效率提升。后续用户已明确将核心范围收敛到四种基础原语，
按 M5 Parallel → M6 Router → M7 Loop 逐阶段推进，复合模式不进入核心。

### M5 Parallel：接口、案例与验证

```python
analysis = Team(
    [as_member(feasibility), as_member(risk), as_member(cost)],
    Parallel(),
)
reports = await analysis.execute(proposal, context)
# [FeasibilityReport, RiskReport, CostReport]，按成员顺序排列
```

[Parallel 实现](src/nooa_patterns/patterns/parallel.py) 在 M5 的接口为
`async run(members: Sequence[TeamMember], task: Any, context: Any) -> list[Any]`；M6 将成员标注统一为 Members，执行语义不变。
所有成员共享入口引用；快速失败会取消未完成成员，等待清理后传播原异常。
外层取消也会转交并等待清理；成员清理抛错不能把外层取消替换成业务异常。
这不是立即中断或事务回滚保证，完整边界见上文契约。

[三分析成员示例](examples/parallel_review.py) 使用具体业务类型与确定性 fake，
保留显式创建任务、取消和等待清理的手写并发对照；普通 `aggregate` 函数将三报告合为 AnalysisBundle。
示例只到报告聚合。递归测试用外层 Sequential 串起分析子 Team 和显式聚合成员。
三个分析函数的输入都是 Proposal，不能直接换成 Sequential 后仍期望三报告列表；
模式替换测试使用输入输出兼容的成员，且明确比较两种模式不同的输出形状。

```powershell
.venv/Scripts/python.exe -X utf8 examples/parallel_review.py
.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_parallel.py tests/test_parallel_review.py -v
```

- 示例实际退出 0，手写与组合业务结果、报告位置及 context 事件多重集一致。
- [Parallel 测试](tests/test_parallel.py) 17 项、[案例测试](tests/test_parallel_review.py) 5 项，
  合计 **22 passed in 0.17s**。覆盖顺序、共享引用、空成员、None、失败/取消清理、嵌套及共享 Pattern。
- Windows 全量回归 **54 passed, 1 skipped in 0.31s**；跳过的仍是上游 fcntl 限制的 NOOA 模块。
- WSL Ubuntu 24.04 / Python 3.12.3：`unshare --net` 完整回归
  **57 passed in 48.97s，无跳过**，包含 M4 的真实 NOOA + FakeLLMClient 测试。
- `python -I` 隔离模式导入六个公共名称通过。NOOA 参考目录与已有快照比较，1,500 文件内容及文件集合均未改变。

完整输出见 [M5_PYTEST.txt](docs/validation/M5_PYTEST.txt)，契约挑战、测试断言与实施记录见
[实施计划 §9](docs/IMPLEMENTATION_PLAN.md)。M5 已通过 reviewer 技术复审，用户已指示提交推送，交付记录见 §9.10；
M5 时尚未实现 Router / Loop；后续契约与实现分别见 M6、M7 章节。

### M6 Members 与 Router：案例与验证

[Members](src/nooa_patterns/members.py) 提供顺序 / 名称访问；[Router](src/nooa_patterns/patterns/router.py)
仅保存同步 selector。`Team(mapping, Router(selector))` 在构造时检查命名要求，所有 Pattern 的 run 均标注 Members。
Sequential / Parallel 的执行语句保持不变；测试同时验证旧交接语义和新映射输入。

[完整评审示例](examples/router_review.py) 保留手写并发、聚合、选择、审查的 await 对照，
组合版以外层 Sequential 串起 Parallel 分析子 Team、普通聚合桥接和命名 Router 子 Team。
调用者显式创建 `ReviewContext(proposal=task)`，聚合得到 `ReviewRequest(proposal, bundle)`；
更换 task 时须由应用提供对应 context，库不注入原任务。三档风险分别选择 security / architecture / quick。
替换 selector 的测试保留相同审查成员，验证分支变化；不把不同输入输出契约的 Pattern 当作等价替换。

```powershell
.venv/Scripts/python.exe -X utf8 examples/router_review.py
.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_members.py tests/test_router.py tests/test_router_review.py -v
```

本次定向 **38 passed in 0.18s**；Windows 全量 **92 passed, 1 skipped in 0.44s**（上游 fcntl 限制）；
WSL 禁网完整回归 **95 passed in 27.36s，无跳过**。完整逐项输出见 [M6_PYTEST.txt](docs/validation/M6_PYTEST.txt)，
断言与命令见[实施计划 §10.5](docs/IMPLEMENTATION_PLAN.md)，reviewer 独立复审结果见 §10.7。
M6 已通过技术复审并提交推送，交付记录见实施计划 §10.8；M7 的 Loop 契约与验证见下节。

### M7 Loop：显式反馈与应用侧耗尽

[Loop](src/nooa_patterns/patterns/loop.py) 使用 `Loop(until, *, max_iterations)`，每轮完整执行 Sequential，
轮后严格检查 bool；最后一轮 True 正常终止，满上限仍 False 返回末结果。成员仍由 Team 持有，映射按顺序执行。
库不写任何 context 字段，不加 on_exhausted；应用每次新建 until 观察闭包，在正常返回后计算耗尽。

[反馈评审示例](examples/loop_review.py) 保留手写 for / await / 并发清理对照，组合版每轮为：
分析子 Team（Sequential + Parallel）→ Router 审查子 Team → 显式 ReviewOpinion-to-Proposal 反馈成员。
until 读取应用 context 中的审查结果；ReviewRun 只是示例函数的应用观测产物，Loop 自身仍返回原业务结果。
示例文档说明三种跨轮转换方式，采用末尾反馈成员；耗尽后的末反馈方案可能尚未再次审查，不能宣称已通过。

```powershell
.venv/Scripts/python.exe -X utf8 examples/loop_review.py
.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_loop.py tests/test_loop_review.py -v
```

本次 [核心测试](tests/test_loop.py) 31 项、[案例测试](tests/test_loop_review.py) 10 项，
合计 **41 passed in 0.20s**；Windows 全量 **133 passed, 1 skipped in 0.54s**（原 NOOA fcntl 限制）；
WSL 禁网全量 **136 passed in 25.92s，无跳过**。两平台示例均通过提前、末轮通过和耗尽三种对照。
完整逐项输出见 [M7_PYTEST.txt](docs/validation/M7_PYTEST.txt)，命令、断言和表达范围判断见
[实施计划 §11.5–11.6](docs/IMPLEMENTATION_PLAN.md)。M7 技术复审已通过并提交推送，独立复审与交付记录见 §11.7–11.8；后续三个台阶的授权与验证见 §15。
