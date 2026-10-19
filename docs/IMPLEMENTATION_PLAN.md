# 实施计划与验收基线：M0–M4

本文件将已由用户确认的设计、M1–M4 实施任务和阶段确认规则落盘，供没有聊天上下文的
实现者与 reviewer 使用。它记录实施范围，不表示后续里程碑已经获准开始。

## 1. 阅读顺序与依据

1. 本文件：确认当前阶段、允许的范围和验收条件。
2. [README](../README.md)：阅读项目定位、核心抽象和完整执行契约 v0。
3. [protocols.py](../src/nooa_patterns/protocols.py)：核对真实接口与协议 docstring。
4. 对应阶段的实现和测试：以实际运行结果验证行为，不能只根据文档宣称通过。

里程碑范围来自用户“分四个里程碑实现”的任务书；执行语义来自此前已确认的契约修正。
原始实施任务正式划分的是 **M1–M4**。下文的 **M0 只是对已完成前置设计的回填编号**，
不新增开发任务、追溯性验收门槛或用户批准。

契约的完整内容保存在 README 和协议 docstring 中，两处都须维护完整内容，这是用户的明确要求。
本文件只索引关键决定，不另立一份不同的契约。后续用户变更设计或范围时，应同步更新相关文件。

## 2. 项目边界与已确认设计

项目根目录和 Git 仓库为 `E:\ComposeAgents\nooa-patterns`。
`E:\ComposeAgents\labs-OO-Agents-main` 为只读参考源码，禁止修改。

项目是 NOOA 生态里的模块化协作与可复用设计模式库，借鉴 `torch.nn` 的组合思想。
它是独立 Python 扩展包；不新增底层 Agent 执行框架，不重写模型调用、沙箱、
Agent 状态管理或事件历史，不以 LangGraph / CrewAI 为基础，也不用 TypeScript 重写核心。

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
| 其他边界 | `None` 为普通结果；空 Team 构造时报 `ValueError`；成员序列取 tuple 快照但成员保持引用；不内置超时、不重试整个流程、不回滚副作用、不承诺同一 Team 并发安全。 |
| 递归与资源 | 子 Team 保留自己的 Pattern；不支持无限自调用；不做完整图校验；资源生命周期归调用者。 |

README 将完整契约按 13 个主题组织，覆盖任务书中的 15 个要点。
验收以内容完整性为准，不要求机械改成 15 个编号。

## 3. 阶段确认规则与当前状态

**每完成一个里程碑，必须汇报并停止。只有用户确认后，才能进入下一个里程碑。**
测试通过不等于用户已批准进入下一阶段；收到 review 建议也不自动表示可以实现后续阶段。

| 阶段 | 内容 | 当前状态 |
| --- | --- | --- |
| M0 | 前置设计、契约、范围确认；本文件回填记录 | 设计已确认，见 §4 |
| M1 | 手写基线 + 协议 + 完整文档 | 已实现并通过 reviewer 复审；独立提权测试与 reviewer 报告的测试均通过，见 §5.4–5.5；等待用户确认进入 M2 |
| M2 | 适配器 + Sequential | 未开始，等待用户确认 |
| M3 | Team 容器 | 未开始 |
| M4 | 组合示例 + 等价测试 + NOOA 集成 | 未开始 |

M1 目前只导出 `TeamMember`、`Pattern`。README/docstring 对后续行为的说明是设计契约，
不是那些功能已经实现的证据。

完整 NOOA 运行时尚未安装验证：M1 使用 `--no-deps` 验证本地包构建与导入。
M2 的纯 Python 适配器和 Sequential 可以用 fake 验证；真实 NOOA Agent 集成属于 M4，
届时必须完成运行时安装、依赖一致性检查及 FakeLLMClient 测试。
可提前独立验证依赖环境，但不能把它误记为 M1 已完成事项或自动启动 M2。

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

复审报告建议进入 M2，但明确要求等待用户确认；本次只更新文档记录，不表示 M2 已获授权。

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

## 9. Reviewer 如何判定问题

- 先确认待审阶段，再区分该阶段必交付、未来阶段交付和非阻塞建议。
- 按实际业务行为、契约与测试证据审查，不把统一签名误判为任意业务组合兼容。
- M1 的硬性文档缺口曾是缺少核心抽象章节，该项现已补齐。
- README/docstring 都保存完整契约是明确需求，不能自行缩为一处而称为去重修复。
- Git 初次提交、NOOA 依赖固定 tag/commit、`uv.lock` 是可追溯性与可复现性建议，
  当前未确认成为 M1 的硬性验收门槛；也不能在没有验证上游版本的情况下随意填写 commit。
- 轻量导入验证可以核对已安装包；不必为了文档修复添加只镜像实现的 `hasattr` 断言。
- 尚无 Git 提交时，明确说明审查基于工作树。不能虚构基线 commit 或 diff。

## 10. 已知环境限制与汇报规则

- Windows 沙箱内 `asyncio` 曾阻塞于 `_fallback_socketpair` / `accept`，
  即使关闭 pytest 缓存也可能发生。遵守平台机制申请沙箱外执行，不改写协程语义绕过验证。
- `.pytest_cache` 不可写时使用 `-p no:cacheprovider`；它只关闭缓存，不跳过测试。
- uv 缓存使用项目内 `.uv-cache`；遇到权限或网络限制先确认原因并按平台规则处理，
  不擅自扩大工作区 ACL，也不修改 NOOA 参考源码。
- 中文管道输出使用 `-X utf8`；乱码与业务断言失败须区分。
- 审批服务容量不足造成的检查失败不等于判定命令不安全，但命令未执行就不能报告为通过。
- 测试报告须区分本次实际运行、历史运行和未执行项。历史的 `3 passed` 不能代替新的运行证据。

## 11. 计划维护规则

每次阶段汇报至少记录：交付文件、实际测试命令和结果、遗留问题、当前停止阶段。
用户明确批准下一阶段后，更新 §3 状态，再按该阶段范围实施；不要只在聊天中修改计划。
计划调整须记录用户已经确认的变更，review 建议本身不自动更改阶段范围。
