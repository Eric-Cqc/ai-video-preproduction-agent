# ADR-005：Provider Adapters

- 状态：已接受（冻结）
- 决定：模型、存储、身份和导出 Provider 通过服务端 Adapter 契约接入。
- 原因：隔离供应商变化、凭据与数据策略，避免领域代码锁定 SDK。
- 后果：Adapter 负责转换、错误分类和策略执行；领域模块不导入 Provider SDK。
- 可替换假设：Provider、SDK 与每类能力的契约形状。
- 复审：第二个已批准 Provider 证明现有契约无法承载共同能力时，以新 ADR 演进契约。
