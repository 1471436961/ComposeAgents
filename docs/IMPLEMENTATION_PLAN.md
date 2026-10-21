# 实施计划与验收基线

这是唯一实施计划。当前 API 与完整契约见 [README](../README.md)，技术设计见 [Team 重构方案](design/team-refactor.md)。
本次按用户要求合并重复说明和历史日志；旧阶段的完整记录仍可从下表对应 Git 提交恢复。

## 1. 当前范围与授权

2026-10-21 用户授权按重构设计完成代码迁移、删除不必要文档和代码，并在触及五小时限额时等待恢复后继续。
授权覆盖本次完整迁移、清理及验证，不需要在已授权的内部步骤间反复确认。
用户随后提供“技术复审通过、无阻塞项”的报告，并授权按确认的非阻塞建议补充原生分配测试及成员映射复用说明。
用户又明确要求分多次提交并推送至 GitHub origin/main；本次交付授权不自动延伸到台阶二。
真实 LLM 应用、角色库和版本发布不在本次范围。测试只用确定性 fake 与 NOOA 公开 FakeLLMClient。

`E:\ComposeAgents\labs-OO-Agents-main` 是只读参考，禁止修改；项目位于 `E:\ComposeAgents\nooa-patterns`。
使用 NOOA 公开 API，不复制其执行引擎。核心只有四值 PatternKind，由普通 Team 执行。
不添加第三方 Pattern、复合类、通用上下文引擎或生产 allocator 注入钩子。
README 和 TeamMember docstring 均保留完整契约，修改时同步；不得把通过测试误写成用户已完成技术复审。

## 2. 文档与清理规则

- README 是使用入口与当前契约；设计文档说明架构和语义；本文件记录授权、顺序、证据和状态。
- 非必要不新建文档，专题通过链接组织；不再为每次测试新增日志或独立计划。
- 历史 M4–M7 的重复 pytest 文本从工作树移除，历史结果和恢复提交见 §3；不把旧结果当新版本证据。
- 删除旧 Pattern/Members、对应的纯旧接口测试和逐阶段重复评审示例；保留或迁移有价值的取消、引用、反馈断言。
- 三个递进评审示例合并成 examples/technical_review.py；两个复合示例仍在 examples/composites，仅供复制修改。

## 3. 历史交付索引

以下均为旧 API 的历史验证，完整细节保留在 Git，不代表重构实现已通过。

| 阶段 | 交付内容 | 历史完整结果 | 交付提交 |
| --- | --- | --- | --- |
| M0 / M1 | 设计、弱类型协议、两条手写基线 | 3 passed | 803c4d2、b207b23 |
| M2 | 适配器、Sequential 与补充测试 | 18 passed | 17b86d9、f4ae217、08a3da9 |
| M3 | 递归 Team 与快照 | 29 passed | 74ec24e、59b36c4 |
| M4 | 等价对照、真实 Agent + FakeLLMClient | WSL 35 passed | d4d1b76、59d2c89、536fbcb |
| M5 | Parallel 及快速失败 | WSL 57 passed | 285264e、52be0d4、2cc65b5 |
| M6 | Members、Router 与技术评审 | WSL 95 passed | 626634d、383480f、180643b |
| M7 | Loop 及有界反馈 | WSL 136 passed | e23fe23、c639aba、daf14b9 |
| 台阶一 | EvaluatorOptimizer、Debate fake 示例 | WSL 157 passed | c50c07c、c1b368e、d577b1b |

重构开始时 HEAD 为 d577b1bf5d50c99047808be19d387e8aa94b30c4；原始日志可例如用
`git show d577b1b:docs/validation/M7_PYTEST.txt` 查看。台阶二真实应用与台阶三判断尚未实施。

## 16. Team 重构设计与迁移准备

2026-10-20 创建设计文档；2026-10-21 明确两层分配、取消描述构造参数、保留单成员、分配错误分类与直接预览，
随后用户明确授权代码重构。具体契约见[设计方案](design/team-refactor.md)，字段和验证目标不在本文件重复维护。

当前状态：主体重构已通过技术复审；确认的非阻塞补充已完成并本地验证。
代码与测试已按授权分次提交并推送 origin/main；本次文档与历史清理作为独立提交交付，不自动进入台阶二。

实施顺序与当前状态：

| 顺序 | 工作 | 状态 |
| --- | --- | --- |
| 1 | 固定枚举、命名只读成员、Team 四算法、局部 context、AllocationError | 已迁移 |
| 2 | 普通 allocate 自动描述、原生 standalone CodeAct 分配、延迟导入 | 已迁移并经 FakeLLMClient 验证 |
| 3 | 适配器原 callable 描述、原生叶子校验与实际模型输入筛选 | 已验证 |
| 4 | 手写/组合业务对照、两复合示例、四模式评审合并 | pytest 通过，Windows/WSL 各 8 个脚本或模块入口通过 |
| 5 | 删除旧接口/冗余日志、重写当前契约、链接与差异检查 | 已完成，旧模块已不存在，语法/链接/差异检查通过 |

### 本次实际验证

运行日：2026-10-21。下列是本次工具输出，不使用历史计数代替。

| 范围 | 命令 | 实际结果 |
| --- | --- | --- |
| 初始纯 Python 定向 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests/test_execution.py tests/test_allocation.py tests/test_adapters.py -q` | 74 passed in 0.18s |
| 初始真实 NOOA 定向 | WSL 禁网运行 test_nooa_allocation.py、test_nooa_adapter.py | 6 passed in 48.73s |
| 重构初版 Windows 全量 | `.venv/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider -q` | 130 passed, 2 skipped in 0.65s |
| 重构初版 WSL 全量 | `LITELLM_LOCAL_MODEL_COST_MAP=True unshare --net .uv-cache/wsl-venv/bin/python -X utf8 -m pytest -p no:cacheprovider -q` | 138 passed in 25.60s，无 skip |
| 隔离导入 | `.venv/Scripts/python.exe -I -B -X utf8 -` 导入五个公共名称，并检查旧模块的 import spec | 五名称导入成功；patterns、members 已不存在 |
| 静态检查 | AST 解析 src/examples/tests；Markdown 本地链接检查；`git diff --check` | 22 个 Python 文件、4 个 Markdown 文件、29 处链接通过，差异无空白错误 |

示例验证在 Windows 和 WSL 禁网环境分别完成，均为 8 个入口退出 0：
manual_flows、composed_flows、technical_review、EvaluatorOptimizer、Debate 五个脚本，
以及后三者的 `python -m examples...` 模块入口。运行时包含手写/组合结果和反馈断言。
文档缩写为 EvaluatorOptimizer 的实际模块名是 `examples.composites.evaluator_optimizer`。

Windows 的两个 skip 是原生 NOOA 集成模块，原因是锁定版本上游无条件导入 Unix fcntl。
真实分配、模型等待取消及叶子提示词筛选在 WSL 完整运行，不写 shim 或修改 NOOA。
Windows 沙箱内初次运行因已知 asyncio 阻塞被终止，未计为通过；表中 Windows 通过结果来自提权运行。

迁移时有两项嵌套取消测试最初超时：测试错误要求父 Team 在子 Team 尚未完成清理时就观察到子失败。
按原等待链契约修正观察顺序，仍断言内外层取消、清理完成和原异常身份；修正后已纳入上述全量通过结果。

验收重点已覆盖：不同局部任务、直接前驱/None、命名结果、嵌套 Loop 反馈、分配异常归属与 cause、
各层取消清理、原生参数/输出校验、实际叶子请求包含所选材料且排除根无关材料。
这证明 fake 条件下的控制和信息边界，不证明真实模型分配质量或应用效率。

### 技术复审后的非阻塞补充

2026-10-21 按用户确认补充以下内容，仅修改既有测试、README 和本计划，不改变生产接口、依赖或 NOOA 源码：

- 父 Team → 子 Team → 真实 EvidenceAgent 的原生调用链。两层均使用真实 allocate，FakeLLMClient 提供脚本响应；
  检查父层能看到子 Team 业务描述、子层只描述直接叶子、逐层材料引用保持，以及子层/叶子请求排除根上下文无关标记。
- Router/Loop 参数化原生用例。在 CodeAct 内检查实际 pattern_description 中的模式及 selector/until 文档、轮数；
  检查 Router 仅执行选中成员，Loop 完成两轮但只消费一次脚本化分配响应，并保留反馈身份。
- README 说明通过 `dict(team.members)` 复用成员映射；仍接受 dict，不扩大为 Mapping，也不新增文件。

本轮实际运行：

| 范围 | 命令 | 实际结果 |
| --- | --- | --- |
| WSL 原生分配定向 | `LITELLM_LOCAL_MODEL_COST_MAP=True unshare --net .uv-cache/wsl-venv/bin/python -B -X utf8 -m pytest -p no:cacheprovider tests/test_nooa_allocation.py -v` | 8 passed in 29.02s |
| Windows 全量 | `.venv/Scripts/python.exe -B -X utf8 -m pytest -p no:cacheprovider -q` | 130 passed, 2 skipped in 0.64s |
| WSL 禁网全量 | `LITELLM_LOCAL_MODEL_COST_MAP=True unshare --net .uv-cache/wsl-venv/bin/python -B -X utf8 -m pytest -p no:cacheprovider -q` | 141 passed in 25.37s，无 skip |

WSL 比初版增加 3 项：嵌套 1 项、模式参数化 2 项；Windows 两个 skip 仍为上游 fcntl 限制。
这些结果验证原生调用链和信息交接，不代表真实模型自主分配质量，也不把本地验证等同于补充内容已通过独立复审。

### 本次提交交付

2026-10-21 用户明确要求分多次提交并推送，按以下边界交付：

| 提交 | 内容 | 交付 |
| --- | --- | --- |
| 0fd2704 | Team 破坏性 API 迁移及必要的示例、控制流测试迁移 | 已推送 origin/main |
| da99710 | 原生分配、嵌套材料边界、Router/Loop 与取消集成验证 | 已推送 origin/main |
| 本文所在的文档提交 | 当前契约、设计与授权记录，删除重复历史日志 | 独立提交，随本次交付推送 |

破坏性接口与其必要调用方同次迁移，避免把旧测试留在不兼容的中间版本；原生集成证据和文档分别提交。
测试代码未在拆分时改写，沿用上方 141 项 WSL 全量通过的同一版本。

### 运行环境和汇报

- Windows Python 3.12、项目 .venv；WSL Ubuntu 24.04、项目 .uv-cache/wsl-venv，完整测试使用禁网命名空间。
- uv.lock 与 NOOA 依赖版本保持原锁；网络/权限问题不通过改写测试语义绕过。
- 本次未运行真实模型、未访问凭据、未修改 NOOA 参考源码或发布版本；代码与测试已按后续授权推送。
- 主体重构已通过技术复审；补充内容已本地验证，用户已授权提交交付，不据此宣称补充内容已通过独立复审。本次交付后停止，不自动进入台阶二。
