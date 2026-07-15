# ADR-019：Brief review、approval 与 requirement issues

- 状态：已接受（第四阶段；领域决定）
- 关联：[ADR-006](ADR-006-versioning-and-audit.md)、[ADR-017](ADR-017-brief-aggregate-and-immutable-versions.md)、[执行计划](../development/plans/versioned-brief-foundation-plan.md)

## 决定

current draft 可显式 submit 为 in_review；只有 owner/admin 可 approve 或 archive，member 可 create version、submit 及管理 issues，viewer 只读。approval 必须同时满足：current version 为 in_review、无 open blocking issue、expected Brief version/current version 匹配、Project 可访问且未 archived。

RequirementIssue 是 BriefVersion 下的有界实体，类型为 missing/ambiguous/conflicting/invalid/compliance_risk，severity 为 blocking/warning/informational，状态为 open/resolved/dismissed。issue 由请求显式创建，或由文档列出的六项 deterministic checks 创建；不进行 AI 推断。

resolve/dismiss 使用显式动作、resolution note、issue version CAS 和 Brief aggregate CAS。Issue 只可在 draft/in_review aggregate 上变更；批准后必须先创建新 draft version，不能追改批准证据。这样并发 issue mutation 会使 stale approval 失败，而不能在 blocker check 后绕过 approval policy。

## 冻结决定

approval 是显式且可审计的状态转换；open blocking issue 不得被绕过；批准 snapshot 内容保持不可变。

## 可替换假设与复审触发

角色名称、issue taxonomy 与 member issue 权限可替换。真实审批层级在至少三个项目中证明当前规则不足时，以新 ADR 评估，不引入通用 workflow/policy engine。
