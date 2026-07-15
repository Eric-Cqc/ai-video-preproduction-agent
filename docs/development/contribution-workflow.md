# 贡献流程

1. 阅读 `FOUNDATION.md`、项目级 `AGENTS.md`、受影响的架构文档与 ADR。
2. 将改动限定为一个可审查意图；不得顺带引入依赖、基础设施、Brief、AI、认证或云能力。
3. Schema 变更必须更新 SQLAlchemy metadata、追加 Alembic revision，并审查 upgrade/downgrade、tenant ownership、约束和索引。
4. Project/Brief/SourceAsset mutation 必须携带 tenant scope、expected version（适用时），并与最小 AuditEvent 在一个 UoW 中提交。Ingestion 与 SourceAsset operation 必须先 PostgreSQL reservation，再受限 finalize；不得提交长期 `reserved`。SourceAssetVersion 插入后不可编辑；Brief attachment 只能在 accepted ingestion 条件插入后同一 transaction 写入。
5. 运行相关分层测试与 `make check`，检查 migration drift、锁文件、生成物、secret、IDOR 和 scope creep。
6. 交付时说明变更、验证、假设与未解决项；不提交数据库凭据、文件字节或客户数据。不得把声明 checksum/size 表述为已验证的文件事实。

所有 JavaScript 子命令由 Makefile 转交 `scripts/run-with-node.sh`。ADR 采用追加历史，已接受决定不被静默重写。

## 复审触发条件

当团队规模、合规要求、数据库 migration 协作或发布频率使现有流程不足时，记录证据并以新 ADR 更新。
