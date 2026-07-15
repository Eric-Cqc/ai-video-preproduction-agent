# ADR-021：Brief audit 与 provenance 边界

- 状态：已接受（第四阶段；审计决定）
- 关联：[ADR-016](ADR-016-immutable-audit-events.md)、[ADR-017](ADR-017-brief-aggregate-and-immutable-versions.md)、[执行计划](../development/plans/versioned-brief-foundation-plan.md)

## 决定

BriefVersion provenance 只记录 source type（manual/imported_structured）、可选有界 opaque source reference、creator、supersedes version、change summary 和 content schema version。不保存文件、路径、抓取内容、request headers、credentials 或数据库 URL。

Brief 与 issue 成功 mutations 追加受控 AuditEvent action。payload 只含 aggregate version、version number、schema version、issue counts、changed section names 或 prior/new state，不复制 Structured Brief content。

Audit append 与 aggregate/version/issue mutation 由同一 UoW transaction 提交或回滚。只增加 tenant-scoped Brief audit read，不建设 global search、event sourcing、analytics 或消息总线。

## 冻结决定

成功关键 mutation 必须有最小 audit；audit 不得泄露 Brief 正文或敏感来源；provenance 不等于原始文件存储。

## 可替换假设与复审触发

source taxonomy、保留期和审计查询形式可替换。出现真实导入管道、合规不可抵赖或外部审计导出要求时，以新 ADR 设计 storage/Job/retention，不扩张当前字段承载原始输入。
