# 领域模块

模块化单体中的模块拥有各自规则与公开契约，避免按技术层或 Provider 切分业务。

| 模块 | 责任 | 不拥有 |
| --- | --- | --- |
| Workspace & Access | tenant、成员、角色与项目访问 | Provider 凭据 |
| Briefing | 简报、目标、约束、参考索引 | 最终成片 |
| Source Assets | tenant/Project-scoped 声明式来源元数据、不可变版本与 Brief 引用 | 上传、存储、读取或验证文件字节 |
| Development | 叙事、脚本、场景、镜头、资产计划 | 模型 SDK |
| Review & Approval | 评论、批准状态、决策记录 | 修改其他模块内部数据 |
| Versioning & Audit | 版本、变更来源、操作审计 | 领域规则的替代实现 |
| Jobs | 异步任务状态、重试、幂等关联 | 业务真相来源 |
| Integrations | Adapter、Provider 策略与转换 | 领域对象定义 |
| Export | 已批准蓝图的交接包 | 渲染/发布 |

当前 Briefing 模块实现一个 Project 下可有多个 Brief 的稳定 aggregate、完整不可变 BriefVersion snapshot、显式 current pointer 和有界 RequirementIssue。Review & Approval 当前只实现 Brief 的 `draft → in_review → approved` 与 archive 动作；不包含评论、通知或通用工作流引擎。Versioning & Audit 通过同一 UoW 保存 mutation 与 AuditEvent。

Briefing 的 controlled ingestion boundary 只接收已结构化 Structured Brief JSON。它使用 Project-scoped idempotency、稳定 SHA-256 digest 与同步 UoW，不拥有文件、解析、AI、Provider 或 Job。

Storyboard/Shot Plan 模块接收已固定的 ScriptVersion/StoryboardVersion lineage，
持久化不可变结构化制作蓝图，并通过 bounded deterministic offline provider、
严格契约和语义校验生成候选。该模块不生成图片或视频，不执行 Prompt，不拥有
真实 Provider、网络、Job 或 UI。

Source Assets 模块当前只保存 metadata-only identity：`SourceAssetVersion` 插入后不可变，新的声明产生 successor，predecessor 永不修改。SHA-256 和 byte size 只是客户端声明，same-content 检测只在同 tenant、同 Project 返回提示，绝不自动合并。Brief ingestion 可通过一个不可变、有序的 relation 引用 active SourceAssetVersion；relation 顺序进入 ingestion digest，attachment、Brief mutation 与审计共用同一个 UoW transaction。

## 冻结决定

制作蓝图由结构化 Schema 表达；模块通过版本化契约协作（[ADR-001](../adr/ADR-001-modular-monolith.md)、[ADR-004](../adr/ADR-004-structured-video-production-schema.md)、[ADR-009](../adr/ADR-009-cross-language-contracts.md)、[ADR-017](../adr/ADR-017-brief-aggregate-and-immutable-versions.md)）。

## 可替换假设与复审触发

模块内部实现和细粒度子域可演进。只有满足工程宪法中的服务拆分证据，才考虑把模块部署为独立服务。
