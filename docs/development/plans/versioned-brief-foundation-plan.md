# Versioned Brief Foundation 执行计划

- 计划状态：Milestone A–E 已完成；等待人工审查，未提交、未推送
- 工作分支：`feat/versioned-brief-foundation`
- 基线提交：`555369a`（第三阶段已合并，初始工作树干净）
- 目标：在现有模块化单体中建立 tenant-aware、不可变版本的 Brief 领域基础；不实现解析、AI、Provider、Job 或产品 UI
- 权威依据：`FOUNDATION.md`、项目级 `AGENTS.md`、产品与架构文档、ADR-001 至 ADR-016

## 1. 环境与依赖决定

| 能力 | 当前状态 |
| --- | --- |
| Node.js / npm | `.node-version` 固定 `24.18.0`；npm 11；命令经仓库 wrapper |
| Python / uv | Python `3.13.5`；仓库内 `.venv`；`uv.lock` |
| Persistence | PostgreSQL 17、SQLAlchemy 2、Alembic、psycopg 3 |
| Contracts | canonical JSON Schema、Python `jsonschema`、TypeScript Ajv |
| CI | GitHub Actions PostgreSQL 17 service 与 `make check` |

本阶段不新增直接依赖。现有 jsonschema/Ajv 足以承担跨语言契约验证，SQLAlchemy/Alembic/psycopg 足以承担 JSONB、复合外键、延迟约束和原子并发更新。标准库负责确定性 issue checks 与 JSON 大小计算；不引入 rules engine、JSON Patch、深比较、fixture factory、解析器、AI 或云 SDK。因此不存在依赖安装审批等待点，也不修改 lockfile，除非实现中发现无法由现有依赖满足的必要能力；届时立即暂停并重新申请批准。

## 2. 治理冲突与解决

现有治理文档仍描述第三阶段并禁止 Brief，这是阶段性边界，不是永久产品非目标。本任务明确授权第四阶段的结构化 Brief aggregate，但不放宽以下冻结决定：

- 仍为模块化单体，不拆服务、不引入分布式事务。
- canonical Structured Brief Schema 是业务真相；Prompt、聊天或 AI 输出不是核心数据。
- 所有 Brief、Version、Issue 和 Audit 访问必须 tenant-scoped。
- 内容变化不可静默覆盖历史，成功 mutation 与 AuditEvent 必须同事务。
- 浏览器不直连 Provider；本阶段完全没有 Provider、解析、生成或 Job。

以 ADR-017 至 ADR-021 追加决定，不修改 ADR-001 至 ADR-016。Milestone E 只更新现有文档的当前阶段说明与实际行为。

## 3. Canonical Structured Brief v1 提案

`packages/contracts/schemas/structured-brief-v1.schema.json` 是唯一权威契约，`schema_version` 固定为 `1.0.0`，顶层及所有对象默认 `additionalProperties: false`。Python 与 TypeScript 仅提供薄验证包装并共享确定性 fixtures。

契约覆盖 15–60 秒商业/社交视频的以下有界章节：objective、audience、offer、product、brand、channels、deliverables、creative_constraints、production_constraints、legal_and_compliance、references、success_criteria、open_questions。字段使用有界字符串、数组、数量、时长和对象深度；不含 Prompt、Provider 参数、文件路径、上传对象或任意 extension map。

结构合法性与业务完整性分离：关键字段可为 `null` 或空数组，以便保存真实的不完整 Brief；小型 deterministic checker 再产生明确 issues。应用在写入 JSONB 前调用 canonical validator，并限制序列化内容为 128 KiB；API middleware 以 256 KiB Content-Length 作为第一道请求限制。

## 4. Aggregate、生命周期与权限

### Brief

Brief 是一个 Project 下的稳定 identity，状态为 `draft`、`in_review`、`approved`、`archived`。它持有非空 `current_version_id`、单调 `latest_version_number` 和乐观并发 `version`。一个 Project 可有多个 Brief；title 属于 aggregate metadata。

### BriefVersion

每次内容变化都创建完整、不可变 snapshot；不提供内容 PATCH。状态为 `draft`、`in_review`、`approved`、`superseded`。新版本使前一 current version 进入 `superseded`，但保留其提交/批准时间和批准人。source type 仅为 `manual` 或 `imported_structured`；source reference 是有界 opaque identifier，不接受路径、URL、凭据或请求 header。

### RequirementIssue

issue type：`missing`、`ambiguous`、`conflicting`、`invalid`、`compliance_risk`；severity：`blocking`、`warning`、`informational`；status：`open`、`resolved`、`dismissed`。resolve/dismiss 是显式动作，要求 resolution note、expected issue version、expected Brief version 和 expected current version ID。

确定性检查仅包括：缺少 primary objective、缺少 primary audience、缺少 duration、多个 duration 值冲突、缺少 CTA、regulated category 缺少 disclaimer requirements。它不推断语义、不调用 AI、不建设规则引擎。

权限：owner/admin 可 create、submit、approve、archive、create version 和管理 issues；member 可 create、create version、submit 和管理 issues；viewer 只读。只有 owner/admin 可 approve/archive。所有操作还要求 active membership、匹配的 tenant path 和未 archived Project。

## 5. 数据库与并发策略

新增 `briefs`、`brief_versions`、`requirement_issues`，并为 `projects` 增加 tenant composite unique key。所有新表保存 Organization、Workspace、Project ownership。

- Brief 通过 `(organization_id, workspace_id, project_id)` 复合外键绑定 Project。
- BriefVersion 通过 tenant + Project + Brief 复合外键绑定同一 aggregate。
- RequirementIssue 通过 tenant + Project + Brief + BriefVersion 复合外键绑定同一 snapshot。
- `(brief_id, version_number)` 唯一；`(brief_id, id)` 支撑 same-Brief pointer/supersedes 外键。
- Brief 的 current pointer 使用 `DEFERRABLE INITIALLY DEFERRED` 复合外键指向同一 BriefVersion，使创建 Brief + Version 1 能在一个事务内保持最终非空约束。
- supersedes 使用 same-Brief 复合外键；状态、版本、approval/resolution metadata 使用 CHECK。

创建新版本先执行数据库级 CAS：`UPDATE briefs ... WHERE tenant + project + brief_id + version = expected + current_version_id = expected`，原子递增 aggregate version/latest number 并移动 pointer，`RETURNING` 分配的新 version number；然后插入 snapshot、supersede 旧版本、创建 issues 与 audit。并发失败无返回行并产生 409，事务回滚，不留下版本或 audit。

submit、approve、archive 与 issue mutations 同样通过 Brief CAS；issue resolve/dismiss 另用 issue version CAS。approval 在同一事务中检查 open blocking issues，再以 expected Brief version CAS，确保并发 issue mutation 会使 approval stale，而不是绕过 blocker。

## 6. API 与错误边界

只增加附件列出的 Project-scoped Brief routes：aggregate create/get/list，version get/list/create，submit/approve/archive，issue get/create/resolve/dismiss，以及小型 Brief audit read。所有 request models `extra="forbid"`，客户端不能赋值 tenant IDs、状态、版本号、pointer、approval 或 audit 字段。

错误保持 canonical envelope：无效内容/语义 400；不可见资源 opaque 404；stale、lifecycle、duplicate allocation、approval blockers 409；未处理错误 500。数据库错误不暴露 SQL、约束名或 stack trace。

## 7. 分阶段实施

### Milestone A — 审查、计划与 ADR

- [x] 检查完整仓库、分支、干净状态、近期提交、迁移 head 与 lockfiles。
- [x] 阅读治理、产品、架构、ADR-001 至 ADR-016、既有计划与四层实现。
- [x] 识别阶段冲突并确定追加式治理更新。
- [x] 创建本计划与 ADR-017 至 ADR-021。
- [x] 确认现有依赖足够，不新增直接依赖。

### Milestone B — Contract、migration 与 records

- [x] 新增 Structured Brief v1 JSON Schema、Python/TypeScript validators 与 fixtures。
- [x] 添加跨语言 valid/invalid/unknown/version contract tests；应用层另验证 128 KiB content bound。
- [x] 追加 Alembic revision 与 SQLAlchemy records，不修改初始 migration。
- [x] 验证现有 head 的 upgrade、单版本 downgrade/upgrade、测试数据库 base→head 完整链、head 与 metadata drift；CI 继续从空 PostgreSQL 17 执行同一 migration chain。

### Milestone C — Domain、repositories 与 deterministic issues

- [x] 实现 Brief/Version/Issue domain states 与 transitions。
- [x] 扩展 tenant-scoped repository Protocols、SQLAlchemy adapters 与 UoW。
- [x] 实现有限 deterministic issue checker。
- [x] 添加 domain、constraint、immutability、rollback 与 repository tests。

### Milestone D — Use cases 与 API

- [x] 实现 create/version/review/approval/archive/issue use cases。
- [x] 实现 Brief CAS、pointer/current-version checks、issue CAS 与 atomic audit。
- [x] 增加 Project-scoped routes、显式 schemas、opaque errors 与 request-size guard。
- [x] 添加 tenant、IDOR、mass assignment、approval、concurrency 与 API tests。

### Milestone E — CI、文档与终审

- [x] 保持 PostgreSQL 17 CI 与既有 gates，扩展 contract/persistence test commands。
- [x] 更新 README、阶段治理、领域/安全/测试/本地数据库文档。
- [x] 运行完整 format、lint、typecheck、tests、contract、migration 与 Web build。
- [x] 审查 secrets、生成物、范围外功能和所有安全 must-fix 项。

## 8. 已知限制与复审触发

- 临时 headers 仍不是认证；共享生产前必须替换并复审 RLS/数据库角色。
- JSON Schema v1 只面向 15–60 秒商业/社交视频；两个真实用户群证明同一核心流程需要不兼容结构时再新增 schema version/ADR。
- 不提供 comment、mention、通知或多人实时协作；真实团队试点证明需要时另行设计。
- approval policy 固定为 owner/admin，member 可管理 issues；真实审批层级出现三个以上项目证据时复审，不建设通用 policy engine。
- content immutability 由 repository API、数据库无 update adapter 与 tests 保证，不声称数据库管理员级 WORM。
- API 内容大小限制不能替代反向代理/ASGI server 的传输层限额；首次公网部署前配置基础设施级 body limit。
