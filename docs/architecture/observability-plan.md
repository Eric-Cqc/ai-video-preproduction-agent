# 可观测性计划

可观测性服务于可追溯的制作决策和可运营的后台任务，而非采集用户内容。未来每个请求/Job 关联 correlation ID、tenant、项目、对象版本、操作者或触发源、Adapter、结果状态与耗时；日志默认不含 Prompt 正文、素材、密钥或个人数据。

## 冻结决定

版本与审计记录是产品能力，Job 生命周期必须可查询、可重试且可关联来源（[ADR-006](../adr/ADR-006-versioning-and-audit.md)、[ADR-007](../adr/ADR-007-background-jobs.md)）。

## 可替换假设与复审触发

当前 skeleton 使用本地 JSON structured logs，固定包含 service、version、environment、event、timestamp 与 level；API 未处理异常只记录错误类型，不向客户端暴露堆栈，普通 health 日志不采集请求正文。Worker self-check 同样输出结构化启动事件与零 handler 就绪状态。

指标、追踪工具与保留期限仍未选定；没有 hosted logging 或 OpenTelemetry 基础设施。在首次生产试点前定义 SLO、correlation ID、告警、脱敏规则和审计访问权限；发生安全事件或无法定位一次关键变更时立即复审。
