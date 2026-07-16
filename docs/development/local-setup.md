# 本地设置

需要 Node 24.18.0、npm 11、Python 3.13、uv、GNU Make、Bash 和 PostgreSQL 17。先运行 `make setup` 并复制 `.env.example`。

## PostgreSQL 选择

原生 PostgreSQL：创建 `foundation_local`、`foundation_test` 及最小权限本地用户，设置 `DATABASE_URL`/`TEST_DATABASE_URL` 后执行 `make db-upgrade`。

可选 Docker：`make db-up` 只启动官方 `postgres:17-alpine`，绑定 `127.0.0.1:54329`，并创建 repository-scoped network/volume；随后运行 `make db-upgrade`。`make db-down` 不删除 volume，也不影响其他 Compose project。

## Migration

- `make db-upgrade`：升级到 head。
- `make db-current`：确认当前为所有 head。
- `make db-check`：确认数据库在 head 且 SQLAlchemy metadata 无未迁移变化。
- `make db-downgrade`：显式回退一个 revision，仅用于已确认安全的本地/测试数据库。

修改 metadata 后使用 Alembic autogenerate 创建 revision，审查所有约束、部分索引、upgrade 和 downgrade，再运行 upgrade/check。不得修改已经共享或应用的 migration 来重写历史。

当前 head 还包含 SourceAsset、Brief ingestion attachment、SourceObject/upload、DocumentExtraction 和 extraction reservation 约束。`SOURCE_OBJECT_STORAGE_ROOT` 默认 `.local/source-objects` 并被 Git 忽略；local filesystem adapter 仅允许 local/test/ci。Docker PostgreSQL 仍只是可选数据库路径，不是对象存储或唯一开发路径。

## 安全重置测试数据

`make db-reset-test` 只读取 `TEST_DATABASE_URL`，并在 database 名不以 `_test` 结尾时拒绝执行。它只截断当前九张业务表，不删除 database、migration metadata、volume 或其他项目资源。普通 `make check` 不执行 reset。

完整命令和环境变量见根 README。没有 SQLite fallback、云数据库、Supabase、云对象存储或外部 Provider。

`DATABASE_STATEMENT_TIMEOUT_MS` 默认 5000，应用到 PostgreSQL session，限制包括 idempotency unique-key wait 在内的单条 SQL；超时使当前 UoW rollback，不改变健康检查语义。

## 复审触发条件

首次共享生产环境前必须替换临时 headers、完成 auth Adapter/威胁建模，并复审 RLS、数据库角色、备份、恢复和凭据管理。
