# ADR-015：Project 生命周期与乐观并发

- 状态：已接受（第三阶段；实现可替换）
- 关联：[ADR-006](ADR-006-versioning-and-audit.md)、[产品范围](../product/product-scope.md)、[执行计划](../development/plans/tenant-persistence-foundation-plan.md)

## 决定

Project 状态仅为 draft、active、archived。允许转换：

- draft → active
- draft → archived
- active → archived

archived 在本阶段为终态。状态只能通过显式 activate/archive use case 改变，PATCH 不接受 status。

Project 创建时 version 为 1。PATCH 与生命周期转换必须提供 `expected_version`；持久化更新同时约束 Organization、Workspace、Project ID 和当前 version。成功 mutation 更新 `updated_at`、将 version 精确加一并追加审计。版本不匹配返回 409，不覆盖数据，也不写成功审计。

## 原因

该最小状态机只表达 Project 容器生命周期，不混入 Brief、评审、生成或制作状态。乐观并发避免静默覆盖，同时不引入分布式锁。

## 数据完整性

数据库 CHECK 限制状态集合与 version ≥ 1；domain 层限制转换图。UUIDv4 由应用生成，时间为 timezone-aware UTC。

## 冻结决定

不得任意写入 status、绕过 expected version 或在 stale mutation 后产生成功 audit event。

## 可替换假设与复审触发

Project 字段、UUID 版本和 concurrency token 表达可替换。只有真实产品流程证明 Project 容器需要额外生命周期时，才以新 ADR 扩展；Brief/approval 状态不得塞入本状态机。
