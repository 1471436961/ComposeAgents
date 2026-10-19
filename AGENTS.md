# 实现与 review 入口

开始工作前按顺序阅读：

1. [实施计划与验收基线](docs/IMPLEMENTATION_PLAN.md)：唯一实施计划，统一记录 M0–M7 及后续三个台阶的范围、当前授权、契约决定、验证证据及阶段确认规则。
2. [README](README.md)：项目定位、核心抽象和完整执行契约。
3. [协议](src/nooa_patterns/protocols.py)：实际接口与协议 docstring。

## 必须遵守

- 当前停在台阶一：EvaluatorOptimizer、Debate 复合示例与手写对照已通过本地验证及 reviewer 技术复审，无阻塞项；独立定向 21 项、WSL 禁网全量 157 项通过，见实施计划 §15.4。已按用户指示分次提交并推送，交付见 §15.5，后续工作等待用户确认。src/、依赖与公开 API 未改，不调用真实模型。M0–M7 已完成并交付；台阶二真实应用、台阶三判断尚未授权开始。
- 修改里程碑状态时同步更新实施计划与 README 的当前进度；不得把实现完成、测试通过和用户确认混为一谈。
- 实施计划统一维护在 `docs/IMPLEMENTATION_PLAN.md`；必要的专题细节可独立成文并通过链接引用，不重复维护计划或阶段状态。
- 非必要不新增文档；是否新增由 agent 根据内容与维护需要自行判断，不以更新现有文件为优先规则。需要写文档时明确文档层级和职责，合理拆分并通过链接组织，避免内容重复或单篇过于冗长。
- 本项目是独立 Python 包，使用 `src` 布局；NOOA 只通过公开 API 调用。
- 禁止修改 `E:\ComposeAgents\labs-OO-Agents-main`，禁止复制或 fork NOOA 执行引擎。
- 核心只提供 Sequential、Parallel、Router、Loop 四种基础原语。复合模式只在 examples/composites 提供，不新增 Pattern 类或公开 API；同一组合至少在 3 个真实场景重复且契约稳定后，才可提议可选 composites 子包，不能自动提升。Supervisor、GroupChat、Handoff 不作标准 Pattern，Blackboard、ContractNet、Negotiation 不做，本轮不创建角色库或应用模板。
- README 与协议 docstring 都须保留完整契约。这是用户明确要求，不能仅根据去重建议删成摘要。
- 测试不得访问真实模型。真实 NOOA Agent + 公开 FakeLLMClient 集成属于 M4。
- 遵守平台提权机制；遇到沙箱限制不得改写测试语义来伪造通过。未执行、超时或被审批服务阻塞都不能报告为通过。

## Review 范围

先从实施计划确认待审里程碑，只按该阶段已约定的交付与验收条件评审。
例如 M1 不要求 Team、适配器、Sequential 实现或完整 NOOA 运行时安装。
后续里程碑的缺失不能判为当前阶段缺陷；非阻塞建议也不能自动升级为验收门槛。
这些规则约束实施顺序，不影响 reviewer 只读检查整个项目并指出实际风险。

完整命令、测试断言和环境说明见实施计划，避免在此重复维护。
