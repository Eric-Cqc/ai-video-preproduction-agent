# Stage 21 Acceptance Contract — Hosted Pilot Validation & Operational Hardening(冻结)

冻结日期:2026-08-15。依据:五路独立审计(H1 hosted 栈、H2 适配器、H3 评审记录、H4 可靠性、H5 运维)。
边界:ADR-064/ADR-066 不变 — 单租户、唯一 DeepSeek 服务端适配器、本地 Compose、确定性默认;不引入 queue/云存储/多用户认证/第二 Provider/监控栈。

## WS-R 可靠性与操作安全(主树)

- R1 F-18:三处 repository 宽泛异常处理收窄为仅 `IntegrityError`→409,其余透传至 500 envelope;参数化测试覆盖三处。
- R2 F-20:新增 `delivery_export_cleanup_requirements` 表(新迁移,镜像 source-object 模式,tenant/project 域,(adapter,key) 唯一);delivery `_delete_quietly` 改为 delete-or-record(删除失败→新 UoW 持久化清理行,再失败→日志)。
- R3 Storage sweep:`infra/scripts/storage_sweep.py` + `make storage-sweep`:默认 dry-run,需显式 apply;仅扫描本地 adapter 根下 `object-*/stage-*`;操作员提供 grace period;保护 `source_objects`∪`delivery_export_files` 引用键;先处理清理行;失败行保留并返回非零;无调度器/后台任务。
- R4 RC PID 所有权:PID 文件带 start-time/命令/端口标记;停止前复验所有权;拒绝杀死/删除存活的非本流程 PID;SIGKILL 后确认退出。
- R5 Makefile 操作性:RC curl 加 `--connect-timeout/--max-time`;hosted compose exec 加 `-T`;新增 `hosted-backup`(quiesce caddy/web/api → pg_dump custom 格式 → application_files tar → sha256 清单 → 重启,全部经真实 compose 服务名)。

## WS-P 适配器真实性与有界预算(worktree ws-h-adapter)

- P1 F-27:`DeepSeekProvider` 接受服务端提供的 `base_url`/`model_id`,`main.py` 传入已验证配置;适配器边界仍只接受批准的 origin/model;接线测试。
- P2 Provider usage 持久化:将 usage 元数据(input/output/total tokens、provider request id)以加法方式持久化到既有 run/operation 行(新迁移,nullable 列);审计不含原文。
- P3 重试卫生:两次尝试间有界 backoff;收到 `Retry-After` 时在上限内尊重;跨尝试总 wall-clock 上限=timeout×attempts。
- P4 错误映射:concepts/script 的 provider 失败映射到稳定错误码(timeout/refusal/provider_error),不再折叠为通用 `invalid_request`。
- P5 `requested_changes` 有界:字节上限与嵌套深度校验(400 超限)。
- P6 F-19 拆分(concepts/script/storyboard/shot-plan 四处):reservation 先短事务提交 → 关闭 UoW → provider 调用 → 新 UoW 重授权+复验输入摘要 → finalize accepted/failed(操作状态迁移新增 failed/expired + 请求时 stale-reservation 恢复);brief extraction 已是该模式,作为参照。revision 拆分为 Large,**明确保留为文档化残留**(捆绑三调用需全有或全无)。

## WS-V hosted 验证真实性(worktree ws-h-hosted)

- V1 compose 最小权限:`web` 移除 `env_file`,仅 allowlist 非密钥变量;`caddy`/`web` 增加 healthcheck(或由 V2 冒烟覆盖并记录理由)。
- V2 真实 hosted 冒烟:新 `infra/scripts/hosted_proxy_smoke.py`(httpx,经 `https://PILOT_DOMAIN` proxy origin + cookie jar):未认证 401→错误密码拒绝→登录+cookie 标志→确定性全链合成工作流(复用 rc_socket_smoke 断言:replay/409、viewer 拒绝、跨租户 404、ZIP 校验和/manifest)→登出;bootstrap 幂等(跑两次断言相同 org/ws ID、active、owner);`make hosted-smoke` 指向它(保留内部 health 为 fallback 检查)。
- V3 本地验证配方:文档化 + `.env.hosted` 本地生成辅助(`PILOT_DOMAIN=localhost`、`MODEL_PROVIDER=deterministic_offline`、强随机密钥;Caddy 本地 CA;不削弱 Secure cookie);TLS 校验经 Caddy 本地根证书或显式记录的 `--insecure` 例外仅限 localhost。
- V4 门限流代理修正:hosted 环境信任 Caddy 的 `X-Forwarded-For`(仅该跳),避免按 proxy IP 聚合锁死全部试点用户。

## WS-D 文档(集成后,主树)

- D1 落地 `docs/hosted/HOSTED_PILOT_REVIEW.md` 与 `docs/adr/ADR-067`(以 H3 草案为基,按实际落地的 P2/P3/P6 修正 GAP 表;结论保持 CONDITIONAL,live key 不接受)。
- D2 落地 `docs/hosted/OPERATIONS_RUNBOOK.md`(以 H5 草案为基,更新为实际新增的 make 目标;restore 保持文档化手工程序)。
- D3 KNOWN_LIMITATIONS/README/handoff 同步(revision F-19 残留、无成本账本、无 PII 检测、单节点)。

## 范围外(保持冻结)

live key 运行与 egress 变更(EXTERNAL + 激活门)、PII 检测/脱敏、成本账本与配额系统、自动降级、日志聚合/监控栈、RLS/审计防篡改、revision 事务拆分、多用户。

## 验收

1. `make check` 全绿(所有新测试并入);迁移 downgrade/upgrade 循环通过。
2. `make rc-check` 通过;`make storage-sweep`(dry-run)可运行。
3. 真实 hosted 栈本机验证:`hosted-build → hosted-up → hosted-bootstrap → hosted-smoke(经 proxy origin 全链)→ hosted-backup → hosted-down`,localhost + 确定性 Provider。
4. 独立 red-team review 通过或 findings 闭合;文档与实现零漂移。
