# Stage 20 Acceptance Contract — Truthful Local RC(冻结)

冻结日期:2026-08-15。依据:`CURRENT_TRUTH_AND_NEXT_STAGE.md` 五路审计 + 本机真实验证。
本阶段目标:把"人工决策的不可变制作蓝图"从后端事实变成产品事实,并使新鲜环境 RC 与文档一致。

范围外(保持冻结,不实施):hosted privacy/retention/cost review(PRODUCT DECISION)、live DeepSeek 全链验收(EXTERNAL)、provider registry 重构、多用户认证、云存储、媒体生成、queue、OCR/富解析。

## WS-A 后端正确性(P1)— services/api、infra/migrations、tests

- A1 Replay 授权:creative/delivery(及其他 replay 路径)在解析 replay 之前执行 membership/role 检查;新增 unauthorized-replay 测试(viewer、已移除成员)。
- A2 Replay payload 真实性:ingestion/source-asset replay 返回与原始操作一致的结果(或显式区分 aggregate-current 与 operation-result 字段);修复硬编码 `duplicate_count=0`;新增版本推进后的 replay 回归测试。
- A3 取消操作:独立 `CANCEL_REVISION_REQUEST` 操作类型(迁移扩展允许值);loser 路径校验 digest/状态;发出取消审计事件(同事务);路由返回 replay 语义(非恒 201)。
- A4 候选接受审计:accept 在同事务中为 Brief 聚合追加审计事件,使 Brief 审计列表可见候选来源变更。
- A5 并发完成 replay:loser 路径重读 winner 已提交状态后再返回。
- A6 流式下载预检:创建 StreamingResponse 前验证对象存在/可读(至少打开与首块读取或 stat),失败返回结构化错误而非 200 断流;补 missing-object 测试。
- A7 Brief extraction 服务端幂等:接受 Idempotency-Key(与现有幂等模式一致);相同 key+digest replay 不新建 run。
- 约束:不可变 lineage 不受破坏;API 仅做加法演进;全部现有测试保持绿;每项修复配新测试;审计不含 prompt/源文本。

## WS-B Production Desk 产品化(P1)— 仅 apps/web

- B1 Stage-aware 项目工作区:持久化 artifact ID(每项目);通过既有 GET 路由水合;刷新/重进可 resume;stage rail 反映真实进度。
- B2 真实人工门:Brief 候选审阅屏(展示内容与 requirement issues,显式 Accept/Reject);概念对比与显式选择(三选一);Script/Storyboard/ShotPlan 生成为显式分步操作;显式 bundle 审批(approve / request changes);revision 请求流。
- B3 可读 artifact 表面:格式化 Brief、概念卡片、脚本阅读视图、分镜卡片、shot 表格、delivery manifest+checksum 展示;禁止以 raw JSON dump 作为主要视图。
- B4 可靠性语义:解析 API 错误 envelope(code/message/correlation_id)并展示;409 给出可执行恢复路径;幂等 key 按 run/内容派生而非固定 projectId+step;切换项目清理 sourceFile/download 状态;pending/failed/blocked 状态真实呈现。
- 约束:只用既有 API 路由(不新增后端端点);遵守 `FRONTEND_DESIGN_SYSTEM.md`;Node 一律经 `./scripts/run-with-node.sh`;客户端逻辑配测试;不引入新依赖除非必要且说明。

## WS-C RC 真实性与文档(P1/P2)— Makefile、infra/scripts、docs

- C1 新增 test DB 迁移目标(如 `db-upgrade-test`),接入 `rc-up`/`rc-check`,与 CI 路径一致。
- C2 LOCAL_QUICKSTART 补 `make setup` 与前置(uv、fnm/Node、Docker);从零可走通。
- C3 rc-up 传播 API_BASE_URL/CORS 至 18000/13000;rc 流程失败时清理后台进程(trap)。
- C4 文档漂移:system-context、KNOWN_LIMITATIONS、REAL_PROVIDER_INTEGRATION_CHECKLIST、current-handoff、README(人工动作措辞与新 UI 一致、hosted 存储措辞)。

## 维护者裁决(2026-08-15,基于独立综合审计,已冻结)

- D-01 A7 兼容性:Idempotency-Key 在既有 brief-extraction 路由上为**可选** header;提供即幂等,缺省保持旧行为。不得强制新 header,不另立版本化路由。
- D-02 A2 遗留行真实性:必须提供 snapshot-availability/legacy 标记(或可辩护的 backfill),禁止对遗留行"过度声称"真实 replay。
- D-03 WS-B resume 定义冻结为**同浏览器、ID 引导** resume(localStorage + 既有 GET 复验;selection 经既有幂等 mutation 复验)。不新增后端 discovery 路由。
- D-04 `rc-smoke` 改为真实 socket 级;原 TestClient 套件保留为 `rc-golden-path-test`。
- D-05 WS-C 在 WS-A + WS-B 集成之后执行。
- D-06 F-09(storage finalize 先于 DB commit 的 crash 窗口)接受为 ADR-034 受控 P2 残留,由 WS-C 在 handoff/KNOWN_LIMITATIONS 记录 post-stage owner;本阶段不做持久 reconciliation。
- D-07 ADR-064 要求的 privacy/retention/cost/availability review 与 live 验收保持在 Stage 20 之外(PRODUCT DECISION);任何文档不得声称 "hosted candidate accepted"。
- D-08 一次性 clone 的 `make typecheck` 证据为验收必需;F-22(next-env.d.ts)仅在复现时修复,不手改生成文件。
- D-09 Builder 工作笔记(.codex-task-plan.md / .codex-notes.md 等)不进入集成。

## 验收(整体)

1. 新鲜环境:`make setup` → `make rc-up` → `make check` 全绿,无需未记载的手工步骤。
2. `make rc-smoke` 通过;Web 测试通过;`make build` 通过。
3. UI 上完成一次真实 Golden Path:每个人工门均由显式操作通过,artifact 可读,lineage 可见,ZIP 可下载。
4. A1–A7 各有可失败的针对性测试;全套测试绿。
5. 独立 red-team review 通过或其 findings 已闭合。
