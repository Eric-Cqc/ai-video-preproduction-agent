# ADR-023：Ingestion Idempotency 与重复处理

- 状态：已接受（第五阶段）
- 关联：ADR-014、ADR-020、ADR-022

## 决定

每个 ingestion mutation 必须有受限 `Idempotency-Key`。唯一 scope 为 Organization、Workspace、Project、operation 与 key；PostgreSQL unique constraint 和 insert-first `reserved` reservation 处理并发。`reserved` 仅为同一同步事务或极短暂并发等待窗口的内部技术状态，不是 API outcome；同 key/digest 的 committed `accepted` 返回原结果，不同 digest 返回 409。

先解析既有 outcome，再只对新 key 判断 Brief CAS，故成功请求在 aggregate 后续前进时仍能重放。replay 不创建新 Version、pointer movement、issues 或 audit。

## 冻结决定

不得使用 in-memory cache、check-then-insert 或 repository commit 作为 duplicate protection。loser 以有界 PostgreSQL row lock/re-read 等待 winner；winner rollback 后 reservation 消失，loser 重新竞争；不无限轮询。

## 可替换假设与复审触发

key 长度和 reservation SQL 可替换。跨进程吞吐证明该唯一索引热点不足时，才以 ADR 评估其他数据库安全策略。
