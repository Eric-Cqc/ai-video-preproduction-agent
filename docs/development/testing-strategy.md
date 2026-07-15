# 测试策略

测试按风险分层：纯 domain tests 验证 Project 状态机与版本；真实 PostgreSQL tests 验证 repository、复合外键、部分唯一索引、事务回滚和 migration head；API tests 验证临时 context、membership、opaque 404、mass assignment、并发 409、安全错误与 audit scope；既有 Vitest/pytest 继续验证 Web、health contract、Worker 和 model registry。

Persistence tests 使用独立 `_test` database，不使用 mock repository 代替 tenant isolation，不依赖执行顺序。fixture 在每个相关测试前后只截断五张业务表。CI 从空 PostgreSQL 17 service 应用 migration，然后执行同一套 gate。

## 根命令

- `make test-domain`：无数据库领域规则。
- `make test-persistence`：PostgreSQL repository、migration、transaction 与 API isolation。
- `make test-integration`：跨组件 contract 与 tenant API。
- `make check`：migration head/drift、格式、lint、strict types、全部测试、contract 与 build。

## 冻结决定

关键测试必须断言 tenant 隔离、版本/审计原子性和结构化领域状态，而不是 Prompt 文本。任何跨 tenant 泄露、stale overwrite、无审计成功 mutation 或 migration drift 都是阻塞失败。

## 可替换假设与复审触发

测试数据库 fixture 和 CI service 细节可替换。出现并行测试需求时可评估 per-schema/per-database isolation；不得因此换用 SQLite。浏览器自动化仍延后到首个真实产品 UI。
