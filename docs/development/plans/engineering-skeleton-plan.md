# Engineering Skeleton 执行计划

- 计划状态：Milestone A-E 已完成
- 工作分支：`feat/engineering-skeleton`（不切换分支）
- 目标：建立只提供健康状态与基础就绪性证明的最小可执行 monorepo，不实现任何 AI 视频产品功能
- 权威依据：`FOUNDATION.md`、项目级 `AGENTS.md`、`docs/product/`、`docs/architecture/`、`docs/adr/`

## 1. 仓库与环境基线

审查时仓库工作区干净，HEAD 为 `5ce452f`，当前分支及远程跟踪均为 `feat/engineering-skeleton`。仓库在本计划前只有工程宪法、文档、Node 版本文件、Codex 配置和 Node 运行包装脚本。

检测到的本地环境：

| 能力 | 版本/状态 |
| --- | --- |
| Node.js | `v24.18.0`，由 `.node-version` 固定 |
| npm | `11.16.0` |
| Python | `3.13.5` |
| uv | `0.11.11`，已安装；只用于仓库内虚拟环境与锁文件 |
| 网络 | Codex workspace 默认禁用；安装依赖前必须取得批准 |
| Docker | 不作为默认开发、测试或 CI 前提 |

所有 Node/npm/npx 命令必须通过 `./scripts/run-with-node.sh`。不得直接调用任何 JavaScript 包管理器。

## 2. 指令冲突与解决方式

### 已识别冲突

1. `AGENTS.md` 与 `FOUNDATION.md` 仍把当前阶段写为“只允许文档”，并禁止 `package.json`、依赖和脚手架；本任务明确授权进入第二阶段并要求这些工件。
2. `docs/development/local-setup.md` 要求实现阶段必须已接受技术选型 ADR；当前 ADR 只冻结架构边界，没有记录 Next.js、FastAPI、npm workspace 与 Python 工具链。
3. `docs/development/environment-assumptions.md` 把框架视为未选假设；本任务已明确本里程碑的框架，但这些选型仍应保留可替换状态。

### 解决顺序

获得依赖批准后、创建任何脚手架前：

1. 新增 `ADR-011-engineering-skeleton-toolchain.md`，记录 npm workspaces、Next.js、FastAPI、Python Worker、uv 和 canonical JSON Schema；状态为本里程碑已接受，框架仍属可替换实现假设。
2. 更新 `AGENTS.md` 的当前阶段，允许第二阶段基础骨架，同时继续禁止全部产品功能、Provider、数据库和云资源。
3. 更新 `FOUNDATION.md`、环境假设和本地设置文档的阶段说明，不改写 ADR-001 至 ADR-010 的历史决定。

该处理不触发微服务复审：Web、API、Worker 是职责/进程边界，仍属于一个 monorepo 和一个模块化单体系统，不引入服务自治、独立数据所有权或分布式事务。

## 3. 关键实现决定

| 主题 | 本里程碑决定 | 边界 |
| --- | --- | --- |
| JavaScript workspace | 普通 npm workspaces | 不引入 Nx/Turborepo/pnpm/yarn |
| Web | Next.js App Router、TypeScript strict、服务端 health client | 不含产品页面、认证或浏览器 Provider 调用 |
| Python workspace | 单一根 `pyproject.toml`、uv lock、仓库内 `.venv` | API/Worker 可独立启动，共享质量标准，不共享领域内部实现 |
| API | FastAPI application factory、`/api/v1/health` | 无数据库、认证、业务路由 |
| Worker | 可执行 self-check/one-shot 进程 | 零生产 handler；无轮询、队列、重试 |
| Contract | `packages/contracts` 中单一 versioned JSON Schema | Python 与 TypeScript 均在测试和运行边界验证；不生成 SDK |
| Model registry | 小型 Python protocol/registry/capability model | 无真实 Provider、路由、Prompt 或生成逻辑 |
| Logging | Python 标准库 JSON formatter；服务端事件字段固定 | 无 hosted logging 或 OpenTelemetry 基础设施 |
| Task runner | 根 `Makefile` | Node 子命令必须调用包装脚本；不要求 Docker |

健康契约的 `contract_version` 固定为 Schema 中的版本常量。Schema 以 `additionalProperties: false` 和必填字段防止消费者静默接受漂移。Python API 的响应在返回边界验证；Web API client 用同一 JSON Schema 和 Ajv 验证。

## 4. 依赖提案

以下是允许安装的完整直接依赖范围。安装时使用稳定、兼容 Node 24 / Python 3.13 的版本，并由 `package-lock.json` 与 `uv.lock` 固定解析结果；若解析要求新增直接依赖，必须先更新本计划并再次说明。

### JavaScript 生产依赖

| 依赖 | 用途 |
| --- | --- |
| `next` | Web App Router、服务端渲染与构建 |
| `react`, `react-dom` | Next.js 必需的视图运行时 |
| `ajv` | 在 TypeScript 边界可靠验证 canonical JSON Schema |
| `@foundation/contracts` | 本地 workspace 契约包，不从网络获取 |

### JavaScript 开发依赖

| 依赖 | 用途 |
| --- | --- |
| `typescript` | strict 静态类型检查 |
| `@types/node`, `@types/react`, `@types/react-dom` | TypeScript 类型定义 |
| `eslint`, `eslint-config-next` | Next.js/React/TypeScript lint 规则 |
| `vitest` | Web client 与组件的快速测试 |
| `@testing-library/react`, `@testing-library/dom`, `@testing-library/jest-dom` | 当前状态页行为和错误状态断言所需的最小 Testing Library 集合 |
| `jsdom` | Vitest 的轻量 DOM 运行环境；不提供浏览器自动化或交互框架 |
| `prettier` | JS/TS/JSON/Markdown/CSS 的统一格式检查；不与 ESLint 重叠承担语义 lint |

### Python 运行依赖

| 依赖 | 用途 |
| --- | --- |
| `fastapi` | API 路由、生命周期与异常边界 |
| `uvicorn` | 本地 ASGI 服务进程 |
| `pydantic` | API、Worker、model registry 的结构化验证 |
| `pydantic-settings` | API/Worker 环境配置验证 |
| `jsonschema` | Python 侧对 canonical health JSON Schema 的运行/测试验证 |

### Python 开发依赖

| 依赖 | 用途 |
| --- | --- |
| `pytest` | API、Worker、契约、registry 与集成测试 |
| `httpx` | FastAPI `TestClient` 所需且用于进程内 API 测试 |
| `ruff` | Python formatter 与 lint，避免叠加多个格式工具 |
| `mypy` | Python strict 静态类型检查 |

不加入生产队列、数据库客户端、Provider SDK、UI 框架、代码生成器、OpenTelemetry、Docker Python/Node SDK 或云依赖。

## 5. 目标结构

```text
apps/web/                    Next.js foundation status page
services/api/                FastAPI application factory and health route
services/worker/             one-shot Worker readiness process
packages/contracts/          canonical health JSON Schema and TS validator
packages/model-registry/     minimal provider capability/registration boundary
packages/test-fixtures/      deterministic non-sensitive JSON fixtures
infra/migrations/            documented empty boundary; no database migrations
infra/scripts/               infrastructure script boundary; no cloud scripts
infra/docker/                documented future boundary; Docker not required
tests/integration/           cross-component contract integration tests
tests/end-to-end/            documented boundary; no browser E2E dependency yet
docs/development/plans/      this tracked execution plan
```

空边界目录使用说明文件保留，不使用伪业务实现。

## 6. 分阶段执行与验证

### Milestone A — 审查、计划、依赖批准

- [x] 检查完整仓库、Git 状态与近期提交。
- [x] 阅读工程宪法、产品边界、架构、全部 ADR、Codex 配置和 Node 包装脚本。
- [x] 识别阶段指令冲突并制定追加 ADR/文档更新方案。
- [x] 检测 Node、npm、Python 与 uv 环境。
- [x] 写入执行计划和直接依赖提案。
- [x] 获得仅访问官方 npm/Python 注册表的依赖安装批准；批准时移除 `python-dotenv` 并收紧 Testing Library 包集合。

验证：`git diff --check`、计划与 ADR/产品非目标的人工一致性审查。

### Milestone B — 根工作区与 Web

- [x] 先新增 ADR-011 并更新阶段性治理文档。
- [x] 建立根 `package.json`、npm workspaces、`.gitignore` 与 `.env.example`；`Makefile` 在 Milestone E 汇总全部命令。
- [x] 通过包装脚本从官方 npm registry 安装并锁定 JavaScript 依赖。
- [x] 创建严格 TypeScript Next.js App Router skeleton、验证环境配置、health client 与状态页。
- [x] 添加 Web 的成功、不可用、无效响应和页面状态测试。

验证：Prettier、ESLint、TypeScript 均通过；contracts 3 项与 Web 5 项测试通过；Next.js 16.2.10 production build 通过；未发现产品功能或云连接。canonical contract 因 Web 从第一天必须验证响应而提前创建，Python 集成仍在 Milestone D 完成。

### Milestone C — API 与 Worker

- [x] 建立根 Python 项目、仓库内虚拟环境与 `uv.lock`。
- [x] 创建 FastAPI factory、版本化 health route、配置、结构化日志、CORS 与安全异常处理。
- [x] 创建 Worker self-check，明确零生产 handlers 并正常退出。
- [x] 创建最小 model registry protocol/registry/capability schema。
- [x] 添加 API、Worker、配置和 registry 测试。

验证：Ruff format/lint、strict mypy 均通过；API/Worker/Python contract/registry 共 17 项 pytest 通过。`python-dotenv` 不是直接依赖，但由 `pydantic-settings` 官方依赖元数据传递安装；代码未启用 dotenv 文件读取。Starlette 对已批准的 `httpx` 发出迁移到未批准 `httpx2` 的提示，记录为非阻塞已知限制，不新增依赖。

### Milestone D — Canonical contract 与集成

- [x] 创建 versioned health JSON Schema、契约所有权与演进文档。
- [x] 添加有效/无效 health 与 capability fixtures。
- [x] Python API 和 TypeScript client 使用同一 schema 验证。
- [x] 添加 API schema conformity 与 Web client 接受真实 API 响应的集成测试。

验证：两种语言的 valid/invalid/version 契约测试通过；本地 Uvicorn 真实进程由 Web health client 调用并接受；手工运行态 smoke test 确认页面渲染 `Connected`、service `foundation-api`、API version `0.1.0` 与 contract version `1.0.0`。

### Milestone E — CI 与文档闭环

- [x] 建立无 secret、无部署步骤的 GitHub Actions workflow。
- [x] 完成根命令：`setup`、`dev-web`、`dev-api`、`dev-worker`、`dev`、`format`、`lint`、`typecheck`、`test`、`build`、`check`。
- [x] 更新 README、local setup、testing、observability、system context 和环境说明，使其与实际一致。
- [x] 执行全量 `make check`、组件启动、Web→API smoke test和最终 diff/安全审查。

验证：`package-lock.json` 与 `uv.lock` 已生成；最终 `make check` 通过 Prettier、Ruff format、ESLint、Ruff lint、TypeScript、strict mypy、10 项 Web/contract JS 测试、18 项 Python 测试、契约专项复验和 Next.js 16.2.10 production build。API、Web 与 Worker 均独立启动成功，运行态健康链路通过。

## 7. 偏差记录

1. canonical health schema 在 Milestone B 创建，而非等到 D；原因是 Web health client 从首次实现起就必须验证真实边界。Milestone D 完成 Python 消费端与跨进程集成，没有改变架构。
2. 初次 npm 下载曾产生不完整 `node_modules`。确认没有属于仓库的活跃 npm/node 安装进程后，仅删除根/工作区 `node_modules` 与任务临时缓存，保留有效 `package-lock.json`；随后唯一一次 `npm ci --registry=https://registry.npmjs.org/ --no-audit --no-fund` 退出码为 0。
3. `python-dotenv` 已从直接依赖提案和 `pyproject.toml` 删除，但 `pydantic-settings 2.14.2` 的官方依赖元数据将其作为传递依赖锁入。实现未配置 `env_file` 或调用 dotenv，只从进程环境读取。若要求从依赖图完全排除，必须在未来 ADR 中替换 `pydantic-settings`。
4. 当前 Starlette 对已批准的 `httpx` 测试适配层发出迁移至 `httpx2` 的弃用提示。测试与运行均通过；由于 `httpx2` 未获依赖批准，本里程碑不新增它，后续在 FastAPI/Starlette 正式移除兼容层前复审。
5. monorepo Python packages 未引入额外构建后端；Makefile 与测试配置显式设置仓库内 `PYTHONPATH`。若未来独立发布组件，再复审可安装 package 布局。

没有修改 ADR-001 至 ADR-010 的原始决策，没有新增产品功能、真实 Provider、数据库、生产队列、云资源或未批准的直接依赖。
