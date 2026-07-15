# 安全边界

信任边界包括：浏览器与服务端、服务端与 Worker、系统与外部 Provider、以及 tenant 与 tenant 之间。所有请求在服务端完成身份验证、授权、tenant 解析、输入校验和审计；Worker 继承最小化的受限执行上下文。

## 冻结决定

- Provider 密钥仅位于受控服务端/Worker 环境，绝不发送到浏览器或提交到仓库。
- 每个业务对象、Job、审计记录和未来持久化查询均带 tenant 语义（[ADR-008](../adr/ADR-008-tenant-aware-foundation.md)）。
- 原始素材、个人数据、密钥和 Provider 原始响应按最小必要原则访问、留存与脱敏日志处理。
- 浏览器不得调用模型或其他 Provider（[ADR-010](../adr/ADR-010-no-browser-provider-calls.md)）。

## 可替换假设与复审触发

身份提供方、密钥保管服务和数据保留时长尚未选定。处理真实客户素材、外部协作者或受监管数据前，必须完成威胁建模、保留策略和访问控制 ADR。
