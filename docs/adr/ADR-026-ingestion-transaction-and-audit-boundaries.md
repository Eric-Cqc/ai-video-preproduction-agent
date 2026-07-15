# ADR-026：Ingestion Transaction 与 Audit 边界

- 状态：已接受（第五阶段）
- 关联：ADR-014、ADR-016、ADR-020、ADR-023

## 决定

`reserved` ingestion、Brief/Version mutation、deterministic issues、pointer CAS、条件式 `finalize_accepted` 和一条 `brief.ingestion_accepted` audit 必须在同一 Unit of Work transaction 提交或回滚。失败不会留下 reservation、accepted ingestion 或业务 mutation；replay 只读取原结果，不写 audit。

## 冻结决定

repository 只能 flush，UoW 是唯一 commit/rollback owner；stale CAS、audit failure 或 constraint failure 必须回滚整笔 mutation。

## 可替换假设与复审触发

未来异步 import 必须以 Job 关联此 transaction，不改变 Brief/Version 的原子真相边界。
