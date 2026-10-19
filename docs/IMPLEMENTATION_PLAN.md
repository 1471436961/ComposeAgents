# 实施计划与验收基线：M0–M7

本文件是项目唯一维护的实施计划，统一记录 M0–M7 的范围、契约决定、验证证据与阶段确认规则。
当前 **M6：Members、构造时命名检查、Router 与评审案例已通过本地验证和 reviewer 技术复审，用户已指示提交推送**，交付记录见 §10.8。M7 Loop 尚未授权。

本文件将已由用户确认的设计、M1–M7 实施任务和阶段确认规则落盘，供没有聊天上下文的
实现者与 reviewer 使用。它记录实施范围，不表示后续里程碑已经获准开始。

## 1. 阅读顺序与依据

1. 本文件：确认当前阶段、允许的范围和验收条件。
2. [README](../README.md)：阅读项目定位、核心抽象和完整执行契约 v0。
3. [protocols.py](../src/nooa_patterns/protocols.py)：核对真实接口与协议 docstring。
4. 对应阶段的实现和测试：以实际运行结果验证行为，不能只根据文档宣称通过。

里程碑范围来自用户“分四个里程碑实现”的任务书；执行语义来自此前已确认的契约修正。
原始实施任务正式划分的是 **M1–M4**。下文的 **M0 只是对已完成前置设计的回填编号**，
不新增开发任务、追溯性验收门槛或用户批准。M4 后用户进一步确认 Parallel → Router → Loop，
对应 M5–M7，新增阶段仍须逐个获得实现授权。

契约的完整内容保存在 README 和协议 docstring 中，两处都须维护完整内容，这是用户的明确要求。
本文件只索引关键决定，不另立一份不同的契约。后续用户变更设计或范围时，应同步更新相关文件。

## 2. 项目边界与已确认设计

项目根目录和 Git 仓库为 `E:\ComposeAgents\nooa-patterns`。
`E:\ComposeAgents\labs-OO-Agents-main` 为只读参考源码，禁止修改。

项目是 NOOA 生态里的模块化协作与可复用设计模式库，借鉴 `torch.nn` 的组合思想。
它是独立 Python 扩展包；不新增底层 Agent 执行框架，不重写模型调用、沙箱、
Agent 状态管理或事件历史，不以 LangGraph / CrewAI 为基础，也不用 TypeScript 重写核心。

核心只提供 Sequential、Parallel、Router、Loop 四种基础控制原语，仍以 NOOA 公开 API 为底座。
Supervisor、GroupChat、Handoff 不作为标准 Pattern；EvaluatorOptimizer、Voting、Debate、
PlanExecute、MapReduce、MoA 仅可作为未来 examples / 文档中的组合方式，不预置同名核心类。
Blackboard、ContractNet、Negotiation 不做。领域角色留待未来应用验证，M5 不创建 roles/。
模式目录是研究资产，不是逐项实现路线图。

保留 Team 持有成员、Pattern 决定协作的分离，Pattern 不保存本次执行状态。
弱类型、活引用、无隐式重试/回滚/持久化、资源归调用者和 NOOA 只读边界继续生效。

核心结构：

```text
概念：Team = [Agent | Team] × Pattern
调用：Team = [TeamMember] × Pattern
```

- 叶子使用 NOOA Agent 的业务能力，本项目不新增 Agent 基类。
  裸 NOOA Agent 基类没有成员协议的 `execute`；具体对象已实现协议时可直接参与，
  否则以显式异步函数桥接，再交给 `as_member`。
- Team 是实现 `execute` 的普通 Python 容器，成员可以是叶子或子 Team。
- Pattern 提供 `run(members, task, context)`，是组织结构之外的协作维度。
  它不是 TeamMember 子类型；仅实现 `run` 不意味着可当作成员调用。
- NOOA Strategy 控制单个生成方法的执行，Pattern 控制成员之间的协作，职责不同。

必须保留的决定：

| 主题 | 已确认内容 |
| --- | --- |
| 类型边界 | v0 使用 `Any / Any -> Any` 弱类型协议；兼容性由调用者与测试保证，不继承 NOOA 类型校验契约；被调用 NOOA 公开方法原有校验仍生效。 |
| 顺序交接 | 首成员收到入口 task；之后接收前一步返回值。原始 task 不是不可变快照，不自动注入 context。 |
| context | 调用者持有，同一活引用；库不复制、不注入、不持久化，失败不回滚；与 NOOA `agent.context` 无关且不自动同步。 |
| 返回值 | Team 与叶子返回同一成员调用边界上的业务结果，不要求同一类型；子 Team 输出仍须兼容外层下一成员。 |
| Pattern | 无每次执行的可变状态，可跨 Team 复用；不将进度、当前输入或临时结果保存为字段或其他共享状态。 |
| 其他边界 | `None` 为普通结果；空 Team 构造时报 `ValueError`；序列 / 映射统一为 Members 浅快照（M6 扩展），成员保持引用；不内置超时、不重试整个流程、不回滚副作用、不承诺同一 Team 并发安全。 |
| 递归与资源 | 子 Team 保留自己的 Pattern；不支持无限自调用；不做完整图校验；资源生命周期归调用者。 |

README 将完整契约按 13 个主题组织，覆盖任务书中的 15 个要点。
验收以内容完整性为准，不要求机械改成 15 个编号。

## 3. 阶段确认规则与当前状态

**每完成一个里程碑，必须汇报并停止。只有用户确认后，才能进入下一个里程碑。**
测试通过不等于用户已批准进入下一阶段；收到 review 建议也不自动表示可以实现后续阶段。

| 阶段 | 内容 | 当前状态 |
| --- | --- | --- |
| M0 | 前置设计、契约、范围确认；本文件回填记录 | 设计已确认，见 §4 |
| M1 | 手写基线 + 协议 + 完整文档 | 已实现并通过 reviewer 复审，验证见 §5.4–5.5；用户已确认进入 M2 |
| M2 | 适配器 + Sequential | 已通过技术复审与补充测试；按用户要求分三次提交并推送，见 §6.7；用户已确认进入 M3 |
| M3 | Team 容器 | 已通过本地验证与 reviewer 技术复审；已分次提交并推送，远程已核验，见 §7.6 |
| M4 | 组合示例 + 等价测试 + NOOA 集成 | 已通过复审并分三次提交推送，远程 main 已核验为 536fbcb；历史证据见 §8.9 |
| M5 | 设计 + Parallel | 已通过复审并分次提交推送，远程已核验为 2cc65b5；交付见 §9.10；用户已确认进入 M6 |
| M6 | Members、声明式命名检查、Router 与专业审查案例 | 已通过本地验证和 reviewer 技术复审，无阻塞项；用户已指示提交推送，见 §10.5–10.8；M7 尚未授权 |
| M7 | 通用有界 Loop；终止条件与耗尽标记契约 | 只规划，等待 M6 汇报后的用户确认；见 §11 |

M1 的导出基线为 `TeamMember`、`Pattern`；M2 增加 `as_member` 与 `Sequential`，M3 增加 `Team`。
M4 已完成两条应用微流程的等价对照和真实 NOOA 的公开方法集成，不能将此扩大为真实模型、
完整应用价值或 NOOA 全部策略与沙箱能力已被验证。

M1–M3 使用 `--no-deps` 验证本地包与纯 Python 编排。M4 新增完整依赖安装与锁文件，
并在 Linux / WSL 验证 NOOA 导入、依赖一致性和 FakeLLMClient 原生调用；
当前上游版本在原生 Windows 上导入 fcntl 失败，详见 §8.5，不混淆安装成功与运行时可用。

## 4. M0：已确认的前置设计记录

此节仅回填已经发生的设计工作：

- 确认独立 Python 包、NOOA 公开 API 边界、`src` 布局和禁止修改 NOOA 源码。
- 确认 Agent / Team 递归结构与 Pattern 解耦，避免固定三层结构。
- 确认弱类型 v0 契约、引用语义、业务返回值、失败与副作用边界，以及 Pattern 无状态。
- 先写两个手写顺序微流程，证明同一种“等待 → 结果交接”协调逻辑重复出现，再提取组合内核。
- 两条基线分别为“资料分析 → 报告生成”和“变更方案 → 审查意见”。
  首版不引入退回修改、再次审查、循环、辩论或路由。

两个微流程证明的是重复协调逻辑，尚不能证明完整库的应用价值。
是否扩展库，需要后续组合原型和真实应用证据。

## 5. M1：手写基线 + 协议

### 5.1 交付物

- `pyproject.toml`：独立包元数据、NOOA 依赖声明、pytest 开发依赖和 `src` 布局。
- `README.md`：定位、边界、核心抽象、完整执行契约及运行说明。
- `examples/manual_flows.py`：两条纯 `await`、普通 fake 函数驱动的顺序流程。
- `src/nooa_patterns/protocols.py`：`TeamMember` 与 `Pattern`，以及完整协议 docstring。
- `src/nooa_patterns/__init__.py`：仅导出上述两个协议。
- `tests/test_manual_flows.py`：M1 行为基线；实际实现了 3 个测试，而不是占位断言。

本次落盘的 `AGENTS.md` 和实施计划是 reviewer 阅读入口，不增加运行时功能。

### 5.2 验收条件

- 两个流程都只有两步顺序调用，无循环、退回或再次审查。
- A：资料字符串 → `Analysis` → 报告字符串；context 提供读者、来源与调用记录。
- B：变更目标字符串 → `ChangePlan` → `ReviewOpinion`；context 提供审查要求与调用记录。
- 中间产物通过返回值交接；所有步骤收到调用者创建的同一个 context。
- 验证入口对象身份、中间产物身份、产物内容、最终结果、调用顺序和 context 修改。
- 不通过的审查意见直接作为业务结果返回，不触发修改或重审。
- 示例只依赖标准库；测试不访问真实模型。
- 两个协议只定义接口与契约，不引入运行时类型推断或强制业务校验。
- README 集中呈现核心抽象，包括递归公式、`Pattern.run` 和 NOOA 适配路径。

### 5.3 验收命令

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 examples/manual_flows.py
.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider -v
.\.venv\Scripts\python.exe -I -X utf8 -c "from nooa_patterns import TeamMember, Pattern; print('import OK')"
```

M1 不要求 `adapters.py`、`sequential.py`、`team.py`、组合示例或 NOOA 集成测试。
也不以完整 NOOA 安装、依赖锁文件或首次 Git 提交作为原始 M1 硬性验收门槛。

### 5.4 已完成的评审修复与验证记录

- 已补上 README“核心抽象”章节，集中说明两个角色、递归规则、正交 Pattern、`run` 入口和适配路径。
- 已澄清 Pattern docstring：复用成员契约中的语义，不是 TeamMember 子类型。
- 已补充 UTF-8 中文输出和 pytest 无缓存运行说明。
- editable 包构建与协议导入已成功；`python -I` 隔离模式导入也成功。
- 两个手写流程已经实际运行，业务结果与调用记录断言通过。
- 最近一次用户要求提权重跑 pytest 的实际结果如下；不是本次文档整理中新产生的测试结果：

```text
命令：.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider -v
环境：Windows / Python 3.12.14 / pytest 9.1.1
test_research_flow_handoffs_and_shared_context PASSED
test_change_flow_handoffs_and_shared_context PASSED
test_rejection_is_a_business_result_without_revision PASSED
3 passed in 0.10s
```

该结果来自沙箱外的实际执行。此前沙箱内超时及审批服务容量不足的尝试均未计为通过。

### 5.5 Reviewer 复审结论

来源：用户提供的《M1 Review 报告（复审）》。以下是 reviewer 报告的验证记录，
与 §5.4 的独立提权运行分别保留，不混作同一次执行。

- **技术验收结论：通过，无新的 M1 阻塞问题。**
- 核心抽象章节和 Pattern / TeamMember 关系的文档问题已经修复，完整契约按内容判定为 15/15。
- reviewer 报告：手写示例正常退出、`python -I` 导入成功，pytest 三项均通过，耗时 **0.12s**。
- reviewer 撤回将完整 NOOA 安装视为 M2 前置的判断：M2 可用 fake 验证，真实 NOOA 集成属于 M4。
- reviewer 撤回契约去重和新增 `hasattr` 测试建议；完整契约双份保留及隔离导入验证符合要求。
- README 的里程碑映射建议已修正为 M2 = 适配器 + Sequential、M3 = Team、M4 = 组合示例与集成验证。
- 首次 Git 提交、依赖 pin 与锁文件仍是非阻塞建议，不改变 M1 的技术验收结论。

该复审报告本身不构成 M2 授权；用户随后于 2026-10-19 明确指示“开始M2”，当前状态见 §3。

## 6. M2：适配器 + Sequential

**开始条件：用户确认 M1 并授权进入 M2。**

### 6.1 交付物与顺序

1. `src/nooa_patterns/adapters.py` 与 `tests/test_adapters.py`：实现 `as_member`。
2. `src/nooa_patterns/patterns/__init__.py`、`patterns/sequential.py`
   与 `tests/test_sequential.py`：实现唯一首版生产 Pattern `Sequential`。
3. 按实际实现更新包导出与 README 当前进度。

适配器接口：

```python
as_member(fn: Callable[[Any, Any], Awaitable[Any]]) -> TeamMember
```

适配结果须有真正的类方法 `async execute(task, context)`；保存原 callable 引用并转交调用。
业务参数映射由调用者显式写出的异步桥接函数负责，不推断方法名或业务签名，
不以赋值 `self.execute = agent.some_method` 代替方法包装。

Sequential 按 `r₀ = task`、逐个等待并更新当前结果、返回 `rₙ` 的规则执行。
执行进度仅保存在局部变量中。`run` 的成员序列前提为非空；
Team 构造期拒绝空成员的职责在 M3 验证。

### 6.2 必须验证的行为

- `as_member` 转交 task/context 引用，原样返回结果并传播异常。
- 首成员接收入口对象；后续成员接收前一步返回的同一个对象。
- 全部成员收到同一个 context，前一步修改对后一步可见。
- 中间与最终 `None` 原样传递，没有隐式跳过或提前结束。
- 异常和协作式取消正常传播，不启动后续成员。
- 失败前已经发生的修改保留，无库级整流程重试。
- Sequential 不保存每次执行的状态；跨 Team 共享测试安排在 M3。

### 6.3 验收与汇报

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_adapters.py tests/test_sequential.py -v
```

汇报适配器和 Sequential 的最终内容、实际测试输出、发现的契约歧义；然后停止。
M2 不实现 Team，不要求真实 NOOA Agent 集成，不开始 M3。

### 6.4 M2 首次实施与验证记录

授权来源：用户于 2026-10-19 明确指示“开始M2”。本节为首次实施的历史记录；
后续 reviewer 结论和测试补充分别见 §6.5、§6.6，当时尚未授权 M3；其后授权见 §6.7。

已交付：

- `src/nooa_patterns/adapters.py`：私有普通类保存原 callable 引用，真实 `async execute` 转交调用；
  `as_member` 不进行签名推断、业务转换、对象复制或自动 context 同步。
- `src/nooa_patterns/patterns/sequential.py`：仅用局部变量和顺序 `await` 交接结果，无执行状态字段。
- `src/nooa_patterns/patterns/__init__.py` 和包根导出：公开 `Sequential`、`as_member`，保留两个协议。
- `tests/test_adapters.py`：6 个行为测试。
- `tests/test_sequential.py`：7 个测试用例，其中包括 3 种中间/最终 `None` 组合。
- README、AGENTS 与本计划同步更新到 M2 完成并等待下一阶段确认。

实际执行结果：

| 验证 | 实际命令 / 内容 | 结果 |
| --- | --- | --- |
| 适配器增量验证 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_adapters.py -v` | `6 passed in 0.13s` |
| M2 定向验收 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_adapters.py tests/test_sequential.py -v` | `13 passed in 0.19s` |
| M1+M2 回归 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider -v` | `16 passed in 0.16s` |
| 隔离公共 API 验证 | `python -I -X utf8` 导入两个协议、`as_member`、`Sequential`；对 3 依次加 1、乘 2，复用同一应用 context | 返回 `8`，context 为 `["add", "double"]` |

运行环境为 Windows / Python 3.12.14 / pytest 9.1.1。测试仅使用普通 fake，无新增依赖、网络或模型调用。

关键断言：

- task/context/业务结果的身份保持；绑定方法沿用同一个原实例及其状态。
- 显式桥接异构签名，不自动改写实例自身的 context。
- 用事件暂停首成员，确认其完成前第二成员未启动；首成员产物原样成为下一输入。
- 中间 `None` 仍会调用下一成员，最终 `None` 原样返回。
- 异常对象保持身份，后续成员不运行；输入、context 和 fake 实例的失败前修改保留，未重试。
- 对运行中的调用执行真实 `Task.cancel()`，取消传播且后续步骤不启动，已有修改保留。
- 同一个 Sequential 的两次 `run` 交错执行，分别使用独立成员/context，结果和输入无串扰。
  这不是 M3 的跨 Team 测试，也不扩大为同一 Team 或成员并发安全承诺。
- 测试中的 5 秒超时只用于防止测试卡住，未给生产 Pattern 增加超时机制。

未发现新增的未决契约歧义。非空成员仍按已确认的直接调用前提处理，
M3 将由 Team 构造器拒绝空成员；本次未定义空序列直接调用 `Sequential.run` 的保证行为。
首次实施完成时停在 M2 等待复审；后续结论见 §6.5–6.6。
Team、组合应用与真实 NOOA 集成均未实现。

### 6.5 Reviewer M2 技术复审结论

来源：用户提供的《M2 Review 报告》。以下是 reviewer 在新增两项补充测试之前的验证记录，
与 §6.4 的实施运行和 §6.6 的后续运行分开保存。

- **结论：通过，无 M2 阻塞问题，建议等待用户确认后进入 M3。**
- 适配器符合真实异步类方法、原 callable 与实例引用保持、显式桥接、无自动 context 同步的要求。
- Sequential 符合逐级交接、`None`、异常与取消传播、无重试/回滚、无执行状态和交错复用约定。
- reviewer 报告的实际结果：适配器 `6 passed in 0.11s`、Sequential `7 passed in 0.12s`、
  M2 定向 `13 passed in 0.20s`、全量回归 `16 passed in 0.20s`。
- reviewer 报告：隔离模式公共导入和适配器/Sequential 联合调用均通过。
- 单成员独立测试、适配器异步类方法结构测试、空序列文档与提交建议均为非阻塞项。
- 完整 NOOA 运行时及 FakeLLMClient 集成继续归 M4；Team 归 M3，不属于 M2 缺陷。
- 评审基于 M2 工作树；M1 有提交基线，M2 当时尚未提交。

该报告不表示用户已经授权 M3。

### 6.6 M2 评审后的测试补充

在 M2 范围内采纳了以下非阻塞建议：

- 新增适配器结构测试：检查公开 `execute` 是类上可发现的函数且为协程函数，
  防止退化为实例字段赋值。这是明确交付形状的测试，不对业务签名或协议做生产运行时校验。
- 新增独立单成员测试：输入对象与业务产物不同，结果必须是成员返回的同一对象，成员恰好调用一次。
- Sequential docstring 与 README 明确空序列调用不受支持、行为不保证；保持非空调用前提，
  没有新增空序列的运行时处理规则。空 Team 构造期检查仍在 M3。

本轮实际执行结果（Windows / Python 3.12.14 / pytest 9.1.1）：

| 验证 | 命令 | 结果 |
| --- | --- | --- |
| M2 定向 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_adapters.py tests/test_sequential.py -v` | `15 passed in 0.19s` |
| M1+M2 全量 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider -v` | `18 passed in 0.17s` |

该次运行的测试数量为适配器 7 项、Sequential 8 项、M1 基线 3 项。
没有新增依赖、真实模型或网络调用。之后的 M3 授权与提交记录见 §6.7。

### 6.7 M2 分次提交、推送与 M3 授权

用户于 2026-10-19 明确要求：“分多次提交并推送，然后开始M3”。
先完成三次提交并推送后，才开始 M3：

- `17b86d9` — `feat: add explicit callable member adaptation`
- `f4ae217` — `feat: add stateless sequential collaboration`
- `08a3da9` — `docs: record M2 acceptance and review follow-up`

已推送至 `https://github.com/1471436961/ComposeAgents` 的 `main`。
远程 `main` 与本地提交 `08a3da9a75def0ddf6f2f70d0bd4d1e22ea902e4` 已核对一致，
开始 M3 前工作区干净。环境与缓存目录未纳入提交。

## 7. M3：Team 容器

**开始条件：用户确认 M2 并授权进入 M3。**

### 7.1 交付物

- `src/nooa_patterns/team.py`：普通 Python Team，持有成员 tuple 与 Pattern，
  `execute` 委托 `pattern.run`，直接返回业务结果。
- `tests/test_team.py`，以及对应包导出、README 更新。

### 7.2 必须验证的行为

- 空成员构造时 `ValueError`。
- 成员序列取 tuple 快照：修改原始 list 不改变 Team；成员对象引用不变。
- 单成员结果保持原值与对象身份，不额外包装。
- 嵌套 Team 返回业务结果，子 Team 的 Pattern 保留，不扁平化。
- 一个仅供测试的自定义 Pattern 证明 Team 没有写死 Sequential 逻辑。
  测试用 Pattern 不算新增生产模式。
- 两个不同 Team 共享同一个 `Sequential()`，使用独立成员与 context 交错执行，
  证明 Pattern 没有进度或结果串扰；这不扩大为同一 Team / Agent 并发安全承诺。
- 异构嵌套：子 Team 输入与输出类型不同，外层下一成员明确接收子 Team 的业务输出。

### 7.3 验收与汇报

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_team.py -v
```

汇报 Team 最终内容、实际测试输出，以及 Pattern 共享和异构嵌套测试的具体断言；然后停止。
不开始组合应用、等价测试或真实 NOOA 集成。

### 7.4 M3 实施与验证记录

授权来源：用户于 2026-10-19 指示先分次提交并推送 M2，再开始 M3。
§6.7 的推送和远程提交号核验完成后，实施了本阶段。本节保留实施时验证结果，
后续 reviewer 复审见 §7.5；当时停在 M3 等待用户确认，后续授权见 §7.6。

交付物：

- `src/nooa_patterns/team.py`：普通 Python Team，不继承 NOOA Agent；只依赖两个公开协议。
- 构造时取成员 tuple 快照，空成员即 `ValueError`；`members` 只读属性返回该快照，成员对象不复制。
- `pattern` 保存传入对象引用；`execute` 只委托 `pattern.run` 并直接返回业务结果。
- 根包增加 `Team` 导出。Sequential docstring 将 Team 构造检查从未来描述改为已实现描述。
- `tests/test_team.py`：11 项用例，含 `None` / 对象两种单成员结果。
- README、AGENTS 与实施计划同步更新到 M3 本地验证完成、等待 M4 授权。

实际执行结果（Windows / Python 3.12.14 / pytest 9.1.1）：

| 验证 | 命令 / 内容 | 实际结果 |
| --- | --- | --- |
| M3 定向 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_team.py -v` | `11 passed in 0.20s` |
| M1–M3 全量回归 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider -v` | `29 passed in 0.21s` |
| 隔离递归 API | `python -I -X utf8` 导入五个公开名称，外层 Team 包含子 Team 与适配函数，子/外层共享同一个 Sequential | 输入 `3` 返回 `8`，context 为 `["add", "double"]` |

测试覆盖空成员、tuple 快照与成员身份、单成员结果、跨 Team 共享有状态成员、
自定义 Pattern 委托、保留子 Team Pattern、共享 Sequential、异构嵌套、异常和取消。

共享 Pattern 测试的具体断言：

- `team_a.pattern is team_b.pattern is pattern`，没有复制 Pattern。
- A 在首成员的事件上暂停，B 在 A 恢复前完成；B 完成后 A 仍未结束，然后才释放 A。
- A/B 分别返回 `final_a` / `final_b` 的同一对象。
- A 的后续成员收到 `middle_a` 与 `context_a`；B 收到 `task_b` / `middle_b` 与 `context_b`。
- A context 仅为 `["paused", "resumed"]`，B context 仍为空，无相互写入。
- 两个 Team 使用独立成员与 context，不承诺同一 Team 或同一 Agent 的并发调用安全。

异构嵌套测试的具体断言：

- 子 Team 接收整数 `3`，内部经历 `int → tuple[int, int] → str`，业务输出为 `"3 + 4"`。
- 外层下一成员接收的就是这个字符串对象，不是中间 tuple 或容器执行状态信封。
- `received[0] is child_output`，最终 `result is business_result`，结果为 `{"formula": "3 + 4"}`。
- 同一个 context 记录的顺序为 `["expand", "format", "consume"]`。

另一个嵌套测试令子 Team 使用仅供测试的无状态 `_FirstOnly`，外层使用 Sequential：
子 Team 的未选中成员不执行，外层后续成员接收选中成员的业务结果，证明没有扁平化子结构。
该测试 Pattern 不是新增生产模式。

本阶段没有新增依赖、模型/网络调用、图校验器或生命周期管理，也未修改 NOOA 参考源码。
测试的 5 秒超时仅用于防卡死。M4 的组合示例、应用等价测试与真实 NOOA 集成均未开始。

### 7.5 Reviewer M3 技术复审结论

来源：用户提供的《M3 Review 报告》。以下为 reviewer 报告中的独立验证结果，
与 §7.4 的实施运行分别记录，不作为本次文档更新中新执行的测试。

- **结论：通过，无 M3 阻塞问题。**
- reviewer 报告：Team 定向测试 `11 passed in 0.15s`，全量回归 `29 passed in 0.21s`。
- 隔离模式下五个公共名称导入和递归 Team 冒烟调用通过：输入 `3`，结果 `8`，
  context 为 `["add", "double"]`。
- 空成员拒绝、成员快照与引用、单成员、嵌套与自定义 Pattern 委托、共享 Sequential、
  异构业务结果交接、异常及取消均符合约定；未发现需要返工的实现或文档问题。
- M3 修改仍在工作树中，尚未提交；这是非阻塞的追溯性事项，不改变技术复审结论。
- 完整 NOOA 运行时安装、依赖验证和公开 FakeLLMClient 集成仍属于 M4 待办。

该报告本身不构成 M4 授权；用户之后明确确认，见 §7.6。

### 7.6 M3 分次提交与 M4 授权

用户于 2026-10-19 指示“分多次提交并推送，然后开始M4”。执行顺序为先提交与推送 M3，
核对远程分支后再开始 §8，不把该授权扩展到新增 Pattern 或角色库。

- 提交前实际全量回归：`python -X utf8 -m pytest -p no:cacheprovider -q`，
  结果为 `29 passed in 0.20s`；`git diff --check` 通过。
- 实现与契约测试提交：`74ec24e`，`feat: add recursive team composition with contract tests`。
- 文档独立提交：`59b36c4`，`docs: record M3 acceptance and M4 authorization`，保留实施与复审的独立记录。
- 已推送到 `origin/main`，本地 HEAD 与远程 `refs/heads/main` 均为
  `59b36c48808a269c3efff8e5523b4777e7f71774`；核验后开始 M4。

## 8. M4：组合示例 + 等价测试 + NOOA 适配

**开始条件：用户确认 M3 并授权进入 M4。**

### 8.1 交付物

- `examples/composed_flows.py`：使用 Team + Sequential + as_member 重写两条手写基线。
- `tests/test_equivalence.py`：手写流程与组合流程对照。
- `tests/test_nooa_adapter.py`：公开 FakeLLMClient 驱动真实 NOOA Agent。
- 对应 README、导出和实施计划状态更新。

### 8.2 等价测试要求

- 两种流程复用相同业务逻辑，避免因重写业务函数而混淆对照。
- 手写版与组合版分别创建新的 context 和有状态 fake 成员。
  禁止先运行手写版，再把已污染的实例或 context 用于组合版。
- 跨运行比较业务值、调用顺序、context 修改；引用身份在每次运行内部检查。
- 不把不同运行之间的对象身份相等当作要求。
- 流程 B 仍然是方案 → 意见，不增加退回修改或再次审查。

### 8.3 NOOA 集成要求

- 先安装和验证完整 NOOA 依赖，确认 `import nooa` 成功且依赖检查通过。
  当前仅声明 Git `main` 依赖，不代表该安装验证已经完成。
- 在编写测试前核对实际使用版本的公开 FakeLLMClient 用法，必要时只读查看源码。
- 驱动真实 NOOA Agent 的公开方法，确认适配后仍经过 NOOA 原生调用链。
- 对照直接调用和适配调用的类型校验行为，不能把弱类型协议误报为绕过 NOOA 校验。
- 全部模型响应由公开 FakeLLMClient 提供，不访问真实模型，不需要真实模型凭据。
- 不使用 NOOA 私有 runtime API，不修改参考源码以使测试通过。

依赖安装与检查示例（以实际环境验证为准）：

```powershell
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe --editable .
uv --cache-dir .uv-cache pip check --python .venv/Scripts/python.exe
.\.venv\Scripts\python.exe -X utf8 -c "import nooa; print(nooa.__file__)"
```

### 8.4 验收与汇报

```powershell
.\.venv\Scripts\python.exe -X utf8 examples/composed_flows.py
.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider -v
```

汇报组合与手写基线的对比、等价断言、NOOA 适配测试细节、完整实际测试输出，
以及“是否值得继续扩展”的判断。微型 fake 流程只验证抽象与协调逻辑，
不能代替真实多智能体应用对价值的验证。新增模式或角色库另行讨论和确认。

### 8.5 M4 实施与依赖环境

授权来源：用户于 2026-10-19 指示“分多次提交并推送，然后开始M4”。
在 §7.6 的 M3 两次提交推送并核对远程提交号之后开始本阶段，未提前实现后续模式。

交付物：

- `examples/composed_flows.py`：以 Team + Sequential + as_member 重写两个流程，业务函数仍来自
  `manual_flows.py`；兼容直接脚本运行与作为 examples 模块导入，未修改手写基线。
- `tests/test_equivalence.py`：3 项测试，覆盖资料报告和通过 / 不通过两种变更意见。
- `tests/test_nooa_adapter.py`：3 项真实 NOOA 测试，使用公开 Agent、strategy、PredictStrategy、
  PredictConfig、FakeLLMClient 和事件查询接口，不使用私有 runtime API。
- `uv.lock`：锁定 75 个跨平台依赖条目，NOOA 为 `0.0.11.dev433`，Git 提交
  `1454b78c8f0a85c97eab1c6a91cc8cfc95b34de5`。保留 pyproject.toml 原有 main 声明，
  通过 `uv sync --locked` 使用已解析提交，不在每次验证时追踪分支更新。
- `docs/validation/M4_PYTEST.txt`：禁网 Linux 完整 pytest 原始输出；README 与 AGENTS 同步当前状态。

环境与安装记录：

1. Windows 执行 `uv --cache-dir .uv-cache sync --python .venv/Scripts/python.exe` 成功，
   `uv pip check` 检查 75 个包并报告全部兼容。
2. 随后的 `python -I -c "import nooa"` 失败：上游 `nooa/storage/sqlite.py` 无条件导入
   Unix `fcntl`，原生 Windows 缺少该模块。没有写 shim、替换模块或修改 NOOA 使其假通过。
3. 使用机器已有的 Ubuntu-24.04 WSL，Linux uv 0.11.12 位于 `.uv-cache/wsl-tools/uv`；
   独立虚拟环境位于 `.uv-cache/wsl-venv`，包缓存位于 `.uv-cache/wsl-packages`，均已被忽略。
   WSL 直连 GitHub 超时后，将本项目 Windows uv 已取得的同一 Git 提交填入 WSL Git 缓存，
   再运行 `sync --locked` 成功；没有使用或改动只读 NOOA 参考源码进行安装。
4. WSL 依赖检查报告 74 个包全部兼容；在禁网命名空间下隔离导入 NOOA 成功，
   版本为 `0.0.11.dev433`，路径位于 WSL 虚拟环境的 site-packages。
5. 模型响应均由严格响应耗尽模式的 FakeLLMClient 提供；PredictConfig 的 max_retries 为 1，
   避免用无限 fake 响应掩盖意外调用。客户端由测试的异步上下文管理器关闭。
   公开 `enable_tracing(exporters=[])` 避免自动 viewer 探测与网络导出；
   LiteLLM 使用本地模型元数据，测试 fixture 拒绝 IP 连接，并允许 asyncio 的本地 socketpair。
6. 额外通过 Linux `unshare --net` 隔离整个测试进程的网络；完整验收没有依赖真实模型或凭据。

### 8.6 M4 实际验证记录与断言

本节保留实施时运行记录；当时尚未获得独立 reviewer 技术复审，后续复审结果见 §8.8。

| 验证 | 实际环境 / 命令 | 结果 |
| --- | --- | --- |
| 组合示例 | Windows `python -X utf8 examples/composed_flows.py` | 正常退出，报告与意见断言通过，事件分别为 analyze/report、plan/review |
| 隔离等价测试 | Windows `python -X utf8 -m pytest -p no:cacheprovider tests/test_equivalence.py -v` | `3 passed in 0.15s` |
| Windows 回归 | `python -X utf8 -m pytest -p no:cacheprovider -q` | `32 passed, 1 skipped in 0.36s`；跳过 fcntl 不可用的 NOOA 集成模块 |
| Linux 依赖与导入 | `uv pip check`；`unshare --net python -I -X utf8 -c "import nooa"` | 依赖全部兼容，NOOA 导入成功 |
| 真实 NOOA 定向测试 | WSL Python 3.12.3 / pytest 9.1.1，禁网执行 test_nooa_adapter.py | `3 passed in 102.60s`；首次导入主要受 Windows 挂载盘文件 I/O 影响 |
| 完整回归 | 同一 WSL 环境，禁网执行全部 tests | `35 passed in 46.14s`，无跳过 |
| Linux 示例与隔离包导入 | 两种示例、`python -I` 导入五个公开名称，均在禁网环境执行 | 两种示例断言通过；隔离导入成功 |

Linux 实际完整验收命令（在项目根目录的 Linux shell 执行）：

```bash
UV_PROJECT_ENVIRONMENT=.uv-cache/wsl-venv .uv-cache/wsl-tools/uv --cache-dir .uv-cache/wsl-packages sync --locked --python python3
.uv-cache/wsl-tools/uv --cache-dir .uv-cache/wsl-packages pip check --python .uv-cache/wsl-venv/bin/python
set -o pipefail
unshare --net .uv-cache/wsl-venv/bin/python -X utf8 -m pytest -p no:cacheprovider -v 2>&1 | tee docs/validation/M4_PYTEST.txt
```

完整实际输出保存在 [M4_PYTEST.txt](validation/M4_PYTEST.txt)，35 = M1 3 + M2 15 + M3 11 + M4 6。
Windows 的平台跳过不计作 NOOA 集成通过；M4 的完整验收依据是 Linux 35 项全部通过。

等价对照的具体断言：

- 每次分别创建 ResearchContext / ChangeContext 和新的有状态步骤对象，初始 calls 为 0、events 为空。
- 每次执行仅调用两步；首成员收到该次 task，第二成员收到首成员返回的同一 Analysis / ChangePlan。
- 同一 context 引用贯穿各次运行的两步，最终结果是末成员返回的同一对象。
- 跨运行的成员、context 和 events 列表身份不同；跨运行比较中间业务值、最终结果、
  完整 context 值和事件顺序，均相等；不要求跨运行对象身份相等。
- 不通过的审查意见也保持两步事件顺序，不增加修改、循环或重审。

NOOA 适配的具体断言：

- 直接调用和 Team + 显式桥接 + as_member 调用分别创建新的真实 ScoringAgent 与 FakeLLMClient。
- 成功时两者都返回同值的 ScoreCard，fake 仅调用一次且响应已耗尽；
  请求的 output_model 就是 ScoreCard，消息中包含输入，公开事件查询可取得原生 Task 和 LLMResponse。
- NOOA agent.context 的对象身份保留；应用 context 仅由显式桥接写入 score，不自动同步。
- 故意传入 int 违背方法的 str 注解，两条路径抛出相同 TypeError 文本；fake 调用数为 0，响应仍未消耗。
- 返回非法整数字符串，两条路径均抛原生 GenerationError，其 cause 为 Pydantic ValidationError；
  score 字段的结构化校验错误相同，fake 恰好调用一次，没有库级重试或错误结果包装。
- 每个测试检查 IP 连接尝试列表为空；完整进程额外禁网，仍运行成功。

收尾核对：完整执行契约与已提交基线逐字一致，生产源码、pyproject.toml、手写示例与其测试无 diff；
文档本地链接、锁文件提交号和完整输出中的 35 项通过记录检查成功，`git diff --check` 通过。
只读 NOOA 参考目录的 1500 个文件 SHA-256 均与本轮快照一致。全量测试后只更新文档，未重复运行测试。

### 8.7 价值判断与停止状态

两个业务场景证明相同的顺序协调可以复用；Team 的递归语义和与 NOOA 原生校验的边界也有实际证据。
但两步手写 await 本来比构造 Team 更短，不能用这些示例宣称代码量减少或完整应用效率提升。

建议保留已验证的薄组合内核，下一步用一个实际 NOOA 应用验证复用价值，
只在再次出现相同协调需求时添加能力；当前没有证据支持提前扩展更多 Pattern 或角色库。
Predict 路径通过也不等于已覆盖 NOOA 的全部 CodeAct、沙箱、MCP 或 Skill 行为。

本阶段未修改生产库 API、原有手写基线、完整执行契约或 NOOA 参考源码。
M4 后续技术复审已通过，见 §8.8；用户随后指示提交推送，交付记录见 §8.9。后续扩展另行确认。

### 8.8 Reviewer M4 技术复审结论

来源：用户提供的《M4 Review 报告》。以下为 reviewer 的独立运行记录，
与 §8.6 的实施运行分别保留；未用本次文档更新覆盖原始 M4_PYTEST.txt 或冒充新执行的测试。

- **结论：通过，按 Linux / WSL 35 项全部通过的 M4 验收基线，无阻塞项。**
- 组合示例、隔离等价测试、真实 NOOA Agent + 公开 FakeLLMClient 集成、锁文件与验证证据均符合要求。
- reviewer 报告的独立结果：

| 验证 | reviewer 报告的结果 |
| --- | --- |
| Windows 组合示例 | 正常退出，两条流程断言通过 |
| Windows 等价测试 | `3 passed in 0.05s` |
| Windows 回归 | `32 passed, 1 skipped in 0.22s`；跳过 NOOA 集成模块 |
| WSL 禁网完整回归 | `35 passed in 59.00s`，无跳过 |
| WSL 其他检查 | 两种示例、隔离公共 API 导入及 NOOA 导入通过；74 个已安装包依赖全部兼容 |

reviewer 复现了锁定 NOOA 在原生 Windows 上的 fcntl 导入失败，确认项目未使用 shim、
替换模块或修改 NOOA 伪装通过。这是当前基线已记录的上游平台限制；
如后续把原生 Windows NOOA 运行列为产品硬要求，需要另行决策，不能视为现已支持。

reviewer 未发现生产 API、契约、作用域或测试隔离问题，支持保留薄内核并用真实应用继续验证价值。
该复审基于当时的 M4 工作树；当时新增示例、两个测试、uv.lock、原始输出及文档尚未提交，
reviewer 建议后续提交时一并保留这些可追溯证据。后续执行见 §8.9。

该复审本身不构成用户最终验收、提交推送或后续扩展的指示。之后的提交推送授权见 §8.9。

### 8.9 M4 分次提交与交付

用户于 2026-10-19 明确指示“提交并推送”。本次按职责分组提交已复审内容，
未改变已验证的代码、锁文件或原始测试证据，未开始后续应用或模式扩展。

| 分组 | 提交 | 内容 |
| --- | --- | --- |
| 组合示例与等价对照 | `d4d1b76`：`feat(examples): compose sequential baselines with teams` | composed_flows.py 与 test_equivalence.py |
| 原生 NOOA 集成与依赖证据 | `59d2c89`：`test: lock and verify native NOOA integration` | test_nooa_adapter.py、uv.lock 与 M4_PYTEST.txt |
| 验收与交付文档 | `docs: record M4 acceptance and delivery` | README、AGENTS 与实施计划，包括实施和 reviewer 独立运行记录 |

提交前已核对：生产库与 M3 基线无 diff、锁定提交号正确、原始证据包含 35 项通过且无跳过，
新文件无尾随空白，`git diff --check` 通过。此次仅整理提交与更新文档，未重复运行 pytest；
此前实施与 reviewer 的验证结果分别保留在 §8.6、§8.8。

推送目标为 `origin/main`，推送后核对本地 HEAD、远程跟踪分支与服务器端 main 提交号；
实际推送结果在本次交付回复中报告，Git 历史是提交与远程状态的可追溯依据。

## 9. M5：Parallel

用户已授权设计与 Parallel，实现、本地验证与 reviewer 技术复审均已完成，无阻塞项；用户随后指示提交推送，见 §9.10。
M5 不增加 Router / Loop 源码、测试、导出或占位类，不创建复合模式与协作体系。
真实 NOOA 集成继续按 Linux / WSL 验收：锁定上游在原生 Windows 导入 fcntl 失败。
M5 自身使用确定性 fake，不调用真实模型；完整回归保留 M4 的三项真实 NOOA + FakeLLMClient 测试。

### 9.1 入口和成员归属

```python
Parallel()
async def run(self, members: Sequence[TeamMember], task: Any, context: Any) -> list[Any]: ...
Team(members=[...], pattern=Parallel())
```

Parallel 不持有成员和配置参数。空成员在 **Team 构造时**抛 ValueError，沿用现有容器职责。
直接调用 Parallel.run 时也拒绝空序列，作为此模式明确的额外边界检查；不改变 Sequential
对直接空序列调用不作保证的既有约定。

### 9.2 输入、结果和并发

- 所有成员接收调用入口的同一个 task 和同一个 context 引用，不使用前一成员的返回值。
- task 和 context 都可能被并发修改，调用者负责两者的并发安全；库不加锁、不复制或自动合并。
- 正常完成时返回新建的结果 list，严格按成员顺序排列，与完成顺序无关。
- list 中每个元素是对应成员返回的原对象；不复制、不展开子列表，不过滤 None。
- 单成员返回单元素列表，包含 None 也不特殊处理；该行为不同于单成员 Sequential。
- 并发指协作式异步执行，不保证 CPU 并行、耗时变短或阻塞代码能及时被取消。
- 重复引用同一有状态成员仍是同一对象，不保证该对象的并发重入安全。

挑战：只有共同的 execute 签名不能保证成员适合相同输入，也不能保证下游能接收 list。
异构报告属于业务结果；list[Report] 与一个 Report 是不同的下游契约。

### 9.3 快速失败的精确含义

- 任一成员的异常被调度器观察到后，立即向其他尚未结束的直接子任务发出取消请求。
- 等待所有本次创建的成员任务结束并取走其异常后，传播原先触发失败的同一个异常对象。
- 不返回部分结果、不把异常塞进结果列表、不包装为 ExceptionGroup、不重试、不回滚已发生副作用。
- 多个异常同时出现时，不保证选择成员顺序最靠前者；传播最先被调度器观察到的异常。
- 取消清理中其他成员再次抛异常，不覆盖原先的业务异常；这些异常仍被取走，避免遗留未处理任务。
- “快速”指取消决定不等待其他正常工作完成，不承诺异常立即返回。清理必须 await；
  成员屏蔽取消、阻塞事件循环或清理不结束时，Parallel 也可能继续等待，首版不内置超时。

实现使用显式 asyncio 子任务与 gather；不能只使用默认 gather，因为普通成员失败不会自动取消其余成员。
也不直接使用 TaskGroup 的默认异常分组行为，以保留既有原异常传播契约。
内部收集 future 使用 shield，外层取消在 run 内显式转交给子任务，再等待收集 future 与全部子任务；
shield 不是让成员逃避取消，而是避免成员清理异常把外层 CancelledError 替换掉。

### 9.4 外层与成员取消

- 外层调用被取消时，所有尚未完成的成员任务都收到取消请求，等待结束后向外传播 CancelledError。
- 已经完成的成员不会被追溯取消，其副作用也不撤销。
- 成员吞掉取消后正常返回也不会把已取消的整个 run 改成成功。
- 成员自行取消或抛 CancelledError 同样中止本次汇集，取消其他未完成成员，不作为普通结果返回。
- 如果清理过程中外层又被取消，取消仍可向上传播，不能把取消包装成业务错误。
- 只管理本次直接等待的调用链；不接管成员私自创建的后台任务，也不保证外部服务副作用被撤销。
- 取消正在运行的嵌套 Parallel Team 应递归传入其直接子任务；测试验证这条等待链。

### 9.5 无执行状态与资源

任务列表、当前结果、异常与取消进度全部属于一次 run 的局部变量。
同一 Parallel 实例可被独立 Team / context 共享；一个运行失败不得取消另一个运行。
此约定不扩大为同一 Team、同一有状态 Agent 或共享对象的并发安全保证。

### 9.6 验收案例与手写对照

输入为具体业务类型 Proposal(text, goal)，输出按位置组织为：

```text
[FeasibilityReport, RiskReport, CostReport]
```

三个普通 fake 异步业务函数各自接收 Proposal 和调用者创建的 ReviewContext。
共享 context 只承载应用主动写入的观察记录，不要求并发完成顺序固定。
可用普通函数 aggregate(reports) 生成 AnalysisBundle；它不是 Pattern，也不做路由。

组合版本：Team([as_member(feasibility), as_member(risk), as_member(cost)], Parallel())。
手写版本显式 create_task 后 await gather，并在失败/取消时取消和等待剩余任务；
不能用三个串行 await 冒充并发等价对照，也不能用未取消兄弟任务的默认 gather 冒充契约等价。
两版运行使用新 context 与新的有状态观察成员，业务逻辑相同，跨运行只比较业务值。
并发事件次序本身不作保证，观察记录比较事件多重集；报告列表仍严格比较成员顺序与各次运行内部身份。

递归在 M5 通过外层 Sequential 包含分析 Parallel 子 Team 和显式聚合成员来验证。

#### 9.6.1 原验收描述中必须修正的两处

1. 分析子 Team 不能直接成为“按 AnalysisBundle 选审查者”的 Router 的一个审查分支：
   selector 需要先取得分析与聚合产物。完整数据流应为外层 Sequential：
   **分析 Parallel 子 Team → 普通聚合函数 → Router(安全 / 架构 / 快速审查者)**。
   Router 仍留到 M6，本轮没有 selector 或审查分支实现。
2. Proposal → 三种独立 Report 的成员不兼容 Sequential 的逐级交接。
   直接换模式会让风险成员收到 FeasibilityReport，而不是 Proposal；即使改为能接收，
   Sequential 的末结果仍不是三报告列表。M5 用输入输出兼容的成员验证“保持成员、替换模式”，
   并明确断言输出形状不同。M6 若要让同一业务案例可替换，须设计显式业务载体/桥接与聚合，
   不能修改 Sequential 的既有交接语义或让库猜测、收集被丢弃的中间报告。

最可能出问题的环节是下游聚合的输入形状、共享可变 task/context 的并发修改，以及取消后资源清理。
这些问题不能靠统一签名或更换 Pattern 自动解决。

### 9.7 文件、顺序与测试

1. 先保存本计划，更新 README / AGENTS 入口，明确只授权 M5。
2. 实现 src/nooa_patterns/patterns/parallel.py，更新两个包导出，维护 README 和协议完整契约。
3. tests/test_parallel.py 验证：
   - 确实重叠运行；反向完成仍按成员顺序汇集，task/context 保持同一引用。
   - 单成员对象与 None、嵌套列表身份保持；空 Team 构造与直接空 run 拒绝。
   - 一个成员失败时其余成员真实收到取消；await 清理结束后才传播原异常，副作用保留。
   - 外层真实 Task.cancel() 传播到全部未完成成员，等待异步清理。
   - 成员自行取消、多个同时异常、取消清理抛错，以及嵌套 Team 的取消等待链。
   - 共享同一 Parallel 的独立运行没有任务/异常/取消串扰。
   - 契约兼容的相同成员可替换 Sequential / Parallel，分别返回业务值 / 业务值列表。
4. examples/parallel_review.py 保存三分析成员子 Team、普通聚合与手写并发对照。
   tests/test_parallel_review.py 验证隔离运行的成功与失败对照、异构报告、递归交接。
5. 实际运行定向测试与示例，再进行一次包含 M4 集成的禁网 WSL 全量回归；
   完整输出保存 docs/validation/M5_PYTEST.txt，区分 Windows 的平台跳过与 Linux 无跳过结果。
6. 汇报契约挑战、最终实现、接口、例子、测试结果和剩余设计问题，然后停止。

测试用 asyncio.Event 控制交错与取消，超时只用于防止测试挂死，不靠耗时阈值证明并发。
不新增依赖、签名推断、可配置失败策略、字典结果或完整图引擎。

### 9.8 实施与本地验证记录

#### 9.8.1 实际交付和边界

先保存本计划与入口，再实现 [Parallel](../src/nooa_patterns/patterns/parallel.py)、
更新导出、README 和协议完整契约；之后添加 [核心测试](../tests/test_parallel.py)、
[三分析成员示例](../examples/parallel_review.py) 与 [案例测试](../tests/test_parallel_review.py)。
Team、Sequential、适配器、M1 手写基线、pyproject.toml、uv.lock 和 M4 原始验证输出未修改。
没有 Router / Loop 源码、测试、导出或占位类，也未新增依赖、角色库、复合 Pattern。

实现中遇到并修复一处真实的取消边界问题：直接等待 gather 时，外层取消后，成员清理抛出的
RuntimeError 可能覆盖 CancelledError。新增回归测试先实际失败，再通过 shield 收集 future、
显式取消并等待全部任务修复；修复后的完整回归见下文。shield 不阻止库向成员转交取消。

#### 9.8.2 关键测试断言

- 17 项核心测试使用 Event 控制交错，不用完成耗时推断并发：三个成员全部开始后才允许完成，
  让它们反向完成，结果仍按成员顺序且保留原对象身份；同一个 task/context 传到所有成员。
- 单成员对象 / None 保持单元素列表；中间嵌套列表不展开；空 Team 构造与直接空 run 均抛 ValueError。
- 业务失败后其他成员真实收到取消，清理阻塞期间 run 不结束；释放清理后传播同一原异常，
  所有已创建任务结束、既有副作用保留、成员不重试。
- 外层取消传到全部未完成成员并等待异步清理；自行取消、清理抛错、同时失败、
  失败清理期间外层取消、吞掉取消等情况均覆盖。嵌套取消到达内外等待链，完成的工作不撤销。
- 两个 Team 共用同一个 Parallel，B 失败取消自己的成员时，A 的等待成员不受影响，之后正常返回。
- 相同兼容成员替换 Sequential / Parallel，前者返回业务值，后者返回列表；不宣称任意类型兼容。
- 5 项案例测试分别使用新的有状态观察成员和 context；跨运行比较业务值与事件多重集，
  引用身份在每次运行内部检查。失败对照分别验证手写版 / 组合版的兄弟取消。
- 递归案例使用 Sequential([Parallel 分析子 Team, 显式聚合成员])，子 Team 不扁平化，
  聚合字段保持对应报告身份；普通业务聚合拒绝报告数量或类型位置错误。

#### 9.8.3 本次实际运行

Windows / Python 3.12.14 / pytest 9.1.1，项目根目录：

```powershell
.\.venv\Scripts\python.exe -X utf8 examples\parallel_review.py
# exit 0；Handwritten and composed concurrent analyses passed.

.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_parallel.py tests/test_parallel_review.py -v
# 22 passed in 0.17s

.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider -q
# 54 passed, 1 skipped in 0.31s

.\.venv\Scripts\python.exe -I -X utf8 -c "from nooa_patterns import Parallel, Pattern, Sequential, Team, TeamMember, as_member; print('isolated six-name import OK')"
# isolated six-name import OK
```

Windows 跳过的是锁定 NOOA 无法导入 fcntl 的集成模块，不是本次 22 项测试。
完整验收继续使用 WSL Ubuntu 24.04 / Python 3.12.3 / pytest 9.1.1：

```bash
set -o pipefail
unshare --net .uv-cache/wsl-venv/bin/python -X utf8 -m pytest -p no:cacheprovider -v 2>&1 | tee docs/validation/M5_PYTEST.txt
# 57 passed in 48.97s，无跳过
```

57 = 原有 35 + 本次 22，包含三项真实 NOOA + 公开 FakeLLMClient 集成，全部在禁网命名空间中通过。
原始输出保存于 [M5_PYTEST.txt](validation/M5_PYTEST.txt)，M4 旧记录保持不变。
与已有 SHA-256 只读参考快照逐一比较，NOOA 的 1,500 文件均未变化，文件集合也无增删。

#### 9.8.4 当前交付状态

M5 已完成实现与本地验证，并通过 reviewer 技术复审（见 §9.9）；用户随后指示提交推送，交付记录见 §9.10。
M5 当时停在本阶段等待确认；用户随后授权 M6，见 §10。M7 Loop 仍未授权。

### 9.9 Reviewer M5 技术复审结论

来源：用户提供的《M5 Review 报告》。结论为 **通过，无 M5 阻塞项**。
以下是 reviewer 的独立运行记录，与 §9.8.3 的实施运行分别保留；本次状态更新没有重跑测试或覆盖 M5_PYTEST.txt。

| 验证 | reviewer 报告的结果 |
| --- | --- |
| Windows M5 定向 | `22 passed in 0.12s` |
| Windows 全量 | `54 passed, 1 skipped in 0.22s`；跳过仍为上游 fcntl 限制的 NOOA 集成模块 |
| WSL 禁网完整回归 | `57 passed in 49.49s`，无跳过 |
| 示例与导入 | Windows / WSL 示例正常退出；六个公共名称隔离导入通过 |

复审确认 Parallel 的引用、结果顺序、快速失败、取消清理、嵌套与独立复用均符合契约，范围未超出 M5。
空生成器不属于当前 Sequence 参数契约，无需因此扩大接口；Router / Loop 的未决设计留到各自阶段。
复审本身不构成提交推送或进入 M6 的授权；用户随后明确指示提交推送，见 §9.10。后续 M6 的澄清确认与实现授权见 §10。

### 9.10 M5 分次提交与交付

用户于 2026-10-19 明确指示“提交并推送”。按职责分三组交付，未开始 M6 / M7：

| 分组 | 提交 | 内容 |
| --- | --- | --- |
| Parallel 与核心契约测试 | `285264e`：`feat: add fail-fast parallel team execution` | Parallel、公共导出、协议 docstring、17 项核心测试 |
| 并发案例与验证证据 | `52be0d4`：`test(examples): verify parallel review composition` | 三分析成员示例、5 项案例测试、M5_PYTEST.txt |
| 计划、契约与交付文档 | `docs: consolidate roadmap and record M5 acceptance` | README、AGENTS、唯一实施计划；包含用户确认的文档组织原则与独立复审记录 |

提交前核对了变更范围、Python 语法、文档链接和空白；原有 Team / Sequential / 适配器、
依赖声明、锁文件与 M1 / M4 基线保持不变。代码和测试未在复审后改动，本次未重复运行 pytest；
实施结果与 reviewer 独立结果分别保留在 §9.8.3、§9.9。
已推送 origin/main，交付时核对本地 HEAD、远程跟踪分支与服务器端 main 均为 2cc65b580fb0273e59d0b4aacb2af0f6b0912932，工作树干净。

## 10. M6：Members 与 Router

用户已确认以下契约并授权实现，现已完成实现、本地验证与 reviewer 技术复审，用户随后指示提交推送，见 §10.8。本阶段只做 Router 所需的成员接口、声明式检查和验收案例；
不实现 Loop，不改变 Sequential / Parallel 的交接、汇集、失败或取消语义。完成后汇报并停止。

### 10.1 成员归属与构造时检查

- Team 接受 Sequence[TeamMember] 或 Mapping[str, TeamMember]，统一保存为轻量 Members。
- Members 支持迭代成员、长度、整数 / 名称访问、has_name(name)；提供只读 names 元组供错误消息列出名称。
- 对序列或映射取浅快照，保持顺序和成员引用；无增删接口。Team.members 从原 tuple 升级为 Members，
  这是本阶段明确授权的接口扩展。旧阶段的 tuple 描述与断言作为历史约定保留，不代表 M6 仍返回 tuple。
- Pattern 声明类属性 requires_named_members: bool = False；Sequential / Parallel 显式声明 False，Router 为 True。
  Protocol 不给结构类型自动安装默认值；未声明属性的既有自定义 Pattern 按 False 处理，不依据名称或签名猜测。
- Team 构造时检查声明：要求命名但输入不是 Mapping，立即 ValueError("Router requires named members")；
  同样声明要求的自定义 Pattern 使用其类名描述错误。空映射 / 空序列仍在构造时拒绝。
- Pattern.run 的成员标注改为 Members；Sequential / Parallel 执行逻辑保持不变。

### 10.2 Router 执行契约

```python
Router(selector: Callable[[Any, Any], str])
async def run(self, members: Members, task: Any, context: Any) -> Any: ...
Team({"security": ..., "architecture": ..., "quick": ...}, Router(selector))
```

- selector 应是纯函数式的同步决策，不应调用 LLM 或做 I/O；模型决策由前置异步成员完成，selector 只读其产物。
- 每次只调用一次 selector，只执行一次选中成员；task / context 原样传给两者，成员结果原样返回，包括 None。
- selector 抛异常直接传播；未命中抛 LookupError，消息包含返回名称与有序可用名称列表。
  selector 返回非字符串时抛 TypeError，不把整数当索引、不支持异步 selector 或双协议推断。
- 不吞异常、不包装、不自动重试、不回滚、不注入 context、不管理资源；取消传到被选成员。
- 只有 selector 属于固定配置；本次名称和结果仅在局部变量中，同一 Router 可跨独立 Team 复用。
- 直接调用 run 也要求非空命名 Members；Team 的声明式构造检查仍是正常入口的提前失败保证。

### 10.3 验收案例与契约兼容替换

应用定义 ReviewRequest(proposal, bundle)，不是库级结果封装。数据流为：
Proposal → Parallel 分析子 Team → 显式普通聚合 → ReviewRequest → Router → 审查意见。
审查者收到原方案、目标与三份报告；原任务由应用显式桥接携带，库不向 context 自动注入。
复用 M5 的确定性分析业务，保留纯 await 的手写并发 / 聚合 / 分支对照，覆盖高、中、低风险。
同一次运行内检查引用，跨运行使用新 context 与有状态成员并比较业务值和事件，不强制并发事件次序。

契约兼容替换：同一组业务成员换 selector，验证分支变化且成员引用不变；
也验证 Mapping 供 Sequential / Parallel 使用时按映射顺序执行，不把名称作为成员。
不把 Parallel 换成 Sequential 宣称为等价替换；改变 Pattern 时仍须匹配输入输出契约。
可选的“Pattern 与下游一起改”语义变更案例不作为本阶段必交付。

### 10.4 实施顺序与验收

1. Members 与 tests/test_members.py：序列 / 映射顺序、名称 / 索引、快照、成员引用及空容器。
2. Pattern 声明、Team 检查与 Members 委托，迁移原 tuple 形状测试；既有执行语义回归。
3. Router 与 tests/test_router.py：构造时拒绝未命名、空映射、未命中消息、selector 一次、
   原引用、结果 / None、异常 / 取消、子 Team、共享 Router 与 selector 替换。
4. examples/router_review.py 与 tests/test_router_review.py：三风险分支、手写 / 组合隔离对照、
   原方案和报告引用、递归以及构造错误发生在任何分析副作用之前。
5. 实际运行定向测试、示例与 Windows 回归；WSL 禁网运行包括 NOOA 集成的全量回归，
   完整逐项输出保存 docs/validation/M6_PYTEST.txt。结果取得后再记录，不预填通过。
6. 汇报最终接口、完整测试输出、手写 / 组合对比及 Loop 是否必要的判断；停止等待 review 与用户确认。

### 10.5 实施与本地验证记录

交付 [Members](../src/nooa_patterns/members.py)、[Router](../src/nooa_patterns/patterns/router.py)、
声明式属性与 Team 检查、导出、完整契约，以及 [评审案例](../examples/router_review.py)。
原 test_team 的 tuple 形状断言按授权迁移为 Members，其余交接、引用、异常、取消断言保留。
AST 比较确认 Sequential / Parallel 的 run 执行语句未变，仅调整成员标注、导入和固定类声明。

| 本次实际检查 | 结果 |
| --- | --- |
| Members 10 + Router 21 + 案例 7 | `38 passed in 0.18s` |
| Windows 全量 | `92 passed, 1 skipped in 0.44s`；仍跳过上游 fcntl 限制的 NOOA 模块 |
| WSL Ubuntu 24.04 / Python 3.12.3 禁网全量 | `95 passed in 27.36s`，无跳过，包含原 NOOA 三项集成 |
| Windows 示例 | 三种风险均命中预期审查者，手写 / 组合断言通过，退出 0 |
| WSL 禁网示例 | `unshare --net` 运行 router_review.py，同样通过三风险分支对照，退出 0 |
| Windows 隔离导入 | `python -I` 导入八个公共名称成功 |

Windows / Python 3.12.14 / pytest 9.1.1 实际命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 examples\router_review.py
.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_members.py tests/test_router.py tests/test_router_review.py -v
.\.venv\Scripts\python.exe -X utf8 -m pytest -p no:cacheprovider -v
```

WSL 全量实际命令（pytest 9.1.1），完整 95 项逐项输出保存在 [M6_PYTEST.txt](validation/M6_PYTEST.txt)：

```bash
set -o pipefail
unshare --net .uv-cache/wsl-venv/bin/python -X utf8 -m pytest -p no:cacheprovider -v 2>&1 | tee docs/validation/M6_PYTEST.txt
```

38 项新增测试覆盖 §10.4 全部条款，另验证自定义命名声明、旧自定义 Pattern 的默认 False、
非字符串选路、共享 Router 无串扰和完整流水线分析失败时不进入 selector。
手写 / 组合的三风险测试各自创建新 context、有状态审查成员与分析观察器；
跨运行比较业务值和事件多重集，运行内部断言原方案、报告、ReviewRequest、context 与返回值身份。
替换 selector 保留审查成员引用；构造错误发生在分析副作用之前。没有异步 selector 兼容、默认分支或 Loop。
NOOA 参考目录与既有快照比较，1,500 文件内容与文件集合完全一致；未新增依赖或修改锁文件。

### 10.6 Loop 判断与停止状态

建议保留后续 Loop：Router 只能选择一次分支，不能表达“执行一轮 → 检查结果 → 有界继续”的反馈协调。
该能力可以先用普通 Python 循环描述，再提取通用有界原语；不是 Router 的失败重试，也不预置 EvaluatorOptimizer。
M7 实现前仍须确认耗尽标记与“不自动注入任意 context”契约的扩展，以及终止 / 上限边界。

当前停在 M6：已完成实现与本地验证，并通过 reviewer 技术复审（见 §10.7）；用户随后指示提交推送，交付见 §10.8。
M7 Loop 尚未授权实现，等待用户确认后先澄清 §11 的契约边界。

### 10.7 Reviewer M6 技术复审结论

来源：用户提供的《M6 Review 报告》。结论为 **通过，无 M6 阻塞项**。
以下是 reviewer 的独立运行记录，与 §10.5 的实施结果分别保留；本次文档更新没有重跑测试或覆盖 M6_PYTEST.txt。

| 验证 | reviewer 报告的结果 |
| --- | --- |
| Windows M6 定向 | `38 passed in 0.15s` |
| Windows 全量 | `92 passed, 1 skipped in 0.28s`；仍为上游 fcntl 平台限制 |
| WSL 禁网完整回归 | `95 passed in 28.88s`，无跳过 |
| 示例与导入 | Windows / WSL 三风险评审对照通过；八个公共名称隔离导入成功 |

复审确认成员快照、声明式命名检查、单分支路由、引用、异常 / 取消、递归与案例均符合契约。
将 Members 快照直接传回 Team 不在当前 Sequence / Mapping 输入承诺内；若后续扩展，须明确名称保留语义。
直接 run 成功、单名称与异步 selector 拒绝等独立测试建议均为非阻塞项，不自动扩大本阶段范围。
本次复审本身不构成提交推送或 M7 实现授权；后续用户明确指示提交推送，见 §10.8。M7 仍未授权。

### 10.8 M6 分次提交与交付

用户于 2026-10-19 明确指示“提交并推送”。按职责分三组交付，未开始 M7：

| 分组 | 提交 | 内容 |
| --- | --- | --- |
| 成员接口与路由 | `626634d`：`feat: add named member snapshots and routing` | Members、Team / Pattern 声明检查、Router、公共导出和核心测试 |
| 完整评审案例与证据 | `383480f`：`test(examples): verify routed technical reviews` | router_review.py、7 项案例测试及 M6_PYTEST.txt |
| 契约、计划与交付文档 | `docs: record M6 acceptance and delivery` | README、AGENTS、唯一实施计划中的契约、实施结果与独立复审记录 |

提交前检查 Python 语法、文档链接、空白、变更范围及原始 95 项通过记录；依赖声明、锁文件、
适配器、既有示例及 M4 / M5 验证输出保持不变。复审后没有修改代码或测试，本次未重复运行 pytest；
实施与 reviewer 独立结果分别保留在 §10.5、§10.7。推送目标为 origin/main，推送后核对
本地 HEAD、远程跟踪分支与服务器端 main；最终提交号及推送结果以 Git 和本次交付回复为准。

## 11. M7：Loop 的计划与待澄清项（未实现）

用户草案为 Loop(members, until, max_iterations)：每轮按 Sequential 交接，
完成整轮后判断 until(result, context)；max_iterations 必须显式给出，
达到上限返回最后结果并记录 loop_exhausted，不抛耗尽异常，不自动累计每轮历史。
终止判断属于调用者，库不内置质量或评审语义。

M7 开始前需要澄清：

- 成员归属应与 M6 的 Members / Team 分工一致，Loop 的构造接口仍待 M7 确认；第 2 轮入口应明确为上一轮末结果。
- 自动写 loop_exhausted 是对 v0“库不向任意 context 注入字段”的明确扩展；
  任意对象未必能写字段，需明确 context 能力、标记清除/覆盖和嵌套 Loop 相互覆盖的语义。
- max_iterations 正整数与 bool 边界、最后一轮 until 为真时的耗尽判定、判断函数抛错/取消的行为。

这些是未来契约设计事项，不在 M5 实现，不预置 EvaluatorOptimizer。

## 12. Reviewer 如何判定问题

- 先确认待审阶段，再区分该阶段必交付、未来阶段交付和非阻塞建议。
- 按实际业务行为、契约与测试证据审查，不把统一签名误判为任意业务组合兼容。
- M1 的硬性文档缺口曾是缺少核心抽象章节，该项现已补齐。
- README/docstring 都保存完整契约是明确需求，不能自行缩为一处而称为去重修复。
- Git 初次提交、NOOA 依赖固定 tag/commit、`uv.lock` 是可追溯性与可复现性建议，
  当前未确认成为 M1 的硬性验收门槛；也不能在没有验证上游版本的情况下随意填写 commit。
- 轻量导入验证可以核对已安装包；不必为了文档修复添加只镜像实现的 `hasattr` 断言。
- 尚无 Git 提交时，明确说明审查基于工作树。不能虚构基线 commit 或 diff。

## 13. 已知环境限制与汇报规则

- Windows 沙箱内 `asyncio` 曾阻塞于 `_fallback_socketpair` / `accept`，
  即使关闭 pytest 缓存也可能发生。遵守平台机制申请沙箱外执行，不改写协程语义绕过验证。
- `.pytest_cache` 不可写时使用 `-p no:cacheprovider`；它只关闭缓存，不跳过测试。
- uv 缓存使用项目内 `.uv-cache`；遇到权限或网络限制先确认原因并按平台规则处理，
  不擅自扩大工作区 ACL，也不修改 NOOA 参考源码。
- 中文管道输出使用 `-X utf8`；乱码与业务断言失败须区分。
- 审批服务容量不足造成的检查失败不等于判定命令不安全，但命令未执行就不能报告为通过。
- 测试报告须区分本次实际运行、历史运行和未执行项。历史的 `3 passed` 不能代替新的运行证据。

## 14. 计划维护规则

每次阶段汇报至少记录：交付文件、实际测试命令和结果、遗留问题、当前停止阶段。
用户明确批准下一阶段后，更新 §3 状态，再按该阶段范围实施；不要只在聊天中修改计划。
计划调整须记录用户已经确认的变更，review 建议本身不自动更改阶段范围。

实施计划统一维护在本文件；必要的专题细节可独立成文，通过链接引用，不重复维护计划或阶段状态。
非必要不新增文档；是否新增由 agent 根据内容与维护需要自行判断，不以更新现有文件为优先规则。
需要写文档时明确文档层级和职责，合理拆分并通过链接组织，避免内容重复或单篇过于冗长。
