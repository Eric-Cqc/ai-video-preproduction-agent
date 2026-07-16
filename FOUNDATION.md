# Foundation Bootstrap：工程宪法

## 使命与边界

本项目是 **AI 视频前期制作系统**：把创意简报转化为可审查、可版本化、可交接的制作蓝图（故事、脚本、镜头、资产、预算/排期假设与导出包）。它帮助人作决定和组织生产，**不是自动成片、渲染、剪辑、发布或投放平台**。

前九阶段已建立工程骨架、tenant-aware PostgreSQL、不可变 Brief、受控 Structured Brief ingestion、SourceAsset、verified SourceObject、确定性 DocumentExtraction，以及离线 deterministic fake provider 的 immutable Run/Attempt 与 `human_review_required` candidate。第十阶段只增加显式人审安全基础：tenant-scoped candidate 读取、幂等 accept/reject、CAS 创建新 draft BriefVersion、atomic Audit 与 immutable approved predecessor。仍不得接入真实模型、SDK、凭据、网络、自动候选接受、Job、产品 UI、云资源或自动成片。阶段决定由 [ADR-017 至 ADR-047](docs/adr/) 追加记录。

## 冻结的基础决定

| 决定 | 约束 |
| --- | --- |
| 架构 | 模块化单体，按领域边界组织，避免早期微服务。 |
| 核心数据 | 统一的结构化视频制作 Schema；Prompt 是一次生成的输入/证据，不是核心业务实体。 |
| 集成 | 所有外部模型、存储和未来供应商经 Adapter 边界进入。 |
| 可信性 | 业务对象可版本化、关键操作可审计、长任务由后台 Job 执行。 |
| 隔离 | 数据模型与授权从第一天具备 tenant-aware 语义。 |
| 前后端契约 | 跨语言只共享显式、版本化契约，不共享运行时内部实现。 |
| 浏览器 | 浏览器不直接调用模型或其他 Provider；服务端持有凭据并执行策略。 |

对应论证见 [ADR](docs/adr/)。这些决定在触发条件前不得以局部便利为由绕过。

## 可替换假设与复审触发

技术框架、具体数据库、队列、身份提供方、模型与云厂商均为可替换假设，当前尚未选型。只有出现下列证据时才重新评估冻结决定：

1. 单体的独立部署/伸缩/故障隔离需求连续两个发布周期无法满足，且有量化指标和边界证明时，评估拆分服务。
2. Schema 无法表达已批准的制作流程，或破坏性演进连续两次无法通过版本迁移处理时，评估 Schema 设计。
3. Provider Adapter 无法覆盖两个以上已批准的供应商差异，且造成领域泄漏时，评估 Adapter 契约。
4. 单租户试点准备转为共享生产环境、或出现外部协作者访问时，复审多租户隔离、身份和审计要求。
5. 后台任务的吞吐、可靠性或成本目标连续两个周期不达标时，复审 Job 运行时与队列选型。

所有复审必须先新增 ADR；既有记录不改写。

## 不可违反的工程规则

- 领域模块只能通过公开契约协作，不得跨模块直接依赖内部存储或 Provider SDK。
- 用户可见的制作产物、批准状态和导出必须可追溯至版本、操作者和来源 Job。
- 不把密钥、个人数据、原始客户素材或未脱敏日志写入仓库、客户端或普通日志。
- 任何涉及自动成片、浏览器直连 Provider、未审计的状态变更，均须先更新产品边界和 ADR，并获得明确批准。

详细规则见项目级 [AGENTS.md](AGENTS.md)。
