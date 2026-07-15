# ADR-016：不可变 AuditEvent 基础

- 状态：已接受（第三阶段；实现可替换）
- 关联：[ADR-006](ADR-006-versioning-and-audit.md)、[可观测性计划](../architecture/observability-plan.md)、[执行计划](../development/plans/tenant-persistence-foundation-plan.md)

## 决定

关键 domain mutation 在 PostgreSQL `audit_events` 表追加事件。事件包含应用生成 UUID、Organization/Workspace ownership、actor subject、aggregate type/ID、受控 action、JSONB metadata、UTC occurred_at、correlation ID 与可选 causation ID。

Audit repository 只公开 append 与 tenant-scoped read，不公开 update/delete。Project audit endpoint 只返回指定 tenant 与 Project 的事件。本阶段不实现 global audit search、event sourcing、消息总线或 analytics。

Audit payload 只记录最小结构化 metadata，例如 changed fields、from/to status 与 aggregate version；不得包含 secret、数据库 URL、原始客户素材、Prompt 正文或 Provider response。

## 原因

append-only mutation evidence 落实 ADR-006，并能验证 Project mutation、actor、version 与请求 correlation。它与当前 canonical state 同事务写入，但不替代 Project 表。

## 后果

- 成功 mutation 与事件同事务提交；任何一方失败则全部回滚。
- failed validation、authorization 或 stale concurrency 不写成功 mutation event。
- 应用测试保护 append-only API；本阶段不声称数据库管理员级不可篡改。

## 冻结决定

审计不是领域真相来源；成功关键 mutation 不得缺失对应事件；审计读取必须 tenant-scoped，payload 必须最小化且无 secret。

## 可替换假设与复审触发

保留期限、数据库级防篡改、归档、查询工具和 action taxonomy 可替换。出现合规不可抵赖、外部审计导出或高容量保留要求时，以新 ADR 评估数据库权限、WORM storage 或归档；不得把本表演变成 event sourcing。
