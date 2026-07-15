# Tenant-aware Persistence Foundation 执行计划

- 计划状态：Milestone A–E 已完成；本地 PostgreSQL 与全部质量门禁已验证
- 工作分支：`feat/tenant-persistence-foundation`（不切换分支）
- 目标：建立 tenant-aware PostgreSQL 持久化、最小 Project 领域、原子审计与隔离证明；不实现 Brief、AI、认证 Provider 或产品 UI
- 权威依据：`FOUNDATION.md`、项目级 `AGENTS.md`、`docs/product/`、`docs/architecture/`、ADR-001 至 ADR-011

## 1. 仓库与环境基线

审查时工作区干净，分支为 `feat/tenant-persistence-foundation`，基线提交为 `5915510`。现有 Web/API/Worker、health contract、model registry、锁文件和 CI 均可工作；`infra/migrations/` 与 `infra/docker/` 只有边界说明，没有数据库实现。

| 能力                  | 检测结果                                         |
| --------------------- | ------------------------------------------------ |
| Node.js / npm         | `v24.18.0` / `11.16.0`，经仓库 wrapper           |
| Python / uv           | `3.13.5` / `0.11.11`，仓库内 `.venv`             |
| FastAPI / Pydantic    | `0.139.0` / `2.13.4`                             |
| Docker                | CLI `29.4.2`；daemon 已运行并验证 `postgres:17-alpine` |
| PostgreSQL CLI/server | 未检测到 `psql`、`postgres` 或 `pg_isready`      |
| 网络                  | 默认关闭；安装新依赖或拉取镜像前必须获得明确批准 |

## 2. 治理冲突与解决顺序

当前 `FOUNDATION.md`、`AGENTS.md`、README 和开发文档仍把仓库描述为第二阶段，并明确禁止数据库。这与当前用户任务授权的第三阶段直接冲突。当前任务只覆盖 tenant persistence 与 Project 基础，不放宽 Brief、AI、Provider、认证、队列、云或 UI 非目标。

在任何运行时代码或迁移实现之前，按下列顺序处理：

1. 追加 ADR-012 至 ADR-016；不改写 ADR-001 至 ADR-011。
2. 获得直接依赖安装批准后，将新 ADR 状态从“提议”更新为“已接受”，并只更新治理文档的当前阶段说明。
3. 保留模块化单体：API 内部新增 domain/application/infrastructure/presentation 边界，不创建独立服务或分布式事务。
4. 将 PostgreSQL、SQLAlchemy、Alembic、psycopg 和临时请求头身份视为可替换实现假设；tenant、版本、审计和服务端授权原则仍为冻结决定。

## 3. 拟议架构决定

### 3.1 数据库与迁移

- 生产数据库契约固定为 PostgreSQL；测试持久化语义不使用 SQLite。
- 采用同步 SQLAlchemy 2.x Session、Alembic 和 psycopg 3。当前请求规模没有证据证明 async 数据库层能抵消其测试与事务复杂度。
- Alembic 配置位于仓库根与 `infra/migrations/`；迁移版本提交、可审查，并在合理可行时提供 downgrade。
- PostgreSQL 17 作为本里程碑固定测试主版本。CI 使用无 secrets 的 service container；本地支持原生 PostgreSQL 或可选 Docker，不把 Docker 作为唯一方式。

### 3.2 tenant 与成员关系

层级固定为 `Organization → Workspace → Project`。Project 永远同时保存 `organization_id` 与 `workspace_id`，并以复合外键保证 Workspace 属于同一 Organization。

Membership 允许两种明确 scope：

- `workspace_id IS NULL`：仅允许 `owner`、`admin`，代表 Organization-wide membership；创建 Organization 时原子创建初始 owner。
- `workspace_id IS NOT NULL`：允许 `admin`、`member`、`viewer`，并以复合外键绑定同一 Organization 下的 Workspace。

最小权限规则：owner/admin 可创建 Workspace 与 Membership；owner/admin/member 可创建和变更 Project；viewer 只读。任何 active membership 均可读取其 scope 内资源。本阶段不建设通用权限矩阵。

### 3.3 临时 actor context

- 受保护路由集中解析 `X-Actor-Subject`、`X-Organization-Id` 与 `X-Workspace-Id`；bootstrap Organization 只需 actor subject。
- 路径 tenant 与 header tenant 必须一致，并再次验证 Organization、Workspace 与 active Membership 关系。
- 仅 `local`、`test`、`ci` 环境允许临时 header；其他环境启动或请求时拒绝该机制。
- header 是测试/开发上下文注入，不是认证。不可访问和不存在资源统一返回不泄露存在性的 404。

### 3.4 事务、审计与并发

- repository 只 `flush`，不自行 `commit`；application use case 通过一个同步 Unit of Work 控制 Session 事务。
- 领域变更与对应 AuditEvent 在同一事务中提交或回滚。
- AuditEvent 只提供 append 与 tenant-scoped read，不提供 update/delete；它不是 event sourcing 或领域真相来源。
- Project PATCH、activate、archive 都必须提供 `expected_version`。数据库更新包含 tenant 条件与 `version = expected_version`，成功时只递增一次；stale version 返回 409 且不写成功审计事件。

## 4. 最小 Schema 与数据库约束

所有主键由应用生成 UUIDv4；时间使用 timezone-aware UTC 与 PostgreSQL `timestamptz`；版本从 1 开始。

| 表              | 关键约束                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------- |
| `organizations` | 全局唯一 slug；status 为 active/suspended/archived；version ≥ 1                                   |
| `workspaces`    | `(organization_id, slug)` 唯一；复合 tenant key；status 受约束                                    |
| `memberships`   | scope/role CHECK；复合 Workspace 外键；Organization-wide 与 Workspace-scoped 唯一 membership 索引 |
| `projects`      | 复合 Workspace 外键阻止跨 Organization 引用；status 为 draft/active/archived；version ≥ 1         |
| `audit_events`  | tenant ownership 非空；payload 使用 JSONB；应用层只追加；Project 审计按 tenant 与 aggregate 查询  |

Project 生命周期仅允许 `draft → active`、`draft → archived`、`active → archived`；archived 为本阶段终态。数据库 CHECK 保证状态集合，领域层保证转换关系。

## 5. API 与错误边界

实现任务列出的 Organization、Workspace、Membership、Project 与 Project audit endpoints，不添加 delete、generic status mutation 或 Brief 路由。数据库 model 不直接作为响应。

所有错误使用稳定 code/message/correlation ID 结构：无效语义 400，不可访问资源 404，slug、生命周期或并发冲突 409，未处理错误 500。数据库异常在 infrastructure/application 边界映射，不返回 SQL、约束名、凭据或堆栈。

请求 correlation ID 由中间件验证或生成，写入响应、结构化日志与同事务 AuditEvent。PATCH 只允许 name、description 与 expected_version，状态只能通过显式 activate/archive use case 改变。

## 6. 直接依赖提案

只新增以下 Python 运行依赖；不新增 JavaScript 或开发测试框架依赖：

| 直接依赖                  | 分类            | 必要性                                                                | 为什么现有工具不足                                                               |
| ------------------------- | --------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `sqlalchemy>=2.0,<3`      | Runtime         | typed ORM mapping、同步 Session、复合约束、显式事务与 repository 实现 | 标准库和当前 FastAPI/Pydantic 不提供 PostgreSQL persistence/session/identity map |
| `alembic>=1.15,<2`        | Runtime/tooling | deterministic、reviewable、可升降级 migration history                 | SQLAlchemy 不管理 schema 历史；手写无版本 SQL 无法可靠检测 head 与回滚           |
| `psycopg[binary]>=3.2,<4` | Runtime         | SQLAlchemy 的 PostgreSQL 3 driver，支持 Python 3.13、本地与 CI        | 标准库没有 PostgreSQL protocol；binary extra 避免要求全局 libpq/compiler         |

`psycopg[binary]` 会由 uv 锁定其平台二进制传递包；不再加入第二个 driver。精确解析版本写入 `uv.lock`。如解析需要任何新的直接依赖，立即暂停并重新申请批准。

## 7. 分阶段执行

### Milestone A — 审查、计划、ADR 与审批

- [x] 检查完整仓库、分支、干净状态与近期提交。
- [x] 阅读治理、产品、架构、ADR、工程计划、工具链、现有组件、测试和配置。
- [x] 识别阶段冲突与追加式治理更新方案。
- [x] 选择最小同步 PostgreSQL persistence 方向。
- [x] 新增本计划和 ADR-012 至 ADR-016 提案。
- [x] 获得三项直接依赖及官方 PyPI 网络访问批准。
- [x] 获得本地 Docker 与固定 `postgres:17-alpine` image 的批准。

### Milestone B — 配置、迁移与数据库基础

- [x] 接受 ADR 并更新当前阶段说明。
- [x] 增加验证/脱敏的 DATABASE_URL 与 pool 配置；禁止 SQLite fallback。
- [x] 配置 SQLAlchemy engine/session、Alembic 与初始 migration。
- [x] 增加可选的最小 PostgreSQL 17 Docker 定义和原生 PostgreSQL 文档。
- [x] 验证空数据库 upgrade、current/head、check 与安全 downgrade。

### Milestone C — 领域、repository、UoW 与审计

- [x] 实现无框架依赖的 Project lifecycle/domain errors。
- [x] 定义 tenant context、repository protocols 与同步 Unit of Work。
- [x] 实现五类 SQLAlchemy repositories、数据库约束与原子 audit append。
- [x] 添加领域、repository、rollback 与 audit 测试。

### Milestone D — 请求上下文、use case 与 API

- [x] 实现集中且非生产的 header context injection。
- [x] 实现最小 use cases、权限检查、opaque 404、409 concurrency 与安全错误映射。
- [x] 增加明确 request/response schemas、routes 与 correlation ID。
- [x] 保持 Web 与 Worker 不增加产品功能或持久任务。

### Milestone E — 隔离证明、CI 与文档闭环

- [x] 添加真实 PostgreSQL tenant、事务、并发、migration 与 API tests。
- [x] CI 增加固定 PostgreSQL 17 service、health check 与 migration gate，不改 `npm ci`/`uv.lock`。
- [x] 扩展 Makefile 的最小 db/test commands，并让 `make check` 包含数据库相关 gate。
- [x] 更新 README、环境示例、架构/安全/测试/本地设置文档和本计划状态。
- [x] 执行完整格式、lint、typecheck、tests、migration、build 与 scope/security diff review。

## 8. 实际结果与偏差

- `uv.lock` 最终锁定 SQLAlchemy `2.0.51`、Alembic `1.18.5`、psycopg/psycopg-binary `3.3.4`；没有新增未批准的直接依赖。
- 初始 migration revision 为 `fca964a30853`。本地 PostgreSQL 17 已完成 upgrade、head/check、downgrade、再次 upgrade 与 autogenerate drift 检查。
- 分层 PostgreSQL 验证覆盖领域、repository、复合外键、部分唯一索引、tenant 隔离、原子 rollback、并发冲突、API 错误映射与 header 环境限制。
- `db-reset-test` 已验证拒绝非 `_test` 数据库，并在允许的测试库上重置后重新通过测试。
- CI workflow 已定义 PostgreSQL 17 service、migration gate 与完整 `make check`，但本轮没有权限触发远程 GitHub Actions；本地使用同版本镜像验证等价路径。
- 没有实现认证、Brief、AI/Provider、产品 UI、队列或云集成；Web 与 Worker 的既有 foundation 行为未扩展。

## 9. 测试与安全验证

真实 PostgreSQL tests 覆盖：slug/复合外键约束、tenant-scoped repository、跨 tenant 读写隐藏、membership bypass、Organization/Workspace mismatch、Project IDOR、原子 audit rollback、stale version、准确 version increment、迁移 head 与安全错误。

测试数据库必须显式配置且名称以 `_test` 结尾；任何清理 helper 在名称不匹配时拒绝执行。测试不依赖顺序，不使用真实客户数据或凭据。CI 使用固定测试账号与 ephemeral service，不使用 secrets。

## 10. 已知限制与复审触发

- 临时 headers 可被调用者伪造，绝不允许进入生产；真实共享环境前必须增加 auth Adapter 与威胁模型。
- 本阶段在应用 repository/use case 层实施 tenant isolation，不启用 PostgreSQL RLS。首次共享生产或受监管数据前复审 RLS/物理隔离。
- 同步 Session 是可替换假设。只有请求并发/延迟指标连续两个周期证明阻塞，才评估 async persistence。
- `psycopg[binary]` 适合当前开发与 CI；生产镜像、安全或平台政策要求源码/libpq 构建时复审 packaging。
- Audit append-only 由应用接口与测试保证，不是数据库账户级不可变存储；出现合规不可抵赖要求时新增 ADR。
