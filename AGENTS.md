# 项目级工作规则

本文件约束后续所有自动化与人工改动；与 `FOUNDATION.md` 冲突时，以更严格的约束为准。

## 当前阶段

第1–19阶段已完成并合并到 `main`。Hosted Pilot Phase 1 仅授权通过 ADR-064 的服务器端 DeepSeek `deepseek-v4-flash` Adapter；默认、测试与 CI 仍使用确定性离线 Provider。除该精确 Adapter 外，继续禁止真实 Provider/SDK、浏览器 Provider 访问、tool use、URL 抓取、图片或视频生成、媒体渲染、Job/queue、云对象存储、认证、部署与第二十阶段推测性范围。所有产物必须 tenant-aware、可审计且保持不可变 lineage。

所有 Node.js、npm、npx 或 JavaScript 包管理器命令必须通过 `./scripts/run-with-node.sh`。Python 使用仓库内 `.venv` 与已锁定依赖，不修改全局环境。

Makefile 是开发者的公共命令入口；不要直接执行裸 `node`、`npm` 或 `npx`。根 `package.json` 会让其后续 npm 子进程再次经过 wrapper；直接运行 `npm run ...` 无法技术上控制该父 npm 进程所使用的 Node，因此不属于支持的入口。

## 产品与架构护栏

- 产品是 AI 视频前期制作系统，不得描述或实现自动成片平台。
- 维持模块化单体；未经 ADR 和触发证据，不引入微服务、分布式事务或服务间 RPC。
- 结构化制作 Schema 是核心；Prompt 仅作为可审计的输入、模板或执行记录，不能成为作品真相来源。
- 外部能力经 Adapter；浏览器不得保存 Provider 密钥或直接调用 Provider。
- 所有未来持久化设计必须 tenant-aware，并为版本、审计和后台 Job 留出关联字段。

## 变更流程

1. 先阅读 `FOUNDATION.md` 及受影响目录文档；保持其术语和边界一致。
2. 以小而可审查的改动完成单一意图；保留用户已有的有效修改。
3. 架构取舍、新外部边界、破坏性 Schema 演进或达到复审触发条件时，先新增 ADR，不修改历史 ADR 结论。
4. 不记录、输出或提交密钥、令牌、真实客户素材、个人数据或 Provider 原始响应。
5. 完成后检查变更范围、链接、术语一致性和适用的格式/测试；报告未解决的假设。

## 文档约定

- 明确标记“冻结决定”“可替换假设”“复审触发条件”。
- 使用“制作蓝图/前期制作产物”，避免把生成建议表述为最终视频。
- 新文档必须链接相关产品边界与 ADR；新增技术选型不得伪装成既定事实。
