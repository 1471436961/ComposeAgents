# nooa-patterns

NOOA 之上的递归多智能体组合库。Team 对外接受任务与上下文、交付业务结果；对内用 LLM 分配局部工作与材料，
再由确定的 Python 算法协作。NOOA 提供对象描述、生成方法、模型调用、CodeAct、叶子类型校验及历史。

当前已按 [Team 重构设计](docs/design/team-refactor.md)完成迁移，主体重构已通过技术复审；
其后确认的测试补充已完成本地验证，代码与测试已按用户要求分次提交并推送。
[唯一实施计划](docs/IMPLEMENTATION_PLAN.md#16-team-重构设计与迁移准备)记录授权、实际验证及历史交付。
旧 Pattern Protocol、四个 Pattern 类和 Members 已删除。本库不提供新的 Agent 执行引擎或第三方 Pattern 接口。

## 使用

公开接口为 `Team`、`TeamMember`、`PatternKind`、`as_member`、`AllocationError`。
成员已实现 `async execute(task, context)` 时直接参与；其他 NOOA 业务方法通过显式异步桥接与 `as_member` 适配。

```python
from nooa_patterns import PatternKind, Team, as_member

async def report_bridge(task, context):
    """根据实际分析结果和分配的材料生成报告。"""
    return await reporter.write(task, context)

team = Team(
    {"analysis": analyst, "report": as_member(report_bridge)},
    PatternKind.SEQUENTIAL,
    llm=client,  # NOOA UnifiedLLM 客户端或其支持的模型别名
)
result = await team.execute("分析方案并生成报告", {"documents": documents})
```

`analyst`、`reporter` 和 `client` 由应用创建。稳定职责来自类 docstring；方法契约来自方法文档及注解；
本次交付要求来自 task/context，不需要 description/output_description 构造参数。
`allocate` 自动描述直接成员，调用原生 standalone `@strategy(CodeActStrategy(), llm=...)` 函数并校验返回值。
Team 普通方法本身不依赖 Agent 继承或私有 NOOA runtime。

## 完整执行契约

同一契约亦保留在 [TeamMember docstring](src/nooa_patterns/protocols.py)，两处必须同步维护。

### 1. 调用、类型与成员配置

成员接口为 `async execute(task, context) -> result`。**这是弱类型协议，兼容性由调用者和测试保证，
不继承 NOOA 的类型校验契约。通过适配器调用 NOOA 公开方法时，该方法原有校验仍生效。**
业务代码保留具体类型；相同签名不保证业务输入输出兼容。本库不做跨成员类型推导或自动转换。

Team 构造只接受非空命名 dict，单成员合法。构造时浅拷贝，保留顺序和成员引用；成员映射、pattern 只读，
不支持增删或运行时替换。字典构造前被覆盖的重复名称无法事后检测。四值枚举封闭，不接受自定义 Pattern 对象。
成员对象仍有状态，不自动复制、重置或开启干净会话；跨 Team 共享实例由应用明确选择。
复用现有成员映射时显式传入 `dict(team.members)`；它只复制映射，仍保留同一批成员实例。

### 2. 分配与预览

每次 execute 先调用一次 `allocate(task, context)`，得到名称到 `{"task": ..., "context": ...}` 的字典。
名称必须完整且恰好覆盖成员，每项恰有两个字段；None 是合法值，不等于字段缺失。
先分配并校验全队，再开始执行；Router 也不例外。结构错误不会导致部分成员先运行。
不自动重新分配，不在失败时回退为把全部上下文给成员，不添加可注入的 allocator 构造参数。

分配依赖清晰的能力范围、输入输出说明和注解；自省不创造缺失职责，结构合法不保证分工正确。
生成函数得到成员描述而非调度对象表，负责选取/组织输入，不负责执行成员或改变成员集合及控制流。
生成方法一次调用可能包含原生多轮模型交互或重试，不等于一次供应商请求。

```python
assignments = await team.allocate(task, context)  # 校验后返回，不执行成员
```

单独预览也消耗一次生成；后续 execute 会再次分配，两次可能不同。观察本次实际分配应在该次 allocate 返回点记录或调试。
不另设 preview_allocation、通用回放或执行前注入分配的 API。构造和包导入不发起模型调用。

### 3. 局部任务、材料与运行结果

每个成员始终接收自己的分配 task；执行器不把前一结果覆盖到 task 上。每次实际调用新建普通 context 字典：

```python
{
    "materials": assignment["context"],
    "upstream": {},  # 有前驱时为 {直接前驱名称: 实际结果}
    "feedback": {},  # Loop 后续轮为 {"result": 上轮末结果}
}
```

外层和两个运行时字典每次独立创建，材料和结果保留活引用，不保证深层隔离或共享对象的并发安全。
局部字典的修改不自动回写其他成员；修改共享材料的副作用仍可能可见。没有前驱与前驱返回 None 通过键是否存在区分。
upstream 只包含直接前驱，不自动累计所有上游或完整历史。分配只能选取当时已有材料；需要跨多步使用的动态产物，
由前驱显式携带在业务返回值中，或由子 Team 汇总返回，不凭空提前生成。

入口 context 由调用者创建持有，可以是任意对象；执行器不往其中注入原任务、last_result、history 或 loop_exhausted，
不复制全部材料或自动持久化。它与 NOOA `agent.context`（提示词块 API）不同，不自动同步。
分配应选择/构造材料、不有意修改入口，但库不强制防写或提供事务隔离。
叶子须通过其实际生成方法参数使用局部输入；Python 中存在字典不代表模型已经看到它。
NOOA 提示块和历史筛选可在叶子配置，不自动继承根材料；ScopedContext 不提供整棵组织树的隔离保证。

### 4. 四种固定算法

| PatternKind | 执行与交接 | 返回值 |
| --- | --- | --- |
| SEQUENTIAL | 按成员字典顺序逐个等待；首成员 upstream 空，之后仅含直接前驱结果；feedback 空 | 末成员原结果 |
| PARALLEL | 独立分配输入并发执行；upstream/feedback 均空 | 按成员顺序插入的命名结果 dict |
| ROUTER | 分配后调用一次 selector，执行一个选中成员 | 选中成员原结果 |
| LOOP | 至少完成一轮顺序执行；每轮重置 upstream，后轮所有成员获得上轮末结果作为 feedback | 最后一轮末结果 |

Parallel 单成员返回单项 dict；元素保留原对象身份，不过滤 None、不摊平嵌套 dict、不按完成顺序排序。
叶子与 Team 返回同一调用边界的业务结果，不要求相同类型/粒度。下游须接受实际结果形状。
None 是普通业务结果，不表示跳过、提前结束或保留前值。

### 5. Router 与 Loop 的参数

ROUTER 必须配置同步 `selector(task, context) -> str`；参数是 Team 的入口对象，随后选中成员获得自己的分配输入。
非 str 返回值抛 TypeError，未知名称抛 LookupError 并包含可用名称列表，不设默认分支。
LOOP 必须配置同步 `until(result, entry_context) -> bool` 和显式正整数 max_iterations。
bool、非整数和缺少上限抛 TypeError；零负数抛 ValueError。其他模式收到不适用的非 None 参数时报错。
已知异步 selector/until 在构造时拒绝；同步判断应是纯业务判断，不调用模型或 I/O，模型决策放在异步成员内。

until 只在完整轮后调用一次，必须返回 bool，不依赖隐式真值；末轮 True 是正常终止，满上限仍 False 返回末结果。
分配 task 跨轮不变，本 Team 不重新规划；反馈不自动转换或累计。需要转换时安排显式业务成员。
应用可每次新建 until 闭包记录 rounds/last_ok，正常返回后计算耗尽；错误与取消不记录为耗尽。
不提供 on_exhausted；闭包属于应用，不共享给独立并发运行。

### 6. 异常、取消与副作用

描述收集、生成、结构校验的普通异常包装为 AllocationError，保存 `team` 与原始 `__cause__`；它只标识阶段，不保证可重试。
校验器的 TypeError/ValueError 和 NOOA 原生错误可从 cause 检查。构造、成员、selector、until 错误不作该包装。
子 Team 的 AllocationError 保留原对象及最初归属，父层不重复包装。
CancelledError、KeyboardInterrupt、SystemExit 不包装；外层 asyncio.timeout 仍按原取消协议产生 TimeoutError。

顺序/循环失败或取消后不执行后续步骤。Parallel 首个被观察到的失败或成员取消会取消未完成兄弟任务，
等待清理后传播原触发异常，不分组、不返回部分结果。外层取消保持 CancelledError，即使成员清理抛错；
清理错误不覆盖原异常。二次外层取消仍可中断清理。嵌套子 Team 清理完成后，父层才观察到其失败。
已完成的成员不被追溯取消，成员吞取消后返回也不能把被取消的整体调用改成成功。
取消为协作式，快速失败不保证立即退出；只管理直接等待链，不接管成员自行创建的后台任务。

不重试整个流程；NOOA 策略自身仍可重试。不回滚输入、材料、Agent 状态或外部副作用。
不内置超时；max_iterations 只限制轮数，不保证总耗时。调用者可用外部超时或显式成员包装限制等待。

### 7. 递归、状态与资源

父 Team 将成员级分配 task 和局部 context 交给子 Team；子 Team 每次独立分配，只描述自己的直接成员。
父层和子层同名 context 字段不自动合并，不自动获得根上下文或兄弟历史。外层 Loop 每轮调用子 Team，
子 Team 每轮各分配一次，外层自身仍只分配一次。子 Team 的结果整体交接，不自动展开。
允许共享叶子/子 Team 引用，不支持直接或间接无限自调用，不实现完整图校验器。

分配、临时结果、轮次和异步任务都属于调用局部；固定配置留在实例。
不承诺同一 Team/成员并发安全，独立 Agent 实例更易隔离历史。普通 Team 不自动拥有完整组织树 span。
调用者管理 Agent、客户端和连接生命周期；Team 不自动关闭、重置或持久化它们。

## 示例与测试

示例均为确定性 fake，Team 子类覆盖 allocate 只用于演示，不代表生产存在第二个 planner 钩子。
真实 standalone 分配与真实 Agent 调用由 FakeLLMClient 集成测试验证，不访问真实模型。
复合模式仅在 examples/composites 提供，需要时复制修改，不进入公开 API；至少三个真实场景的稳定重复才可提议提升。

```powershell
.venv/Scripts/python.exe -X utf8 examples/manual_flows.py
.venv/Scripts/python.exe -X utf8 examples/composed_flows.py
.venv/Scripts/python.exe -X utf8 examples/technical_review.py
.venv/Scripts/python.exe -X utf8 -m examples.composites.evaluator_optimizer
.venv/Scripts/python.exe -X utf8 -m examples.composites.debate
.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider -q
```

- [技术方案评审](examples/technical_review.py)：并发分析、按名聚合、路由审查、有界反馈，附手写对照。
- [EvaluatorOptimizer](examples/composites/evaluator_optimizer.py)：Loop 包含一个 Sequential 轮次子 Team。
- [Debate](examples/composites/debate.py)：Loop 包含 Parallel 提案子 Team 和普通裁决成员。
- [原生分配测试](tests/test_nooa_allocation.py)：活对象引用、原方法描述、叶子模型输入筛选及生成取消。

安装依赖使用 `uv sync --locked`。uv.lock 锁定 NOOA 0.0.11.dev433 / 1454b78c8f0a85c97eab1c6a91cc8cfc95b34de5。
该版本在原生 Windows 因上游 fcntl 导入限制不能运行 NOOA；包导入与纯 Python 测试仍可运行。
完整原生集成验收使用 Linux/WSL，无 skip。沙箱内 asyncio 阻塞时按平台机制提权，不修改测试来伪造通过。
本次实际结果和命令只在[实施计划](docs/IMPLEMENTATION_PLAN.md#16-team-重构设计与迁移准备)维护。
