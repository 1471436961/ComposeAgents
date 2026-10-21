# 实现与 review 入口

开始工作前按顺序阅读：

1. [实施计划与验收基线](docs/IMPLEMENTATION_PLAN.md)：唯一实施计划，统一记录 M0–M7 及后续三个台阶的范围、当前授权、契约决定、验证证据及阶段确认规则。
2. [README](README.md)：项目定位、核心抽象和完整执行契约。
3. [协议](src/nooa_patterns/protocols.py)：实际接口与协议 docstring。

## 必须遵守

- 本次任务为用户于 2026-10-21 授权的 Team 重构及冗余文件清理，设计见 docs/design/team-refactor.md；当前状态与实际结果统一看实施计划。用户已另行授权补充验证、分次提交与推送，无需再逐项确认；真实 LLM 应用与版本发布尚未授权。
- 修改里程碑状态时同步更新实施计划与 README 的当前进度；不得把实现完成、测试通过和用户确认混为一谈。
- 实施计划统一维护在 `docs/IMPLEMENTATION_PLAN.md`；必要的专题细节可独立成文并通过链接引用，不重复维护计划或阶段状态。
- 非必要不新增文档；是否新增由 agent 根据内容与维护需要自行判断，不以更新现有文件为优先规则。需要写文档时明确文档层级和职责，合理拆分并通过链接组织，避免内容重复或单篇过于冗长。
- 本项目是独立 Python 包，使用 `src` 布局；NOOA 只通过公开 API 调用。
- 禁止修改 `E:\ComposeAgents\labs-OO-Agents-main`，禁止复制或 fork NOOA 执行引擎。
- 核心只提供 PatternKind 的四种固定协作算法，由 Team 执行；删除旧 Pattern Protocol、四个 Pattern 类和 Members。复合模式只在 examples/composites 提供，不创建角色库、复合子包、Supervisor/GroupChat/Handoff 或其他协作引擎。
- README 与协议 docstring 都须保留完整契约。这是用户明确要求，不能仅根据去重建议删成摘要。
- 测试不得访问真实模型。保留并扩展真实 NOOA Agent + 公开 FakeLLMClient 集成；完整原生集成验收必须在 Linux/WSL 无跳过运行。
- 遵守平台提权机制；遇到沙箱限制不得改写测试语义来伪造通过。未执行、超时或被审批服务阻塞都不能报告为通过。

## Review 范围

以重构设计和当前 README/协议评审新接口，不按已删除的 Pattern/Members API 判定。
旧 M0–M7 与台阶一的计数仅是历史证据，不能代替新测试；记录见实施计划。
完整命令、断言和环境说明见实施计划，避免重复维护。
