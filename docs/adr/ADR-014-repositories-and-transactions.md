# ADR-014：Repository 与事务边界

- 状态：已接受（第三阶段；实现可替换）
- 关联：[ADR-001](ADR-001-modular-monolith.md)、[ADR-006](ADR-006-versioning-and-audit.md)、[执行计划](../development/plans/tenant-persistence-foundation-plan.md)

## 决定

API 模块内部按必要职责分为 domain、application、infrastructure 与 presentation；不建设通用 clean-architecture framework。

domain 定义无 SQLAlchemy 依赖的 Project lifecycle 与错误；application 定义 Organization、Workspace、Membership、Project、Audit repositories 的小型 Protocol 及 use cases；infrastructure 提供 SQLAlchemy 实现；presentation 负责 FastAPI schemas、tenant context 与错误映射。

Repository 方法必须接受 tenant context，例如 `get_project(organization_id, workspace_id, project_id)`；不提供无 scope 的 `get_project_by_id(project_id)`。Repository 可 `flush` 以获得约束结果，但不得自行 `commit`。

每个 mutation use case 由同步 Unit of Work/Session transaction 包围。领域 mutation 与 AuditEvent 必须在同一事务中全部提交或全部回滚。

## 原因

显式 repository 能防止 route 直接拼接不带 tenant 的查询；单一事务所有者使 audit 原子性、rollback tests 和 solo developer 调试保持清晰。当前不需要外部 repository/UoW package。

## 后果

- HTTP route 不直接访问 SQLAlchemy model 或 Session。
- 数据库 model 不作为 API response 返回。
- 唯一约束和并发错误在 infrastructure/application 边界转为稳定 domain/API errors。
- 测试可分别覆盖纯 domain 与真实 PostgreSQL repository/transaction 行为。

## 冻结决定

业务 mutation 和成功审计必须原子；repository 查询必须显式 tenant-scoped；任意 repository 自行 commit 属于违规。

## 可替换假设与复审触发

目录名称、Protocol 形状和 Session factory 细节可替换。只有多个 use case 重复事务样板造成可量化维护问题时，才评估更通用的 UoW abstraction；不得引入分布式事务。
