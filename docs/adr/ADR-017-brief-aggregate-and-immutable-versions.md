# ADR-017：Brief aggregate 与不可变版本

- 状态：已接受（第四阶段；领域决定）
- 关联：[ADR-004](ADR-004-structured-video-production-schema.md)、[ADR-006](ADR-006-versioning-and-audit.md)、[执行计划](../development/plans/versioned-brief-foundation-plan.md)

## 决定

Brief 是附属于一个 tenant-scoped Project 的稳定 aggregate identity；BriefVersion 是完整结构化内容的不可变 snapshot。每次 material content change 都创建新 BriefVersion，不提供内容原地 PATCH。

Brief 保存 current version pointer、latest version number、aggregate status 和乐观并发 version。BriefVersion number 由服务端单调分配，客户端不能指定。新版本以 `supersedes_version_id` 关联上一 current version；旧 draft/in_review Version 可标记为 superseded，已批准 Version 保持 `approved` 且所有字段完全不变。

Brief 状态只表达 `draft`、`in_review`、`approved`、`archived`，不混入 concept、storyboard、prompt、generation 或 production 状态。

## 原因与后果

稳定 identity 支撑引用与权限，不可变 snapshot 落实版本历史、批准证据和无静默覆盖原则。代价是每次内容变化写完整 JSONB snapshot；当前 schema 和内容上限使该成本可接受。

## 冻结决定

批准内容不得原地修改或后续 transition；新内容不得覆盖历史；Brief/Version 必须继承 Project tenant path。

## 可替换假设与复审触发

状态名称、snapshot 存储形式和 UUID 版本可替换。真实内容规模连续两个周期证明完整 snapshot 成本不可接受时，以新 ADR 评估结构化 delta，但仍须保持可重建、可审查历史。
