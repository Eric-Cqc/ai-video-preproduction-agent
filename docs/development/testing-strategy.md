# 测试策略

实现阶段采用风险分层验证：领域模块的规则与状态转换使用快速确定性测试；Schema/跨语言契约使用版本兼容性测试；Adapter 使用契约与模拟 Provider 测试；Job 验证幂等、重试和审计关联；端到端测试覆盖“简报到批准交接包”，不覆盖自动成片。

## 冻结决定

关键测试断言结构化制作产物、授权/tenant 隔离、版本/审计和 Provider 边界，而不是 Prompt 的逐字输出。

## 可替换假设与复审触发

当前工具链使用 Vitest/Testing Library 验证 Web 与 TypeScript 契约，pytest 验证 API、Worker、Python 契约和 registry，Ruff/mypy/ESLint/TypeScript 作为静态门禁。`make check` 与无 secrets 的 CI 执行同一套格式、lint、typecheck、test、contract 与 build gate。

浏览器自动化和覆盖率阈值仍未决定；当前真实 Web client→本地 API 测试已证明健康链路，无需引入浏览器依赖。出现首个真实用户工作流或关键回归无法由现有层级捕获时复审。任何数据泄露或破坏性契约回归都要求增加回归测试。
