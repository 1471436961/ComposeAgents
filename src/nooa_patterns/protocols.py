"""The weak structural boundary shared by leaves and recursive Teams."""

from typing import Any, Protocol


class TeamMember(Protocol):
    """完整执行契约：叶子成员及 Team 提供 async execute(task, context)。

    这是弱类型协议，兼容性由调用者和测试保证，不继承 NOOA 的类型校验契约。
    通过适配器调用 NOOA 公开方法时，该方法原有校验仍生效。Any 仅限组合边界；
    业务方法保留具体类型、能力说明和返回注解，签名统一不代表业务兼容。

    Team 只接受非空命名 dict，单成员合法。构造浅拷贝字典并保留成员引用；
    members/pattern 只读，不支持增删或运行时替换。封闭 PatternKind 包含
    SEQUENTIAL、PARALLEL、ROUTER、LOOP，不提供第三方 Pattern 协议。

    每次 Team.execute 先调用一次 allocate。普通方法复用 NOOA doc 收集能力，
    再调用独立 @strategy 生成函数，返回每个名称的 {task, context} 并校验结构。
    不做隐式重分配或失败后全量材料回退。单独 allocate 是公开预览，不执行成员；
    后续 execute 仍独立分配。原生生成可有多轮/重试。清晰文档影响质量但不保证正确。

    成员收到自己的分配 task，不被前一结果覆盖。实际 context 是本次调用新字典：
    materials 为分配所得 context，upstream 为直接前驱名称到结果的字典，feedback
    为 Loop 上轮末结果的 {result: value} 或空字典。外层及运行时字典每次新建，
    材料和结果保留活引用；不保证深层对象隔离，不复制/重置成员或业务对象。
    无前驱与返回 None 通过键是否存在区分；库不累积全部上游历史。静态材料可
    预先分配，尚未生成的动态产物由前驱业务结果显式携带给后继。

    SEQUENTIAL 按成员字典顺序等待并交接直接前驱，返回末结果。
    PARALLEL 并发执行独立输入，upstream/feedback 为空；返回按成员顺序插入的
    结果 dict，保留对象身份及 None，不摊平嵌套字典；单成员返回单项字典。
    ROUTER 分配后调用一次同步 selector(task, context)，参数为 Team 入口对象。
    非 str 抛 TypeError，未知名称抛 LookupError 并列出可用名称，无默认分支；
    只执行选中成员的分配输入，原样返回其结果，未选成员不执行。

    LOOP 必须配置 until/max_iterations；上限只接受正整数，bool/非整数/未配置
    抛 TypeError，零负数抛 ValueError。至少完整执行一轮，轮内同顺序算法；每轮
    重置 upstream，后轮所有成员 feedback 只含上一轮末结果。分配 task 跨轮不变，
    本 Team 不重新规划。轮末调用 until(last_result, entry_context)，严格返回 bool，
    否则 TypeError。末轮 True 为成功，满上限仍 False 返回末结果。不自动转换反馈，
    不写 loop_exhausted、不累积轮史、不提供 on_exhausted。应用每次新建 until 闭包
    记录 rounds/last_ok，在正常返回后计算耗尽。selector/until 是同步纯业务判断，
    不调用 LLM/I/O；异步判断放在业务成员内。

    入口 context 由调用者管理，可为任意对象。执行器不注入字段，不自动同步 NOOA
    agent.context（提示词块 API）。局部字典修改不自动回写其他成员；共享材料的修改
    可能可见，Parallel 并发安全归调用者。叶子须通过真实生成方法参数接收局部输入；
    Python 有字典不保证模型已使用它。NOOA 块、历史及筛选可在叶子公开 API 配置，
    不自动继承根材料，不把 scoped context 当树级隔离。

    分配描述、生成、结构校验的普通异常包装为 AllocationError，保存 team 和原始
    __cause__；构造、成员、selector、until 错误不包装。子 Team 分配错误原样传播，
    不误标父层。CancelledError/其他 BaseException 不包装；外层 asyncio.timeout
    按原取消协议产生 TimeoutError，阶段分类不保证可重试。顺序/循环失败停止后续。
    Parallel 观察到失败或成员取消，取消未完成兄弟并等待清理后传播原异常；外层
    取消保持 CancelledError，清理异常不覆盖原异常，不分组、不返回部分结果；
    二次外层取消仍可中断等待。取消协作式，只管理直接等待链，不接管后台任务，
    快速失败不保证立即返回。不重试整个流程，NOOA 原生策略仍可重试。不回滚输入、
    材料、Agent 状态或外部副作用；错误/取消不记耗尽。不内置超时、持久化或关闭。

    叶子与 Team 都返回自身调用边界的业务结果，不要求同一类型/形状；None 是普通
    结果，不是跳过或保留前值。下游需接受实际结果形状。子 Team 保留自身模式，每次
    独立分配，包括外层 Loop 的每轮子调用。允许引用共享，不支持无限自调用，不做
    完整图校验。普通 Team 不自动有全组织 span。分配、轮次、任务和结果属于调用
    局部，固定配置留在实例。不承诺同一 Team/成员并发安全，独立 Agent 更易隔离历史。
    调用者管理 Agent、模型客户端及连接生命周期。只用 NOOA 公开 API，不改其源码。
    """

    async def execute(self, task: Any, context: Any) -> Any: ...
