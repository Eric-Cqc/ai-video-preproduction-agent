# 扩展策略

先稳定领域语言和结构化 Schema，再扩展入口、Provider 与导出。新增能力须落入既有模块，或以 ADR 说明新模块的独立不变量、数据所有权和公开契约。

## 冻结决定

- Provider 接入采用 Adapter：领域代码依赖能力契约，不依赖某模型、存储或身份 SDK（[ADR-005](../adr/ADR-005-provider-adapters.md)）。
- Schema、导出与跨语言契约显式版本化；旧版本保留可读/可迁移路径（[ADR-004](../adr/ADR-004-structured-video-production-schema.md)、[ADR-009](../adr/ADR-009-cross-language-contracts.md)）。
- Prompt 可版本化以提升可复现性，但永远附属于一次建议或 Job，不能取代结构化实体。

## 可替换假设与复审触发

插件机制、事件总线和 Provider 数量尚未决定。当第二个已批准 Provider 或第二种外部导出需要相同扩展点时，定义最小公共 Adapter 契约；此前不建设通用插件平台。
