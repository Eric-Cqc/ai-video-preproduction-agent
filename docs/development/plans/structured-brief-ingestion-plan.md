# Controlled Structured Brief Ingestion Boundary 执行计划

- 计划状态：Milestone A–E 完成；等待最终只读审查，未提交、未推送
- 工作分支：`feat/structured-brief-ingestion`
- 基线：`3f55517`；初始工作树干净，migration head 为 `8d4e2a1f7c90`
- 权威依据：`FOUNDATION.md`、`AGENTS.md`、ADR-001 至 ADR-021、现有 Brief/tenant 边界

## 决策与边界

这是已结构化 JSON 的同步受控入口，不读取文件、不解析、不调用 AI、不创建 Job、队列、Provider 或产品 UI。继续保持模块化单体、同一 UoW 事务、tenant-scoped repository、不可变 BriefVersion 与 canonical Structured Brief v1 schema。

不新增依赖：标准库 `json` 与 `hashlib.sha256` 可完成最小确定性序列化与 digest；现有 `jsonschema`、SQLAlchemy、Alembic、psycopg 和 pytest 已覆盖其他需要。因此不修改 `pyproject.toml` 或 `uv.lock`。

## 已冻结的实施选择

1. idempotency scope 为 `(organization_id, workspace_id, project_id, operation, idempotency_key)`；同 key 在另一 Project 或 operation 独立，不跨 tenant 重放。
2. 只接受 `imported_structured` 与 `api_structured` ingestion source；既有 direct Brief API 保留 `manual`，不经此入口。
3. 先验证 canonical schema，再以 UTF-8、sorted keys、固定 separators、保留 array order 的 JSON 得 SHA-256 digest；不改写业务字符串、不插入 defaults、不重排数组。
4. 仅在可信 tenant、Project 授权和有效 canonical payload 后持久化内部 `reserved` 记录；它在同一 UoW 内受限转为 accepted，rollback 必须删除它。无效 schema/大小/请求 header 不持久化。
5. accepted mutation 写一条 `brief.ingestion_accepted` audit；同 key 同 payload replay 不写 audit；同 key 不同 digest 返回 409。

## 分阶段

### Milestone A — 审查与治理

- [x] 检查完整仓库、分支、干净状态、近期提交、migration head、依赖与锁文件。
- [x] 阅读工程宪法、产品/架构文档、ADR、既有计划、契约、Brief 四层实现、请求限制、CI 与 Makefile。
- [x] 识别唯一治理冲突：旧“第四阶段”描述必须以新增 ADR/当前阶段文字前进，不重写历史 ADR。
- [x] 确认无新依赖。
- [x] 追加 ADR-022 至 ADR-026。

### Milestone B — 模型、规范化与迁移

- [x] 增加 ingestion domain/value model、确定性 normalize/digest helper、SQLAlchemy record 与新 Alembic revision。
- [x] 增加 composite ownership、idempotency uniqueness、reserved/accepted/rejected consistency及安全字段约束。
- [x] 运行格式、静态检查、迁移 upgrade/head/drift 与 downgrade/re-upgrade。

### Milestone C — repository 与事务

- [x] 增加仅 tenant/Project scoped 的 ingestion repository 和 UoW 接线。
- [x] 实现 `INSERT ... ON CONFLICT DO NOTHING RETURNING` reservation 与受限 finalize，不在 repository commit/rollback。
- [x] 以独立 Session/connection 和 statement timeout 验证 PostgreSQL commit/rollback 并发语义。

### Milestone D — application/API

- [x] 实现 create Brief 与 create Version 两种 ingestion use case，复用 CAS、issues 与 audit。
- [x] 增加显式 request/response schema、Idempotency-Key 依赖和 tenant-scoped outcome read。
- [x] 保持 opaque 404、409、replay precedence 以及既有 body-size/header 限制。

### Milestone E — 证明与文档

- [x] 完成 API、tenant、concurrency、rollback、migration、normalization tests。
- [x] 更新 README、阶段/架构/安全/测试/本地/迁移文档；CI 保持 PostgreSQL 17 与完整 `make check`。
- [x] 运行 `make db-up`, migration gates, `make check`, `git diff --check` 和 scope/security review。

## 已知限制与复审触发

本阶段没有持久化 rejected payload、文件/URL retrieval、异步重试或真实身份认证。首次需要文件解析、长时导入、外部来源抓取、共享生产身份或 schema v2 时，必须先新增 ADR，不能将其塞进当前同步入口。
