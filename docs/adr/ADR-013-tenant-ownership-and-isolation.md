# ADR-013：Tenant ownership 与隔离模型

- 状态：已接受（第三阶段；实现可替换）
- 关联：[ADR-008](ADR-008-tenant-aware-foundation.md)、[安全边界](../architecture/security-boundaries.md)、[执行计划](../development/plans/tenant-persistence-foundation-plan.md)

## 决定

tenant hierarchy 为 `Organization → Workspace → Project`。所有 tenant-owned repository 查询必须携带 Organization 与必要的 Workspace context；Project 不能只按 Project ID 查询。

Project、Membership 与 AuditEvent 保存显式 `organization_id`/`workspace_id` ownership。Project 和 workspace-scoped Membership 通过复合外键保证 Workspace 属于相同 Organization。Workspace slug 只在 Organization 内唯一。

Membership scope：Organization-wide membership 的 `workspace_id` 为 null，只允许 owner/admin；Workspace-scoped membership 允许 admin/member/viewer。创建 Organization 时在同一事务中创建初始 Organization owner。

受保护资源采用 opaque 404：不存在与不可访问保持同一外部行为。应用层必须同时验证 actor、membership、Organization、Workspace 与 path/header context；不信任客户端提供的 Workspace ID。

## 临时身份边界

在认证 Provider 尚未接入时，local/test/ci 可使用集中解析的 `X-Actor-Subject`、`X-Organization-Id`、`X-Workspace-Id` 注入开发上下文。bootstrap Organization 只接受 actor subject。该机制不是认证，其他环境拒绝使用。

## 原因

显式 ownership 与复合约束能降低 IDOR、Organization/Workspace mismatch 和后续补 tenant 的迁移风险。Organization-wide owner 使 bootstrap 能在没有默认 Workspace 或伪登录的情况下保持原子、最小。

## 冻结决定

任何 tenant-owned 访问都不能只凭对象 ID；跨 tenant 资源不得泄露存在性；临时 header 绝不代表安全身份认证。

## 可替换假设与复审触发

角色名称、Organization-wide membership、header 名称和应用层隔离实现可替换。首次共享生产、外部协作者或受监管数据前，必须新增 ADR 评估真实 auth Adapter、PostgreSQL RLS、数据库角色和物理隔离。
