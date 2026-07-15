# 领域模块

模块化单体中的模块拥有各自规则与公开契约，避免按技术层或 Provider 切分业务。

| 模块 | 责任 | 不拥有 |
| --- | --- | --- |
| Workspace & Access | tenant、成员、角色与项目访问 | Provider 凭据 |
| Briefing | 简报、目标、约束、参考索引 | 最终成片 |
| Development | 叙事、脚本、场景、镜头、资产计划 | 模型 SDK |
| Review & Approval | 评论、批准状态、决策记录 | 修改其他模块内部数据 |
| Versioning & Audit | 版本、变更来源、操作审计 | 领域规则的替代实现 |
| Jobs | 异步任务状态、重试、幂等关联 | 业务真相来源 |
| Integrations | Adapter、Provider 策略与转换 | 领域对象定义 |
| Export | 已批准蓝图的交接包 | 渲染/发布 |

## 冻结决定

制作蓝图由结构化 Schema 表达；模块通过版本化契约协作（[ADR-001](../adr/ADR-001-modular-monolith.md)、[ADR-004](../adr/ADR-004-structured-video-production-schema.md)、[ADR-009](../adr/ADR-009-cross-language-contracts.md)）。

## 可替换假设与复审触发

模块内部实现和细粒度子域可演进。只有满足工程宪法中的服务拆分证据，才考虑把模块部署为独立服务。
