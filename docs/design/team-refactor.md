# Team 重构设计方案

初稿日期：2026-10-20；最近修订：2026-10-21。

本文是 Team 重构的设计与实现依据。用户已于 2026-10-21 授权按本方案迁移代码并清理冗余文件；
源码已迁移，当前验证与复审状态统一在
[唯一实施计划](../IMPLEMENTATION_PLAN.md)维护；本文不另建里程碑。

方向决定来自设计讨论，具体落点由本次按方案实施授权采用。本文 Python 展示接口和执行结构，
完整行为以源码、README 和协议 docstring 为准；测试通过不代表用户已完成技术复审。

## 1. 目标与职责

Team 是可递归的多智能体协作单元，对外接受任务和上下文、返回业务结果；对内了解成员能力、
协作方式与交付要求，先通过 LLM 分配工作，再由普通 Python 执行确定的控制流。
目标同时包括构建便利性、行为规范性和成员上下文的相关性；是否改善质量与成本须由后续应用验证。

```text
Team.execute(task, context)
    → await allocate(task, context)
        收集成员、协作方式和执行契约描述 → 调用一次 NOOA 生成函数 → 校验分配结构
        返回 name → {task, context}；阶段内错误附原始原因包装为 AllocationError，取消原样传播
    → 根据固定 PatternKind 执行，交接运行中产生的结果
    → 返回本 Team 的业务结果
```

Team 负责成员组织、任务与材料分配、结果交接、递归调用和取消等待。
NOOA 负责生成方法、模型调用、CodeAct、原生类型校验、对象描述、提示词构造和叶子历史。
只使用 NOOA 公开 API；不修改参考源码，不复制其装饰器、元类或运行时。

## 2. 方向决定与实现选择

### 2.1 已收敛的方向

- **Team 是执行主体。** 以封闭的 `PatternKind` 枚举选择四个私有执行算法，删除 `Pattern` Protocol
  和四个 Pattern 类，不提供第三方 Pattern 扩展点。NOOA 的 `Strategy` 仍负责单个生成方法。
- **协作方式固定。** Team 构造后不能替换 pattern；需要另一种组织行为时构造新的 Team。
  “Pattern 可替换是核心价值”的旧表述撤回；跨 Team 复用业务能力仍可成立。
- **成员全部命名。** 构造入口使用 `dict[str, TeamMember]`，递归成员可以是叶子或子 Team。
- **允许单成员 Team。** 直接成员数量不等于底层 Agent 数量；单个子 Team 可以包含完整业务轮次。
  四种模式均只要求成员非空，单成员时仍执行正常分配与控制流，不增加跳过分配的特殊路径。
- **信息分配是 LLM 能力。** 每次 `execute` 先调用一次分配方法。首版不提供通用规则分配器、
  `use_llm` 开关、逐成员 planner 或分配失败后的隐式全量上下文回退。
- **分配采用两层封装。** 普通 `allocate(task, context)` 从 Team 自身收集生成所需的信息，
  再调用原生独立生成函数。调用者不手工传入成员描述，也不必在构造时提供职责或输出描述参数。
- **分配失败可分类。** 描述收集、生成和分配结构校验中的普通异常统一由 `AllocationError` 标识阶段，
  保留原始原因及所属 Team；业务执行异常和取消不作该包装。分配成功后才进入执行算法。
- **分配结果按成员名称索引。** 各成员可以获得不同的 task/context；Parallel 只规定并发关系，
  不再要求成员实际输入相同。其结果由列表变为名称到业务结果的字典。
- **控制流承担运行时交接。** Sequential 传递上游结果，Loop 传递反馈；这些动作不重新调用本 Team
  的分配方法。子 Team 每次被调用时执行自己的完整分配与执行流程。
- **允许破坏性接口迁移。** 可以修改方法签名、适配器、示例和测试，不以维持旧传参形式限制新设计。
- 不增加角色库、应用模板、复合 Pattern、图引擎或新的上下文管理框架；本轮不进入真实 LLM 应用阶段。

### 2.2 本次实现采用的具体选择

- **成员构造后只读。** 对字典取浅拷贝，公开只读映射；不提供 `add/remove/rename`、
  `from_sequence` 或运行中修改接口。早先“配置期可变”提案在本次实现中收缩为构造固定；
  成员对象本身仍然按引用保留、可以有状态。
- 分配结果使用一个字典，每项同时包含 `task` 和 `context`，避免两个字典的键发生错位。
- 成员调用的局部 context 使用普通字典，固定区分 `materials`、`upstream`、`feedback`，详见 §5。
  不新增上下文基类、依赖表达式语言或通用绑定器。
- 职责和交付要求从类/方法 docstring、执行方法的类型注解及本次 task/context 获取；
  不新增必填的 `description`、`output_description` 构造参数，不维护第二份角色说明表。
- 分配函数首版采用 NOOA `CodeActStrategy`，便于选择和组装活 Python 对象。
  原生生成、引用及返回行为已由 `FakeLLMClient` 集成测试验证，实际运行结果见实施计划。

## 3. 对外接口与结构

```python
class PatternKind(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ROUTER = "router"
    LOOP = "loop"

class AllocationError(Exception):
    def __init__(self, message: str, *, team: "Team") -> None: ...
    # Retain team; raise ... from exc preserves the original exception in __cause__.

class Team:
    def __init__(
        self,
        members: dict[str, TeamMember],
        pattern: PatternKind,
        *,
        llm: Any,
        selector: Callable[[Any, Any], str] | None = None,
        until: Callable[[Any, Any], bool] | None = None,
        max_iterations: int | None = None,
    ): ...

    async def allocate(
        self, task: Any, context: Any
    ) -> dict[str, dict[str, Any]]: ...

    async def execute(self, task: Any, context: Any) -> Any: ...
```

`TeamMember.execute(task, context)` 继续是弱类型结构协议，不强制继承。
裸 NOOA Agent 基类没有这个方法；具体 Agent 可自行实现，或由 `as_member` 显式桥接其业务方法。
统一签名不保证任意业务输入输出兼容，也不继承 NOOA 的运行时业务校验契约。
通过适配器正常调用的 NOOA 方法仍保留原生校验。

构造规则：

- `members` 必须是非空 dict，即 `len(members) >= 1`，不拒绝单成员；键必须为字符串，保留插入顺序及成员对象引用。
  dict 中的名称本身唯一；字典构造前已被覆盖的重复键无法事后恢复或检测。
- `pattern` 必须是 `PatternKind`；成员映射和 pattern 均不提供公开 setter。
- ROUTER 必须提供同步 `selector`；LOOP 必须提供同步 `until` 及正整数 `max_iterations`。
  其他模式收到不适用的非 `None` 配置时报错。
- 对 LOOP，未提供上限时报 `TypeError`；非整数或 bool 报 `TypeError`，零或负数报 `ValueError`。
  签名中的 `None` 仅用来表达非 LOOP 未配置上限，不是 LOOP 的默认执行轮数。
- 构造只验证配置和保存引用，不调用模型。模型配置交给 NOOA 解析，调用者负责客户端生命周期。

单成员 Team 可以承担独立分配边界，或以一个子 Team 为完整 Loop 轮次。
成员数少并不使递归组合失效；不额外限制 Sequential/Parallel 的分支数、Router 的候选数或 Loop 的轮内成员数。

沿用 NOOA 的信息归属：类 docstring 表达稳定职责，执行方法的 docstring 和类型注解表达方法契约，
本次 task/context 表达具体任务、交付要求及材料。职责和输出信息不必全部到执行时才出现，
也不需要以两个必填构造参数重复声明。通用 Team 没有专门业务方法时，按本次 task 的交付要求和
控制流的实际输出形状工作；自省不能从 `Any` 推导未声明的业务类型，也不自动提供输出验证。
Team 的实际返回形状必须与所选控制流一致：Sequential/Loop 返回末成员结果，
Router 返回选中结果，Parallel 返回结果字典。需要报告或汇总文本时，显式安排相应业务成员。
父 Team 的本次分工细化子 Team 的交付目标，不任意改写子 Team 已声明的输出能力。

## 4. NOOA 复用与分配方法

### 4.1 对象描述自动收集

直接复用 `nooa.agentdoc.doc()`，它支持普通 Python 类、实例和绑定方法。
Team 内部构建有名称的直接成员描述，并提供自己的职责、输出约定和四种协作方式的准确说明。
父 Team 通常只需要子 Team 的外部能力，不自动展开整棵组织树或所有成员历史。

适配器需保留原 callable 供描述使用；桥接函数保留实际业务注解和 docstring。
不能只把通用包装器的 `execute(Any, Any)` 描述交给模型，也不能根据成员名称猜测业务能力。
当前 Team 的执行契约也从已有类/执行方法文档和注解自动提取，具体交付要求随本次 task/context 提供。
通用 Team 不要求为了补充描述而派生业务子类；已有业务子类的专门契约可以照常被提取。
自省只提取已有信息，不创造缺失的职责定义。

`allocate` 的使用说明应明确：分配质量依赖成员的类/方法 docstring 与类型注解；
重要成员应清晰描述能力范围、输入要求和输出含义，否则模型可能分配不准确。
清晰描述有助于分配，但不保证语义正确；不通过 docstring 长度检查替代业务验证。

### 4.2 原生生成路径

分配分为两个清楚的步骤：普通方法负责信息收集和调用衔接，生成函数负责语义分工。
对外的 `Team.allocate` 只接受本次 task/context；它已能访问 members、pattern 及执行方法，无需调用者重复提供。

```python
# An ordinary Team method; helper names below illustrate the implementation.
async def allocate(self, task, context):
    try:
        member_descriptions = self._describe_members()
        pattern_description = self._describe_pattern()
        execution_contract = self._describe_execution()
        assignments = await self._generate_assignments(
            task=task,
            context=context,
            member_descriptions=member_descriptions,
            pattern_description=pattern_description,
            execution_contract=execution_contract,
        )
        self._validate_assignments(assignments)
    except Exception as exc:
        raise AllocationError("Team allocation failed", team=self) from exc
    return assignments
```

`_describe_members` 复用 NOOA `doc()` 获取实际业务能力；`_describe_pattern` 说明当前模式及有效配置；
`_describe_execution` 提取当前 Team 的类/执行方法契约。它们只做普通信息整理，不额外调用模型。
`execution_contract` 是自动收集的描述文本，不是要求调用者手写的新参数，也不是输出校验器。
`allocate` 收尾完成结构校验，成功返回可供执行算法使用的分配；`execute` 调用它后进入执行算法，
不另外重复生成或维护第二套校验路径。示意中的 Exception 捕获不包含 CancelledError 等 BaseException。
`_generate_assignments` 延迟调用内部工厂 `make_allocator(llm)`，执行其生成的独立函数；
客户端或模型别名交给 NOOA 解析，使用原生 `@strategy` 和 `...` 方法体：

```python
# Structural sketch: an internal factory binds the caller-supplied llm.
@strategy(CodeActStrategy(), llm=llm)
async def allocate_members(
    task: Any,
    context: Any,
    member_descriptions: dict[str, str],
    pattern_description: str,
    execution_contract: str,
) -> dict[str, dict[str, Any]]:
    """Assign work and relevant materials; return named task/context entries."""
    ...
```

生成函数不再设置独立的 `team_description`、`output_description` 参数。
本次任务和材料只通过 task/context 提供，不再完整重复进描述文本。
独立函数不是带 `self` 的普通实例方法；不假定在普通 Team 方法上加装饰器就会自动获得 Agent runtime。
使用 NOOA 原生 standalone 路径，不调用其私有 runtime 方法，不新增长期驻留的管理者 Agent。
每次分配使用原生的独立调用上下文；输入引用、客户端或外部资源仍可能共享。

生成函数获得成员描述，不获得用于调度的成员实例表。它负责选择、组织输入，
不负责调用成员、改变 pattern、增加成员或执行重试流程。
材料可通过 CodeAct 访问原 Python 对象并选择引用，不要求模型把全部对象重新写成 JSON。
任意输入不保证会完整进入提示词；参数呈现、按需访问及原生限制仍由 NOOA 控制。

### 4.3 分配结果契约

```python
{
    "analyst": {"task": "...", "context": selected_analysis_materials},
    "reporter": {"task": "...", "context": selected_report_materials},
}
```

- 顶层键与本 Team 的成员名称完全一致；每项恰有 `task`、`context` 两个字段。
  两个字段的业务值均可为 `None`，不能用真值判断其是否缺失。
- 所有模式均先分配整个 Team；Router 未选中的分配项不执行。此顺序保留“一次分配后执行”的统一入口。
- `allocate` 内部由 Python 校验顶层/条目结构及成员名称。校验器对结构类型错误抛 `TypeError`，
  对缺失/多余名称或字段抛 `ValueError`；这些异常随后作为 `AllocationError.__cause__` 保留，
  对外分配阶段按 §4.4 分类。不把名称拼错变成跳过成员，不自动补充分配。
- 成员启动前完成上述校验。LLM 原生生成失败、校验失败或取消时，执行器不启动成员。
  不自动重新分配，不自动回退为向所有成员发送全部上下文。
- 一次分配方法调用可能包含 NOOA 内部多次模型交互或验证重试，不等于一次供应商请求。
- 分配结果只保存在本次调用局部。分配方法应选择/构造材料，不有意改写调用者 context；
  不深拷贝所有材料，也不提供强制防写或事务回滚。

### 4.4 分配异常边界

`AllocationError` 仅包装当前 Team 在描述收集、NOOA 生成及分配结构校验期间抛出的 `Exception`。
它保存发生失败的 `team` 引用，并通过 `raise ... from exc` 保留原始异常及其原有 cause 链。
普通 `allocate` 对外报告此异常；`execute` 不在整个方法外围统一捕获并包装。

- 构造配置错误仍按构造契约报错；成员、selector、until 的业务异常仍原样传播。
- `CancelledError`、`KeyboardInterrupt`、`SystemExit` 不包装，原取消与终止语义继续有效。
- 分配内部模型客户端抛出的超时属于可包装的阶段错误；外层 `asyncio.timeout` 通常先发出取消、
  再在其作用域外生成 `TimeoutError`，不能保证后者表现为 AllocationError，也不能为分类吞掉取消。
- 子 Team 分配失败时，父 Team 正在执行成员；父层直接传播同一个 AllocationError，
  不把它改标为父层分配错误。调用者可通过 `error.team` 定位，不能仅凭异常类型认定外层尚未执行业务。
- 阶段分类不表示必定可重试；不增加自动重试、降级或回滚。原生 NOOA 校验仍发生，原始错误经 cause 可检查。

### 4.5 分配预览与实际执行的观察

`allocate` 本身是公开的分配入口，单独调用即可获得经过结构校验的分配，不执行成员：

```python
assignments = await team.allocate(task, context)
```

不新增同义的 `preview_allocation`。预览是一轮真实分配调用，会产生相应模型成本；
随后再调用 `execute` 会重新分配，可能得到不同结果，预览不保证下一次执行采用相同分配。
要观察某次 `execute` 真正使用的分配，应在该次 `allocate` 返回点设置断点或记录结果，
需要时结合 NOOA 现有追踪；不把观察记录自动注入成员 context，不新增通用回放或分配注入 API。

## 5. 本次调用的局部上下文

分配条目的 `context` 表示所选材料；执行器为每次实际成员调用新建以下普通字典：

```python
local_context = {
    "materials": assignment["context"],
    "upstream": {},  # {direct_predecessor_name: actual_result} in the current chain.
    "feedback": {},  # {"result": previous_round_final_result} after the first Loop round.
}
await member.execute(assignment["task"], local_context)
```

- `task` 是该成员被分配的工作要求，执行器不自动用上游结果覆盖它。
- `materials` 保留分配得到的对象引用。`upstream` 只放直接前驱，不默认累积所有已执行成员或完整历史。
- 需要非直接前驱信息时，分配阶段只能从当时已有的材料中选择；不能把尚未生成的动态结果提前作为已有产物放入 materials。
  例如 A 生成方案、B 生成修改说明、C 同时审查两者，应让 B 显式返回包含方案和修改说明的业务对象，
  C 从直接前驱 B 获得该对象；也可由子 Team 汇总返回。分配已有材料、携带动态产物是两种明确的数据交接，
  不为此自动累计全部上游结果。
- 空 `upstream` 表示没有前驱；`{"name": None}` 表示前驱确实返回了 None。`feedback` 同样以键是否存在区分。
- 外层字典及两个运行时字典属于本次成员调用；其中材料、结果仍是活引用，不保证深层对象隔离。
  更改局部字典不会自动回写其他成员；修改共享材料对象的副作用仍可能可见。
- 不往调用者的原 context 注入这三个字段，不自动累积 history，不写 `loop_exhausted`。
  分配材料被放在独立 `materials` 字段下，不会因包含同名字段而覆盖运行数据。
- NOOA 叶子必须通过其生成方法参数实际接收这些数据。旧适配器若忽略 context，必须迁移；
  Python 层有局部字典，不代表模型已经看到它。

这三个字段是本次实现的最小布局，不新增通用 Context 类或材料存储系统。
NOOA 官方将“当前调用的数据”放在方法参数中；必要的跨调用提示内容才使用 `Context`/`agent.context`。
可复用 `ScopedContext` 和 `EventQuery` 做叶子自身的提示词/历史控制，但它们不替代结果路由。
跨 Agent 嵌套调用会清除继承的 scoped 覆盖，不能在 Team 外包一个作用域便宣称控制了整棵树。

## 6. 四种执行算法

`execute` 每次先调用一次完成结构校验的 `allocate`，再按固定枚举分支到以下私有方法。
四种算法均不调用本 Team 的 `allocate`。
成员字典的顺序仍用于 Sequential、Loop 及稳定结果呈现；名称用于身份和查找。

| 模式 | 成员 task | `upstream` | `feedback` | 返回值 |
| --- | --- | --- | --- | --- |
| SEQUENTIAL | 各自的分配 task | 首成员空；之后仅含直接前驱结果 | 空 | 最后成员的原结果 |
| PARALLEL | 各自的分配 task | 全部为空 | 空 | 按构造成员顺序插入的 `dict[name, result]` |
| ROUTER | 选中成员的分配 task | 空 | 空 | 选中成员的原结果 |
| LOOP | 每轮沿用各自的分配 task | 每轮首成员空，之后按轮内顺序交接 | 首轮空；后续轮所有成员获得上一轮末结果 | 最后一轮末成员的原结果 |

### 6.1 Sequential 与 Parallel

Sequential 每次等待前驱结束，再创建下一成员的局部 context；返回值不包装。
Parallel 在分配与校验全部完成后，为各成员创建本次运行专属任务，不在各分支中再次分配。
单成员 Parallel 返回单项字典，None 和嵌套结果字典均原样保留，不展开或按完成顺序重排。

Parallel 延续已有快速失败契约：观察到失败或成员取消后，取消未完成兄弟任务，等待清理后传播原异常。
外层取消同样取消并等待成员；清理异常不覆盖原触发异常；不返回部分结果、不包装异常组、不回滚。
取消为协作式；快速失败不保证立即退出，二次外层取消仍可中断清理。

### 6.2 Router

分配、校验后，调用一次 `selector(task, context)`，参数是本 Team 的入口 task/context；
随后仅执行选中成员自己的分配输入。selector 不根据分配字典再调用模型。
模型选路可由前置异步成员完成，selector 从本 Team 入口中读取该产物。

selector 是同步判断，返回非 str 抛 `TypeError`；未知名称抛 `LookupError`，消息包含所选名称和可用名称列表。
无默认分支，不启动其他成员；未知路由可能已经产生分配成本，但不会执行业务分支。

### 6.3 Loop

至少执行一轮；每轮按成员顺序完整执行后，只调用一次 `until(last_result, context)`，
其中 context 为本 Team 的入口 context。成员或 until 失败/取消直接传播，不继续下一轮。
until 必须同步返回 bool，非 bool 抛 `TypeError`；末轮 True 算正常终止，满上限仍 False 返回末结果。

每轮重新建立局部 context；轮内 `upstream` 重置，上一轮末结果进入本轮 `feedback`。
首轮与后续轮使用同一份分配结果，不重复规划；材料引用可能被业务成员修改，库不提供不可变快照。
Loop 不自动把反馈转换成新的 task，也不自动累计所有轮次；成员负责理解收到的反馈。
需要业务转换时仍可显式安排转换成员。

应用可每次新建 until 观察闭包记录 rounds/last_ok，在正常返回后计算耗尽；
异常与取消不记作耗尽。闭包状态由应用管理，不在 Team 内共享轮次。

## 7. 递归、输出与保留的边界

父 Team 将分配 task 和按控制流组装的局部 context 交给子 Team 的 `execute`。
子 Team 以这两个参数为自己的入口，描述自己的直接成员、分配一次、执行并返回结果。
它不自动获取根 Team 的全部材料或其他成员历史；本层 `materials/upstream/feedback` 不自动与父层同名字段合并。
父层提供的材料或结果经子 Team 的分配方法选择后，成为子成员的材料。

同一子 Team 若在 Loop 中被调用多次，每次子调用都会分配一次；
父 Loop 仍只有一次自身分配。这是递归调用语义，不是父算法的隐藏重规划。
子 Team 失败和取消按普通成员传播；AllocationError 保留最初失败的 Team 与原始原因，父层不重复包装。
Parallel 等待链须覆盖子 Team 的分配与执行阶段；子 Team 的结果字典整体保留，不自动摊平。

继续保留：

- 成员与 Team 返回同一调用边界上的业务结果，不要求相同 Python 类型；None 是普通结果。
- 成员引用、材料引用和结果引用不自动复制或重置；共享 Agent 实例是显式选择，不是复用业务能力的前提。
- 首版不承诺同一 Team/成员并发安全；局部状态不串扰不等于共享 Agent 历史或材料可安全并发。
- 分配阶段以 AllocationError 包装普通异常并保留 cause；成员、selector、until 的异常原样传播，
  取消不包装。不重试整个流程；NOOA 生成方法自身的重试仍按其策略发生。
- 不回滚模型调用、context、Agent 状态或外部副作用；不内置超时、持久化或资源关闭。
- 支持递归，不支持直接/间接无限自调用，不提供完整图校验器。
- 调用者管理客户端、Agent 和资源生命周期。配置保存在实例；分配、结果、轮次和并发任务保存在调用局部。
- 不宣传自动获得最优上下文或质量提升。局部输入筛选、叶子历史控制及最终模型请求需分别验证。

## 8. 新旧契约与文件迁移

| 重构前 | 本次实现 |
| --- | --- |
| Pattern Protocol、四个类、第三方结构扩展 | 封闭 PatternKind；四算法归 Team |
| Team.pattern 是公开可写属性 | 构造固定、只读 |
| Sequence/Mapping → Members 快照 | 非空命名 dict → 构造后只读映射 |
| 不自动进行 LLM 分配 | 每次 Team.execute 一次原生 LLM 分配方法调用 |
| Sequential 的上游结果成为下一 task | 成员自己的 task 保留，上游结果进入局部 context |
| Parallel 同 task/context，返回 list | 分配输入可不同，返回命名结果 dict |
| Loop 末结果成为下一轮入口 task | 分配 task 保留，末结果进入下一轮 feedback |
| 成员共享同一 context 引用 | 每次调用新建局部容器，材料/结果仍可共享引用 |
| 错误直接传播 | 仅分配阶段普通异常包装为 AllocationError 并保留 cause/team；业务错误和取消仍原样传播 |
| 自定义 Pattern / 共享 Pattern 测试 | 固定模式、配置检查、独立 Team 执行及业务成员复用测试 |

当前源码组织：

```text
src/nooa_patterns/
├── __init__.py
├── protocols.py       # TeamMember；更新完整契约
├── adapters.py        # 显式业务桥接与原 callable 描述
├── pattern_kind.py    # 四值枚举
├── team.py            # Team、AllocationError、四种私有算法及局部 context 组装
└── _allocation.py     # NOOA 公开 API 的内部薄桥接，延迟加载生成能力
```

旧 `patterns/`、`members.py` 和相应导出已删除；公开接口收敛为
`Team`、`TeamMember`、`PatternKind`、`as_member`、`AllocationError`，不公开通用规划器或上下文引擎。
Team 使用清晰私有方法组织，无需先按行数增加 mixin 或继承层；NOOA 桥接单独放置。
不在包导入时创建客户端或发起模型调用；纯 Python 控制测试可替换分配方法，不需要真实模型。

当前维护边界：

- 原有示例及其专属测试已删除，examples 保持为空；新应用场景确认后另行设计，不继承旧场景或实施顺序。
- 算法测试通过 `Team.execute` 验证；局部上下文、反馈与取消等核心断言继续保留在 tests 中。
- 业务能力可由新 Team 复用；不测试运行时替换 pattern，也不把共享有状态实例宣传为必要条件。
- README 与 TeamMember docstring 同时维护完整契约。旧交付可从 Git 恢复，历史验证不作为当前结果。

## 9. 验证要求

以下是本次实现的验收要求；实际命令和结果统一记录在实施计划，避免重复维护验证状态。

| 范围 | 必须证明 |
| --- | --- |
| 配置 | 仅接收命名非空 dict；四模式均接受单成员；一个顺序子 Team 可作为完整 Loop 轮次；浅快照和原成员引用；只读成员/枚举；模式参数匹配；Loop 参数边界 |
| 分配 | 每次执行只分配一次；键和字段严格对应；None 不等于缺失；错误/取消不启动成员；无隐式回退 |
| 分配异常 | 描述、生成及结构校验失败均携带原始 cause 和所属 Team；业务异常保持身份；子 Team 失败不重复包装；取消及外层超时保持原协议 |
| 预览 | 单独 allocate 不执行成员且完成结构校验；execute 发起独立分配；观察实际分配不依赖两次生成结果相同 |
| NOOA 描述 | 普通分配方法自动采集普通 Team、NOOA Agent、适配原方法的能力及执行契约，进入生成输入；调用者无需构造描述参数，不只描述泛型包装器 |
| NOOA 生成 | 公开 FakeLLMClient 驱动真实 standalone 调用；验证描述、输入、返回结构、材料引用及原生校验路径 |
| 局部 context | 当前成员 task 保持；材料/结果引用保持；空与 None 区分；局部字典独立；根 context 不被执行器注入字段 |
| Sequential | 顺序等待和直接前驱交接；无完整历史累积；动态跨步产物经前驱业务对象显式携带；失败阻止后续成员 |
| Parallel | 不同分配输入、并发重叠、命名字典结果；异常身份、取消、清理等待、嵌套取消及清理异常优先级 |
| Router | selector 一次、一个成员执行；入口参数保持；未命中含可用名称；子 Team 保留自己的模式 |
| Loop | 整轮执行后判断；严格 bool；末轮 True/耗尽；轮内状态重置；上一轮反馈身份；不重复本 Team 分配 |
| 递归与复用 | 子 Team 获得父分配及实际上游结果；子调用各自分配；无自动根材料继承；跨执行状态不串扰 |
| 模型输入 | 观察叶子真实 FakeLLMClient 请求中的相关材料，并确认未选择的根材料没有意外进入子层和叶子 |

纯控制流测试使用确定性 fake 分配，可用测试子类覆盖 `allocate` 或使用 pytest 替换机制；
两者均属于测试基础设施，不增加 allocator 构造参数、策略注册器或第二个 planner 钩子。
`allocate` 本身仍是公开方法；这不意味着承诺一套可注入的分配策略 API。
fake 覆盖用于控制流测试，分配校验与异常测试仍覆盖真实普通 `allocate` 的收集/生成/校验边界；
NOOA 集成测试使用 FakeLLMClient，并拒绝真实模型/网络调用，不能只替换整个方法来声称原生生成路径已通过。
原生 Windows 的 NOOA `fcntl` 限制沿用已记录的平台事实；完整原生集成验收在 Linux/WSL 无跳过运行。
测试集合变化后重新报告实际数量与结果，不沿用历史计数。

## 10. NOOA 源码依据

以下链接指向本工作区只读参考源码；不要求把 NOOA 源码复制到本项目。

| 能力 | 参考 |
| --- | --- |
| 普通对象、类和方法描述 | [agentdoc/core.py](../../../labs-OO-Agents-main/src/nooa/agentdoc/core.py)、[agentdoc 导出](../../../labs-OO-Agents-main/src/nooa/agentdoc/__init__.py) |
| Agent 的类接口与实例状态描述块 | [agent.py](../../../labs-OO-Agents-main/src/nooa/agent.py) |
| 独立生成函数及装饰器分派 | [standalone.py](../../../labs-OO-Agents-main/src/nooa/standalone.py)、[decorators.py](../../../labs-OO-Agents-main/src/nooa/decorators.py) |
| 本次数据、提示词块与历史的区别 | [prompts-and-context.md](../../../labs-OO-Agents-main/docs/concepts/prompts-and-context.md) |
| 子 Agent 参数交接及上下文隔离 | [multi-agent-systems.md](../../../labs-OO-Agents-main/docs/concepts/multi-agent-systems.md) |
| Context / ScopedContext 与跨 Agent 边界 | [models.py](../../../labs-OO-Agents-main/src/nooa/context_blocks/models.py)、[scoped.py](../../../labs-OO-Agents-main/src/nooa/context_blocks/scoped.py)、[method_wrapper.py](../../../labs-OO-Agents-main/src/nooa/runtime/method_wrapper.py) |
| CodeAct 参数访问与 Predict 返回要求 | [codeact.py](../../../labs-OO-Agents-main/src/nooa/strategies/codeact.py)、[predict.py](../../../labs-OO-Agents-main/src/nooa/strategies/predict.py) |

这些来源支持复用机制的判断，不替代对锁定依赖版本的集成验证。当前工作与授权见[唯一实施计划](../IMPLEMENTATION_PLAN.md)。
