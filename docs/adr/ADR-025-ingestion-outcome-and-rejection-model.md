# ADR-025：Ingestion Outcome 与 Rejection Boundary

- 状态：已接受（第五阶段）
- 关联：ADR-013、ADR-016、ADR-022

## 决定

`BriefIngestion` 有 `reserved`、`accepted` 或 bounded `rejected` 状态。`reserved` 只在 winner transaction 内、或并发 loser 等待该 transaction 的极短窗口出现，绝不作为 API 成功 outcome；rollback 必须删除它。当前仅持久化 accepted domain ingestion；在 tenant authorization、header/key、body size、canonical validation或 provenance validation 失败时直接返回安全错误，不保留 payload、原始 validation errors 或 rejection record。accepted 必须关联 Brief 与 BriefVersion，completed_at 非空。

读取必须带 Organization、Workspace、Project、ingestion ID 全部 scope，不存在与不可访问统一 404。

## 冻结决定

不得持久化完整 invalid payload、raw exception、headers、credentials 或 SQL diagnostics。

## 可替换假设与复审触发

有合规需求时，才以 ADR 定义加密、最小 rejection retention 和访问策略。
