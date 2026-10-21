# 实施计划与当前基线

这是唯一实施计划。当前接口与完整契约见 [README](../README.md)，架构依据见 [Team 重构设计](design/team-refactor.md)。
本文件从已完成重构的现实出发维护当前任务；此前的阶段安排不再作为路线图，历史内容仅通过 Git 查询。

## 1. 当前任务与授权

当前已确认采用相对通用的 GPU 推理优化研发团队方案，已完成 [EdgeSeg-EfficientViT 原始需求](requirements/edgeseg-efficientvit.md)。
用户现授权提交并推送已完成的文档和此前清理提交；本轮不构建团队、不实现应用、不调用真实模型。

此前背景与已完成工作：

2026-10-21 用户要求清理过时文档，删除 examples 下的全部现有文件和子目录，然后重新讨论合适的应用场景。
用户明确纠正：场景确认前不编写新示例，不沿用原技术评审场景。

本轮范围：

- 清空 examples，包括原复合示例目录和讨论前过早生成的三个新文件。
- 删除仅依赖这些示例的测试，清理文档中的失效引用和旧路线表述。
- 保留核心实现、控制流与原生 NOOA 集成测试，并运行回归检查。
- 只讨论新的应用场景；尚未授权应用实现、真实模型调用、模型凭据、预算、版本发布或推送。

用户随后要求先提交本次清理，再搜索公开多智能体评测与论文以重新讨论应用场景。
该指令授权本轮本地提交，尚未授权推送；搜索和讨论不等于授权实现新场景。

用户随后授权检查本机执行环境并处理 WSL 联网问题；本次环境配置与验证不包含新应用实现、真实模型调用、提交或推送。

`E:\ComposeAgents\nooa-patterns` 是项目及 Git 仓库；`E:\ComposeAgents\labs-OO-Agents-main` 为只读 NOOA 参考源码，禁止修改。

## 2. 重构后的实际能力与边界

- Team 是普通 Python 类，固定持有只读命名成员和 PatternKind，递归成员可为叶子或子 Team。
- 四种固定算法是 SEQUENTIAL、PARALLEL、ROUTER、LOOP，由 Team 执行。
- 每次 execute 先通过 NOOA 公开描述和 standalone CodeAct 分配一次；成员使用局部 materials/upstream/feedback。
- 核心保留弱类型边界、分配错误分类、引用传递、异常与取消清理契约；不新增 Pattern 扩展点、规划器钩子或上下文引擎。
- 信息交接已通过 FakeLLMClient 原生调用验证；真实模型的自主分配质量、成本和开发体验仍未被证明。

README 与 TeamMember docstring 均保留完整契约，修改时同步。测试通过、技术复审和用户验收是不同状态。

## 3. 已交付基线

| 提交 | 内容 | 交付 |
| --- | --- | --- |
| 0fd2704 | Team 执行与信息分配重构、必要调用方迁移 | 已推送 origin/main |
| da99710 | 原生分配、嵌套输入筛选、模式描述与取消验证 | 已推送 origin/main |
| 7861ccd | 重构契约、设计、授权及文档整理 | 已推送 origin/main |

主体重构技术复审通过；其后确认的补充测试已完成本地验证。
清理前的基线为 Windows 130 passed、2 个 NOOA 模块平台跳过，WSL 禁网 141 passed 无跳过。
原生分配模块 8 项覆盖父子独立分配、材料活引用、叶子实际模型输入、Router/Loop 和取消。
这些是清理前的历史结果，不代表当前测试集合；完整旧文件可用 `git show 7861ccd:路径` 查询。

## 4. 本轮清理与验证

清理已完成：示例清空，专属测试与文档引用清理，回归验证通过。未创建新示例；当前需求准备状态见 §5。

| 内容 | 状态 |
| --- | --- |
| examples 全部文件及子目录 | 已删除，目录留空 |
| 旧示例专属测试 | 已删除 4 个文件及其 37 项专属用例 |
| AGENTS、README、设计与本计划 | 已取消旧路线，删除失效示例引用 |
| 核心实现与原生集成断言 | 保留，不修改生产接口 |
| 当前全量回归与链接检查 | 已通过，实际输出见下方 |

运行方式：

```powershell
.venv/Scripts/python.exe -B -X utf8 -m pytest -p no:cacheprovider -q
```

WSL 完整验收：

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True unshare --net .uv-cache/wsl-venv/bin/python -B -X utf8 -m pytest -p no:cacheprovider -q
```

原生 Windows 仍受上游 NOOA 无条件导入 Unix fcntl 的限制，两个原生集成模块会明确跳过。
完整原生验收必须在 Linux/WSL 无跳过运行；不写 shim、不修改 NOOA、不把未执行或超时报告为通过。
不为本轮新增验证日志或另一份计划，实际输出统一在本节记录。

2026-10-21 本次实际结果：

| 检查 | 输出 |
| --- | --- |
| Windows 上述命令，按已知 asyncio 沙箱限制提权运行 | 93 passed, 2 skipped in 0.36s |
| WSL 上述命令，禁网命名空间 | 104 passed in 30.23s，无 skip |
| 语法与本地文档链接 | 13 个 Python 文件、4 个 Markdown 文件、25 处链接通过 |
| 清理与差异检查 | examples 无文件或子目录，无示例导入残留，git diff --check 通过 |

相较清理前减少的 37 项均为已删除示例的专属测试；核心和原生分配测试未删改。
清理未修改 src、依赖或只读 NOOA 源码，未运行真实模型。清理对应提交为 63c41cf，纳入本次授权推送。

## 5. 领域团队方向与需求材料

用户确认先构建相对通用的 GPU 推理优化研发团队，再将具体项目需求交给该团队执行。
首个项目采用 [EdgeSeg-EfficientViT 原始需求](requirements/edgeseg-efficientvit.md)，当前已落盘并获准提交推送；它是业务输入，不是另一份实施计划。

- 需求描述目标、资源、初步优化建议、交付期望与工作边界，不指定成员、Pattern、工作流、具体算子实现或预期数值答案。
- 保留原始技术建议，由执行团队依据源码与实测作出技术判断；不在需求中揭示纠正结论。
- 已有同题项目及其结果留作独立参考，不将其解法写入团队代码、角色提示或任务输入。
- 只向执行团队提供获准的需求、独立工作区及资源；本实施计划、设计历史和当前聊天不默认作为执行材料。
- 本轮不新增团队代码、工具执行层、验收程序或另一份规划文档；后续实现、具体运行预算和真实模型访问另行确认。

## 6. 本机 WSL 联网修复

2026-10-21 已按用户授权完成配置与实际验证。
原因为 WSL 使用 NAT，无法连接 Windows 仅监听回环地址的 `127.0.0.1:26799` 代理。
原先不存在用户级 `.wslconfig`；现新建 `%UserProfile%\.wslconfig`，内容为：

```ini
[wsl2]
networkingMode=mirrored
autoProxy=true
dnsTunneling=true
```

确认所有发行版均停止后，执行 `wsl.exe --shutdown` 并重新启动 Ubuntu-24.04。
实际网络模式为 mirrored，HTTP/HTTPS 代理变量自动指向 `127.0.0.1:26799`。

- DNS 查询正常；WSL 默认 HTTPS 访问 GitHub、PyPI 均返回 200。
- 项目 WSL 虚拟环境中的 HTTPX 异步 HTTPS 均返回 200，Git 远程 HEAD 只读查询成功。
- NOOA/Team 导入正常，CUDA 驱动仍识别到 MX250，Windows Python 子进程互通正常。
- 未改变 Windows 代理监听、系统防火墙、GPU 工程或项目生产代码，未使用模型凭据或调用真实模型。

此处统一保留环境验证结果，不另建联网报告。真实模型服务的具体地址与认证尚未验证。
