# 可观测性计划

API 为每个请求接受受限 `X-Correlation-Id` 或生成 UUID，并在响应、结构化错误、日志和成功 mutation AuditEvent 中传播。结构化日志固定包含 service、version、environment、event、timestamp、level，并在可用时包含 correlation ID 与 tenant identifiers。

AuditEvent 是产品级 mutation evidence：记录 actor subject、tenant、aggregate、action、version/status metadata 与 occurred_at；不记录数据库 URL、secret、Prompt、素材、请求正文或 Provider response。failed authorization、validation、stale concurrency 和 rollback 不写成功事件。

Ingestion accepted audit 只记录 ingestion ID、operation、schema/source type、Brief version、issue count 和 aggregate version；不记录 key、digest、source reference 或 Structured Brief 正文。replay 不追加 audit。

SourceAsset audit 只记录 asset ID、version number、media type、声明 byte size、aggregate version 和同 Project duplicate count；不记录 checksum、filename、source reference、external record ID、request digest 或 idempotency key。带 attachment 的 accepted Brief ingestion 额外记录一个有界 `brief_ingestion.source_attached` 摘要（ingestion ID、数量、relation type counts、distinct version count），不记录文件名、checksum、provenance 或完整 attachment ID 列表。attachment replay 不追加 audit。

Worker self-check 保持零 handler 与结构化启动信息。没有 hosted logging、OpenTelemetry、production analytics 或全局 audit search。

## 冻结决定

版本与审计必须能关联关键 mutation；日志不替代 AuditEvent，AuditEvent 不替代 canonical domain state。

## 可替换假设与复审触发

指标、追踪、日志保留与 hosted tooling 尚未选择。首次生产试点前定义 SLO、脱敏、访问权限与保留策略；发生跨 tenant 事件或无法定位一次关键 mutation 时立即复审。
