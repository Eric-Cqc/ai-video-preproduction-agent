# ADR-022：Controlled Structured Brief Ingestion Boundary

- 状态：已接受（第五阶段）
- 关联：ADR-017、ADR-018、ADR-020、ADR-021

## 决定

新增同步、tenant-aware 的受控入口，只接收已符合 canonical Structured Brief v1 的 JSON，创建 Brief 或不可变 successor BriefVersion。它不是文件、网页、邮件、OCR、LLM 或 Provider 导入能力。

ingestion source 仅为 `imported_structured`、`api_structured`；`manual` 继续属于既有 direct API。所有成功路径复用 Project/Brief scope、角色、CAS、RequirementIssue、UoW 与最小 AuditEvent。

## 冻结决定

未经 schema 验证的 payload 不进入领域或持久化；不增加 parsing、Job、queue、ETL 或 AI abstraction。

## 可替换假设与复审触发

输入 transport 与 source taxonomy 可替换。需要文件、外部抓取或长时处理时，先以 ADR 定义存储、鉴权、Job、retention 与失败模型。
