# 实施计划与当前基线

这是唯一实施计划。当前接口与完整契约见 [README](../README.md)，架构依据见 [Team 重构设计](design/team-refactor.md)。
本文件从已完成重构的现实出发维护当前任务；此前的阶段安排不再作为路线图，历史内容仅通过 Git 查询。

## 1. 当前任务与授权

当前已确认采用相对通用的 GPU 推理优化研发团队方案，已完成 [EdgeSeg-EfficientViT 原始需求](requirements/edgeseg-efficientvit.md)。
此前文档与清理已提交推送，基线为 `63174f9`。通用团队已获离线技术复审通过，Evidence 边界修正和英文描述调整均已完成验证。用户现授权将这些已完成工作分次提交并推送，见 §7.3；不扩展权限隔离或预算机制，不运行真实模型、不执行具体项目。

此前已完成的清理与环境工作见 §4–§6：删除全部旧示例、保留核心与原生集成、准备独立业务需求并修复 WSL 联网。
这些任务各自的授权已经执行完毕，不构成本轮运行真实模型或提交新应用的授权。

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
- 现已授权团队实现；具体项目运行、模型凭据、调用预算和真实模型访问仍未授权。当前实施内容见 §7。

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

## 7. 通用推理优化团队（当前任务）

应用放在 `applications/inference_optimization/`，不扩展核心 API、依赖或 PatternKind。
组织为有界 Loop：并行调查子 Team（模型/计算图、运行环境/性能）→ 实验规划 → 工程实现 → 独立验证。
accepted 或 blocked 终止；revise 在轮次上限内反馈，达到上限返回应用级 exhausted。
不为使用全部算法而添加 Router。每次子调查调用独立原生分配，计划使用实际调查和上一轮反馈。

实现顺序与验证：

1. 定义 Findings、实验计划、变更、验证与迭代数据；真实上游记录由普通 Python 组合，不要求模型重复生成。
2. 实现 NOOA CodeAct 角色与递归 Team；所有生产分配使用原生 allocate，不注入测试 planner。
3. 复用 NOOA ShellTools，补充命令证据、工作区文件路径检查、全队命令串行化和资源生命周期。
4. 提供显式 CLI（需求、工作区、模型、轮数、总超时），无导入即执行，无真实模型默认演示。
5. Windows 验证可移植工具/数据边界；WSL 以公开 FakeLLMClient 跑真实原生分配/角色与临时文件命令，覆盖反馈、失败、取消、耗尽和独立验证证据。
6. 完成全量回归后在本节记录实际输出，再汇报；实现阶段不自动提交推送。其后用户已单独授权本次交付，未授权执行需求项目。

重要边界：团队通用于模型/硬件/运行时不同的推理优化项目，不硬编码 EdgeSeg 解法；角色工具约束不等于 OS 沙箱。
命令在调用者提供的隔离环境执行；文件工具禁止越界，但任意 shell/CodeAct 需要外部容器/VM 等隔离。
缺少权限、软件、数据或预算时报告 blocked，不自动安装/下载/改系统。所有命令共享锁，只排除本应用内部测量重叠。
独立验证检查引用的真实命令，不能把“有一条成功命令”当作完整质量证明；真实研究质量和模型成本仍待后续实跑。

初版实现及离线技术复审通过；Evidence 边界修正结果见 §7.1，英文描述调整见 §7.2，本次提交推送授权见 §7.3。未执行真实模型或具体项目。

实际文件：

- `applications/inference_optimization/models.py`：具体业务记录，携带原始 Findings/Plan/Changes，避免模型复述丢失。
- `agents.py`：五个 NOOA 角色，原生 CodeAct，单次角色方法最多 12 轮，原生重试上限 1。
- `team.py`：原生分配的调查子 Team 与有界主 Team，纯同步终止规则，应用级 RunResult。
- `workspace.py`：ShellTools 生命周期、文件工具路径检查、全队命令锁、stdout/stderr/stdin 与命令证据。
- `__main__.py`：显式 CLI，需求/工作区/模型/轮次/总超时均由调用者给定。
- 两个测试文件新增 16 项：可移植边界 9 项，真实 NOOA 集成 7 项。

2026-10-21 本次实际验证：

```powershell
.venv/Scripts/python.exe -B -X utf8 -m pytest -p no:cacheprovider -q
# 102 passed, 3 skipped in 0.51s
```

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True unshare --net .uv-cache/wsl-venv/bin/python -B -X utf8 -m pytest -p no:cacheprovider -q
# 120 passed in 36.11s
```

新增原生集成定向运行 `tests/test_inference_team.py -x -v`：7 passed in 37.51s。
Windows 的三个平台跳过分别是原生适配、原生分配、新应用原生集成模块；WSL 全部执行。
CLI `--help` 在 Windows 可运行，不导入 NOOA 或调用模型。22 个 Python 文件语法解析、30 个本地链接与 `git diff --check` 通过。
`src/`、pyproject、锁文件与业务需求无 diff；只读 NOOA 源码未编辑，examples 仍为空。

关键断言：

- 真实 standalone 根分配一次，调查子 Team 每轮分配一次，五个真实 Agent 使用各自脚本化客户端；响应全部耗尽，没有网络请求。
- 临时文件实际修改；实施与验证命令分开执行并记录；两轮路径实际先检查失败、反馈后再检查通过。
- accepted、blocked、exhausted 三种正常结果不同；分配取消、命令取消和业务校验错误不产生成功/耗尽结果。
- 验证者引用本次命令，否则拒绝 accepted；错误角色、旧轮次或虚构命令 ID 被拒绝。
- 模型能看到原生对象工具描述；根无关材料未进入叶子首轮提示。结构化上游对象携带实际调查/计划，不靠复制提示历史。
- 命令串行、真实命令超时、取消后 Linux 前台进程停止、次要清理错误不覆盖原命令错误；文件工具越界/证据改写拒绝。

尚未证明：真实模型的自主研究/分配质量、真实 GPU 优化收益、完整模型调用成本与跨 Windows 进程清理。
命令记录与独立执行检查只提供可追溯的运行证据，不自动证明实验充分；调用者仍须提供隔离、环境、权限与成本预算。

### 7.1 Evidence 边界修正

- Evidence 根目录和当前 run 目录检查实际路径，拒绝符号链接/junction 重定向；命令日志、stdout/stderr/stdin、最终结果和失败记录统一检查写入目标。
- 文件读取与目录浏览仅暴露当前 run 的 evidence，路径别名也按解析目标检查。历史运行记录保留，供外部审计，不自动删除。
- 已补充预置/创建后替换链接、跨 run 读取和真实 ShellTools 回归；具体结果如下。
- 这些是文件工具的路径约束，不能阻止任意 shell/CodeAct 绕过，也不声称抵御并发恶意路径替换；OS 隔离、验收充分性和成本预算仍属真实运行准备事项。

修正实现与离线验证完成，已纳入本次授权交付；上一节 102/120 为修正前基线。新增 10 项回归（可移植 6 项、原生 4 项），没有删除历史证据。

2026-10-21 实际运行：

| 范围 | 命令与输出 |
| --- | --- |
| Windows 定向 | `python -B -X utf8 -m pytest -p no:cacheprovider tests/test_inference_workspace.py -v`：15 passed in 0.85s，包含实际 junction |
| WSL 禁网定向 | `python -B -X utf8 -m pytest -p no:cacheprovider tests/test_inference_workspace.py tests/test_inference_team.py -x -v`：26 passed in 34.13s |
| Windows 全量 | `.venv/Scripts/python.exe -B -X utf8 -m pytest -p no:cacheprovider -q`：108 passed, 3 skipped in 1.55s |
| WSL 禁网全量 | `LITELLM_LOCAL_MODEL_COST_MAP=True unshare --net .uv-cache/wsl-venv/bin/python -B -X utf8 -m pytest -p no:cacheprovider -q`：130 passed in 31.55s，无 skip |

Windows 测试按既有规则提权运行；WSL 使用 `.uv-cache/wsl-venv/bin/python`。三个 Windows skip 仍是上游 fcntl 平台限制的原生模块。
22 个 Python 文件语法解析、30 个本地文档链接、`git diff --check` 通过；核心、依赖、锁文件和业务需求无 diff，examples 仍为空。
本修正没有新建文档、运行真实模型或执行具体项目；提交前验证记录如上，本次交付见 §7.3。后续权限隔离、验收质量与预算仍须按真实运行需求确认。

### 7.2 代码描述统一为英文

- 扫描自有源码、应用、测试及文档中的 Python 示例；源码中文仅发现于 TeamMember 的完整契约。
- 翻译 `protocols.py` 的完整 docstring，以及 README/设计文档中 Python 示例的 docstring 和注释；独立中文文档正文与业务需求保持原有语言。
- 不新增语言断言测试；通过扫描、去除 docstring 后的 AST 比较和现有全量回归验证，不改变执行方法签名或业务逻辑。

翻译与验证完成：22 个自有 Python 文件无中文，README/设计文档中的 Python 示例也无中文；移除 docstring 后，协议文件与 HEAD 基线的 AST 完全一致。完整契约保留，未新增 API、依赖或测试。

2026-10-21 使用 §7.1 的全量命令实际重跑：Windows 为 `108 passed, 3 skipped in 1.32s`；WSL 禁网为 `130 passed in 55.72s`，无 skip。
`git diff --check` 通过，未修改 NOOA 参考源码或业务需求，未运行真实模型；本次交付见 §7.3。

### 7.3 本次提交与推送

2026-10-21 用户授权提交并推送。按职责拆分：

- `da5a43a`：通用推理优化团队、Evidence 边界与完整离线测试。
- 本节所在文档提交：英文协议及 Python 示例、应用使用说明、授权状态与实际验证记录。

提交不改变上一轮已验证的执行逻辑，不重复运行已通过的测试。远程交付以本地 HEAD、origin/main 和 GitHub main 引用一致为核验依据；不强制推送。
