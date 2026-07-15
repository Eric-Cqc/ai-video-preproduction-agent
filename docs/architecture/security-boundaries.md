# 安全边界

信任边界包括浏览器/API、API/PostgreSQL、未来 Worker/Provider，以及 Organization/Workspace tenant 之间。所有 Project route 在服务端验证 actor、path/header Organization、Workspace ownership、active Membership 与 operation role；Project ID 单独永远不足以授权。

## 临时身份限制

`X-Actor-Subject`、`X-Organization-Id`、`X-Workspace-Id` 只是 local/test/ci context injection，不是认证。配置属性与请求 middleware/dependency 双重限制允许环境；其他环境即使收到 header 也返回 403，不静默接受。该机制可伪造，不能部署到共享生产。

## 数据与错误边界

- Organization/Workspace mismatch 由 scoped query 和复合外键共同阻止。
- inaccessible 与 nonexistent tenant resources 统一 opaque 404，降低 IDOR 枚举。
- PATCH 禁止 status/未知字段；生命周期只走 activate/archive；stale version 返回 409。
- SQLAlchemy repository 不 commit；domain mutation 与 AuditEvent 同 UoW 原子提交。
- DATABASE_URL 不写日志，诊断表示隐藏 password；错误不返回 SQL、约束名或堆栈。
- Audit payload 仅含 changed fields/status/version，不含 secret、Prompt、素材或 Provider response。
- CORS 仍使用显式 origin/method/header，不允许 wildcard credentials。

## 冻结决定

Provider secret 只允许未来受控服务端；每个持久化查询和审计读取必须 tenant-scoped；浏览器不得直连 Provider。

## 已知风险与复审触发

本阶段主要在应用层隔离，未启用 PostgreSQL RLS；数据库管理员也能修改 audit table。首次共享生产、外部协作者或受监管数据前，必须新增 auth Adapter、威胁模型，并复审 RLS、数据库角色、凭据轮换、备份恢复、审计防篡改和保留策略。
