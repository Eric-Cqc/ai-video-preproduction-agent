# ADR-012：PostgreSQL 持久化与迁移策略

- 状态：已接受（第三阶段；实现可替换）
- 关联：[ADR-001](ADR-001-modular-monolith.md)、[ADR-008](ADR-008-tenant-aware-foundation.md)、[执行计划](../development/plans/tenant-persistence-foundation-plan.md)

## 决定

生产持久化契约采用 PostgreSQL。第三阶段使用同步 SQLAlchemy 2.x、psycopg 3 与 Alembic；不使用 SQLite 替代需要 PostgreSQL 语义的测试。

迁移配置与版本历史提交到 `infra/migrations/`，从空数据库可确定性升级到 head；合理可行时提供 downgrade。CI 使用固定 PostgreSQL 17 service container，先健康检查和升级迁移，再运行 persistence gates。

## 原因

本阶段需要复合外键、部分唯一索引、JSONB、timezone-aware timestamps、事务和并发更新语义。PostgreSQL 能直接表达这些 tenant 不变量。同步 Session 对当前单体和单人维护最清晰；尚无吞吐证据支持 async 数据库层的额外复杂度。

SQLAlchemy 提供 typed mapping 与显式 Session；Alembic提供可审查 schema history；psycopg 是唯一 PostgreSQL driver。`psycopg[binary]` 避免本地和 CI 依赖全局 libpq/compiler。

## 后果

- API 获得一个数据库 engine/session factory，但 repository 与 application use case 控制访问和事务。
- 本地开发可使用原生 PostgreSQL 或可选 Docker；Docker 不是唯一工作流。
- production/test 不允许静默回退 SQLite。
- DATABASE_URL 必须验证且日志脱敏；生产环境必须显式配置。

## 冻结决定

PostgreSQL 是本阶段业务持久化语义的验证目标；migration history 必须提交并在 CI 从空库执行。不得以 mock/SQLite 结果替代 tenant、事务和约束证明。

## 可替换假设与复审触发

SQLAlchemy、Alembic、psycopg binary packaging、PostgreSQL major 和同步 Session 属于可替换假设。出现生产镜像政策要求源码 libpq、两个周期的同步 I/O 指标不达标、或 PostgreSQL major 生命周期要求升级时，以新 ADR 复审；不得改写本记录。
