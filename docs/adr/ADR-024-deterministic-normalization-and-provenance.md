# ADR-024：确定性规范化、Digest 与 Provenance

- 状态：已接受（第五阶段）
- 关联：ADR-018、ADR-021、ADR-022

## 决定

先用 Structured Brief v1 验证，再用 UTF-8、sorted object keys、固定 JSON separators 和保留 array order 的序列化计算 SHA-256。无 schema default insertion、大小写改写、业务字符串 trim 或 array reorder。digest 只用于 idempotency 比较，不暴露给客户端、AuditEvent 或 rejection。

source reference 为至多 200 字符的 opaque identifier，拒绝路径、URL、凭据和 header。BriefVersion 保存已验证 canonical content；BriefIngestion 不重复保存 content。

## 冻结决定

不得静默改变结构化内容语义，AuditEvent 不包含正文、digest 或 source reference。

## 可替换假设与复审触发

schema 明确要求的 defaults 才可通过 ADR 加入。schema v2 或签名 provenance 需求须另行设计。
