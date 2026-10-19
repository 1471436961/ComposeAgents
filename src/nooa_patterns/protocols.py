"""弱类型协作边界；仅定义协议，不实现编排或 NOOA 执行机制。"""

from typing import Any, ClassVar, Protocol

from .members import Members


class TeamMember(Protocol):
    """叶子成员与 Team 共同遵守的执行契约 v0。

    类型边界：这是弱类型协议，兼容性由调用者和测试保证，不继承 NOOA 的类型校验契约。
    通过适配器调用 NOOA 公开方法时，该方法原有校验仍生效。
    本协议不检查跨成员类型兼容性，不推导、转换类型，也不验证完整签名或业务语义。
    业务函数应继续使用具体类型；这里的 Any 只表示组合边界暂未强制类型兼容。

    task 是此次调用的业务输入。Sequential 中 r₀ = task，
    rᵢ = await memberᵢ.execute(rᵢ₋₁, context)，返回 rₙ。
    第一成员接收入口的原始 task，之后逐级接收前一结果。
    原始指入口收到的对象，不表示不可变快照。库不序列化、复制或转换输入。
    成员可以修改可变输入；返回值、输入与 context 内对象可以互为别名。
    后续成员需要原始任务时，由调用者显式提供；保存引用不会创建快照。
    Parallel 中所有成员并发接收入口的同一个 task 和 context，而非前一成员结果。
    按成员顺序返回新 list；元素是原业务结果，保留 None、嵌套列表和对象身份，不展开。
    该列表本身是此次 Team 调用的聚合业务结果，下游须能接收该形状。

    context 是调用者创建、持有和管理的任意应用级对象。
    所有成员收到同一个引用，修改彼此可见。库不复制、不持久化，
    不注入 last_result、history 或原始任务；成员和显式适配函数可以主动修改它。
    它与 NOOA agent.context（提示词上下文）无关，不自动同步。
    Parallel 不保护 task/context 的并发读写，调用者负责并发安全；同一成员的重入也由调用者负责。

    叶子与 Team 都返回自身此次调用的业务结果，处于同一成员调用边界，
    不要求相同 Python 类型、数据形状或任务粒度。Pattern 决定业务结果如何产生，
    Team 直接返回该结果，不额外包装统一执行状态对象。
    子 Team 的输出须匹配外层后续成员的输入；统一签名不保证业务兼容。
    None 是普通结果：Sequential 逐级原样传递，Parallel 保留结果列表中的对应元素。
    它不表示跳过、提前结束或保留上一结果。
    只修改 context 且希望继续传递输入的成员应显式 return task。

    异常与 CancelledError 直接传播，不吞掉或包装异常；Sequential 不启动后续成员。
    Parallel 在首个失败被观察到后取消未完成兄弟任务，等待全部直接子任务结束后传播原异常。
    同时失败不保证按成员顺序选择异常；取消清理异常被取走但不覆盖原业务异常。
    外层或单个成员取消会中止 Parallel 汇集，取消其他未完成任务并等待结束。
    外层取消保持 CancelledError，即使成员的取消清理抛错；成员吞掉取消也不把整次调用改成成功。
    已经完成的成员不会被追溯取消；只管理等待链，不接管成员自行创建的后台任务。
    快速失败指及时请求取消，不承诺立即返回；取消清理可能等待，额外的外层取消仍可传播。
    库不重试整个流程；成员或 NOOA 策略自身的重试仍按原机制执行。
    失败或取消不回滚 context、输入、Agent 状态及已经发生的外部副作用。
    库不能强制中断阻塞或屏蔽取消的成员，仅管理直接等待的调用链。
    首版不内置超时；调用者可在外层或显式适配函数中限制等待时间。
    底层自己的超时仍有效，超时也不保证立即停止或撤销副作用。

    Pattern 必须无执行状态并可跨 Team 复用；当前输入、进度、临时结果与异常
    只能属于此次调用，不能保存在 Pattern 字段或其他共享可变存储中。
    固定配置与可变执行状态应区分；Sequential、Parallel 不需要配置字段。
    本协议不能自动证明第三方 Pattern 遵守无状态约定。

    Team 接受成员序列或字符串名称映射，构造时取浅快照并统一保存为只读 Members。
    Members 迭代成员而不是名称，保留顺序、名称和成员引用，支持整数或名称访问及 has_name。
    原始 list/dict 的修改不改变 Team，不复制、不重置成员，没有动态增删接口。
    requires_named_members 是 Pattern 的固定类声明，默认 False；Router 为 True。
    Team 构造时拒绝把非 Mapping 交给要求命名的 Pattern，不靠运行时猜测业务语义。
    多个 Team 共享成员时仍是同一个有状态实例；重复执行不会自动创建干净会话。
    首版不承诺同一 Team 并发调用安全；Pattern 无状态不保证成员或 context 并发安全。
    空 Team 在构造时抛出 ValueError；Pattern 的成员序列前提为非空。
    单成员 Sequential 原样返回该成员的结果；单成员 Parallel 返回单元素列表。
    直接 Parallel.run 也对空成员抛 ValueError，不改变 Sequential 对直接空序列不作保证的边界。

    Router 的 selector 是 Callable[[Any, Any], str]，每次同步调用一次，选择一个名称。
    selector 应是纯函数式的同步决策，不应调用 LLM 或做 I/O；模型决策应由前置异步成员完成，
    selector 只读其产物。库不推断或兼容异步 selector；非字符串返回值抛 TypeError。
    未命中抛 LookupError，消息包含返回名称和有序可用名称列表；selector 异常原样传播。
    被选成员收到同一个 task/context，其结果原样返回，包括 None；其他成员不执行。
    Router 不注入 context、包装结果、重试或回滚，取消传到被选成员；选中子 Team 保留自身 Pattern。

    允许嵌套与成员复用；子 Team 保留自己的 Pattern，不扁平化。
    不支持直接或间接自调用造成无限递归，首版没有完整图校验器。
    调用者管理 Agent、模型客户端和连接等资源；Team 不关闭、重置或持久化它们。

    已满足本契约的 execute 可直接参与；其他 NOOA 异步方法通过显式函数桥接。
    适配器只转交调用，不根据名称或签名猜测业务映射，不自动复制底层文档与签名。
    普通 Python 对象不会自动获得 NOOA span 或完整组织树的 doc(self) 展开；
    NOOA 叶子公开方法仍经过原生调用链。
    """

    async def execute(self, task: Any, context: Any) -> Any:
        """完成当前业务输入，返回此次调用的业务结果，遵守上述引用与失败语义。"""
        ...


class Pattern(Protocol):
    """成员间的协作协议，复用 TeamMember 契约中的数据、引用与失败语义。

    本协议提供 run，不是 TeamMember 的子类型；仅实现 run 不满足成员的 execute 协议。
    Team 的 execute 委托 run 并直接返回业务结果，Pattern 自身不因此成为 Team 成员。

    Pattern 必须无执行状态并可复用。同一 Sequential、Parallel 或 Router 可被多个 Team 共享。
    当前输入、进度、临时结果、异常不得保存到实例字段或其他共享可变存储。
    固定配置应与执行状态区分；Router 保存 selector，不保存本次选择或结果。
    无状态是实现者的约定，Protocol 不会自动验证它。

    members 是非空 Members，保存构造时的浅快照，按原顺序迭代成员并保留成员引用。
    requires_named_members 是固定类声明，默认 False；Router 声明 True。
    Team 构造时对要求命名但输入非 Mapping 的配置抛 ValueError。
    Protocol 默认值不会自动赋给结构类型；Team 将未声明属性的旧自定义 Pattern 按 False 处理。
    task 与 context 按 TeamMember 的契约传递，不由库复制、转换或注入额外字段。
    返回此次协作的业务结果，Team 原样返回它；None 也是普通业务结果。
    异常和取消直接传播，不重试整个流程、不回滚副作用，不内置超时或管理资源。
    子 Team 保留自己的 Pattern；不支持无限递归，也不承诺同一 Team 并发安全。
    Parallel 共享入口 task/context，按成员顺序返回业务结果 list；失败或取消时取消并等待
    未完成兄弟任务，传播原失败或 CancelledError。并发修改与成员重入安全属于调用者。
    Router 用同步 selector 选一个名称，按 TeamMember 中的完整路由契约调用一个成员；
    直接 run 也要求非空命名 Members，不改变 Team 构造时提前检查的职责。

    Pattern 控制成员之间的协作，NOOA Strategy 控制单个生成方法的执行。
    """

    requires_named_members: ClassVar[bool] = False

    async def run(
        self,
        members: Members,
        task: Any,
        context: Any,
    ) -> Any:
        """在非空成员序列上执行协作，返回该调用的业务结果。"""
        ...
