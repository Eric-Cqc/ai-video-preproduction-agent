# ADR-018：Structured Video Brief Schema 与扩展边界

- 状态：已接受（第四阶段；契约决定）
- 关联：[ADR-004](ADR-004-structured-video-production-schema.md)、[ADR-009](ADR-009-cross-language-contracts.md)、[执行计划](../development/plans/versioned-brief-foundation-plan.md)

## 决定

`packages/contracts` 中 versioned JSON Schema 是 Structured Brief 的唯一权威契约。v1 面向 15–60 秒商业/社交视频，覆盖 objective、audience、offer、product、brand、channels、deliverables、creative/production constraints、legal/compliance、references、success criteria 与 open questions。

所有对象拒绝未知字段，字符串、数组、数量、深度与时长均有界；不存在任意 extension map、Prompt、Provider 参数、文件路径或上传对象。Python jsonschema 与 TypeScript Ajv 使用同一 schema 和 fixtures。PostgreSQL 只保存验证后的 JSONB，SQLAlchemy model 不成为契约来源。

结构合法性不等于业务完整性：允许关键值为空，以便显式记录缺失，然后由有限 deterministic checks 生成 RequirementIssue。

## 冻结决定

跨语言消费者必须验证同一 canonical schema；破坏性变化新增 schema 文件与迁移策略，不静默覆盖 v1；Prompt 不是 Brief 数据模型。

## 可替换假设与复审触发

JSON Schema draft、字段细节和序列化工具可替换。两个消费者无法可靠维护当前格式，或两个真实用户群需要不兼容核心结构时，以新 ADR/version 复审。
