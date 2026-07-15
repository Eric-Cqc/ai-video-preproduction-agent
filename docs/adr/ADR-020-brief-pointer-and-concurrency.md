# ADR-020：Brief current pointer 与并发模型

- 状态：已接受（第四阶段；持久化决定）
- 关联：[ADR-014](ADR-014-repositories-and-transactions.md)、[ADR-015](ADR-015-project-lifecycle-and-concurrency.md)、[ADR-017](ADR-017-brief-aggregate-and-immutable-versions.md)

## 决定

Brief aggregate `version` 是所有 workflow、issue 与 current pointer mutation 的数据库级 optimistic concurrency token。pointer mutation 同时要求 expected aggregate version 与 expected current version ID。

创建新版本使用单条 tenant/project/brief-scoped `UPDATE ... WHERE version = expected AND current_version_id = expected RETURNING`，原子递增 aggregate version 与 latest version number、分配新 version number 并移动 pointer。随后同事务插入 snapshot、仅 supersede 旧 draft/in_review Version、创建 issues 和 AuditEvent；旧 approved Version 不进入 transition。`(brief_id, version_number)` 唯一约束提供第二道竞争保护。

current pointer 使用 same-Brief 复合外键，并设为 deferrable initially deferred，使非空 pointer 与 Version 1 可在同一事务中创建。stale CAS 无返回行并映射为 409；repository 不 commit，不使用分布式锁。

## 冻结决定

不得仅靠先 SELECT 后 Python 比较保护 pointer/状态；并发失败不得留下 version、pointer、issue 或成功 audit 的部分写入。

## 可替换假设与复审触发

token 类型和 SQL 表达可替换。只有 PostgreSQL 运行指标证明 CAS 热点持续阻塞，才以新 ADR 评估其他并发模型；不得牺牲原子性或历史唯一性。
