# 实现与 review 入口

开始工作前按顺序阅读：

1. [实施计划与验收基线](docs/IMPLEMENTATION_PLAN.md)：当前进度、M0–M4 范围、交付物、测试与确认规则。
2. [README](README.md)：项目定位、核心抽象和完整执行契约 v0。
3. [协议](src/nooa_patterns/protocols.py)：实际接口与协议 docstring。

## 必须遵守

- 当前完成到 M1；用户尚未授权进入 M2。每个里程碑完成后汇报并停止，只有用户确认后才进入下一里程碑。
- 修改里程碑状态时同步更新实施计划与 README 的当前进度；不得把实现完成、测试通过和用户确认混为一谈。
- 本项目是独立 Python 包，使用 `src` 布局；NOOA 只通过公开 API 调用。
- 禁止修改 `E:\ComposeAgents\labs-OO-Agents-main`，禁止复制或 fork NOOA 执行引擎。
- 首版生产模式只有 Sequential；Parallel、Router、循环、辩论和角色库不在 M1–M4 范围内。
- README 与协议 docstring 都须保留完整契约。这是用户明确要求，不能仅根据去重建议删成摘要。
- 测试不得访问真实模型。真实 NOOA Agent + 公开 FakeLLMClient 集成属于 M4。
- 遵守平台提权机制；遇到沙箱限制不得改写测试语义来伪造通过。未执行、超时或被审批服务阻塞都不能报告为通过。

## Review 范围

先从实施计划确认待审里程碑，只按该阶段已约定的交付与验收条件评审。
例如 M1 不要求 Team、适配器、Sequential 实现或完整 NOOA 运行时安装。
后续里程碑的缺失不能判为当前阶段缺陷；非阻塞建议也不能自动升级为验收门槛。
这些规则约束实施顺序，不影响 reviewer 只读检查整个项目并指出实际风险。

完整命令、测试断言和环境说明见实施计划，避免在此重复维护。
