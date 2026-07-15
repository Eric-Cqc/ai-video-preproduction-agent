# 测试策略

测试按风险分层：纯 domain tests 验证 Project/Brief 状态机、版本与有限 deterministic issue checks；真实 PostgreSQL tests 验证 repository、复合外键、部分唯一索引、事务回滚、Brief CAS 和 migration head；API tests 验证临时 context、membership、opaque 404、mass assignment、不可变 snapshot、审批 blocker、并发 409、安全错误与 audit scope；既有 Vitest/pytest 继续验证 Web、health/Structured Brief contract、Worker 和 model registry。

Persistence tests 使用独立 `_test` database，不使用 mock repository 代替 tenant isolation，不依赖执行顺序。fixture 在每个相关测试前后截断当前十四张业务表。CI 从空 PostgreSQL 17 service 应用 migration，然后执行同一套 gate。

Ingestion tests 使用两个独立 PostgreSQL Session 与 Event/Barrier（不使用 sleep）验证 winner commit/replay、winner rollback/loser 接管、different digest 409、无永久 `reserved`，并覆盖 Issue、finalize、Audit 与 stale CAS rollback。

SourceAsset tests 使用真实 PostgreSQL 约束覆盖 immutable Version ownership、accepted outcome、scoped operation uniqueness、cross-tenant/Project composite FK 和 attachment position/relation constraints。并发 tests 用独立 session 与 Barrier/Event、明确 timeout（不用 sleep）验证 create/version 同 key 只有一个 mutation/audit、rollback 后新的 reservation 可取得，以及无永久 `reserved`。API tests 覆盖 opaque IDOR、role、pagination、provenance/filename/checksum/size 边界和不泄露 operation internal fields。

## 根命令

- `make test-domain`：无数据库领域规则。
- `make test-persistence`：PostgreSQL repository、migration、transaction 与 API isolation。
- `make test-integration`：跨组件 contract 与 tenant API。
- `make check`：migration head/drift、格式、lint、strict types、全部测试、contract 与 build。

## 冻结决定

关键测试必须断言 tenant 隔离、版本/审计原子性和结构化领域状态，而不是 Prompt 文本。任何跨 tenant 泄露、stale overwrite、无审计成功 mutation 或 migration drift 都是阻塞失败。

## 可替换假设与复审触发

测试数据库 fixture 和 CI service 细节可替换。出现并行测试需求时可评估 per-schema/per-database isolation；不得因此换用 SQLite。浏览器自动化仍延后到首个真实产品 UI。
