# ADR-011：Engineering Skeleton 工具链

- 状态：已接受（当前里程碑；实现可替换）
- 决定：第二阶段使用 npm workspaces、Node 24、Next.js App Router、Python 3.13、FastAPI、独立 Python Worker、uv 与单一 versioned JSON Schema 建立可执行工程骨架。
- 原因：这些工具能用少量常规配置证明 Web/API/Worker/契约边界，适合单人维护，且不需要 monorepo orchestrator、容器或云资源。
- 后果：提交 `package-lock.json` 与 `uv.lock`；所有 JavaScript 命令经过 `scripts/run-with-node.sh`；Python 依赖仅进入仓库内 `.venv`；根命令统一执行质量门禁。
- 与既有 ADR 的一致性：Web、API、Worker 是职责与进程边界，仍构成一个 monorepo 内的模块化单体系统；不拥有独立业务数据库，不引入分布式事务或服务自治。JSON Schema 落实 ADR-009，Provider registry 只落实 ADR-005 的最小扩展边界。
- 不包含：数据库、认证、生产队列、真实 Provider、AI 视频功能、云部署、SDK 生成或产品 UI。
- 可替换假设：具体框架、版本范围、测试工具、Python 包管理器和部署拓扑。
- 复审：工具不再支持已固定的 Node/Python 版本、两个连续发布周期造成可量化维护阻塞，或达到既有 ADR 的架构复审条件时，以新 ADR 替代；不得静默改写本记录。
