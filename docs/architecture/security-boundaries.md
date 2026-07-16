# 安全边界

信任边界包括浏览器/API、API/PostgreSQL、未来 Worker/Provider，以及 Organization/Workspace tenant 之间。所有 Project 与 Brief route 在服务端验证 actor、path/header Organization、Workspace ownership、active Membership 与 operation role；Project ID、Brief ID 或 Version ID 单独永远不足以授权。

## 临时身份限制

`X-Actor-Subject`、`X-Organization-Id`、`X-Workspace-Id` 只是 local/test/ci context injection，不是认证。配置属性与请求 middleware/dependency 双重限制允许环境；其他环境即使收到 header 也返回 403，不静默接受。该机制可伪造，不能部署到共享生产。

## 数据与错误边界

- Organization/Workspace mismatch 由 scoped query 和复合外键共同阻止。
- inaccessible 与 nonexistent tenant resources 统一 opaque 404，降低 IDOR 枚举。
- PATCH 禁止 status/未知字段；生命周期只走 activate/archive；stale version 返回 409。
- SQLAlchemy repository 不 commit；domain mutation 与 AuditEvent 同 UoW 原子提交。
- Brief 内容写入前由 canonical schema 验证并限制为 128 KiB；API Content-Length 上限默认为 256 KiB。source reference 只允许 opaque identifier，不接受 URL、路径或凭据。
- Brief/Version/Issue 的每个查询均包含 Organization、Workspace、Project 与上级 aggregate scope；跨 tenant 和错误父级统一 opaque 404。
- Ingestion key 唯一性限定为 Organization/Workspace/Project/operation；digest、idempotency key 与内部 `reserved` 不返回给客户端、不写 Audit。accepted replay 先于 Brief CAS。
- Brief source reference 仅接受有界 opaque identifier。SourceAsset provenance 是有界声明元数据：路径、database URL、Authorization-like 值、signed URL 与控制字符不被接受，任何值均不被抓取。
- SourceAssetVersion 保留 immutable declared SHA-256/byte size；Stage 7 上传只接受绑定既有 Version 的 bounded octet-stream，并在流式写入时独立计算 observed SHA-256/size。任何不一致均回滚且不能形成 available SourceObject。
- Storage key 由服务端随机生成，filename、tenant ID 和客户端字符串不进入路径。Local adapter 校验 root、拒绝 traversal/symlink read、使用 exclusive staging 与不可覆盖 finalize；只允许 local/test/ci。
- SourceObject 与 upload outcome 查询始终包含 Organization、Workspace、Project、Asset、Version scope。字节、filename、checksum、storage key/path、Idempotency-Key 与 headers 不写 Audit 或公共错误。
- Document parser 由 verified media type 服务端选择，不接受动态名称。输入经 StoragePort 读取后重新核对 SHA-256/size；只允许 bounded UTF-8 plain text/CSV/JSON，拒绝 binary controls、重复 JSON key、过深/过宽结构和超限输出。Parser 不执行宏/代码、不解压、不抓取 URL。
- DocumentExtraction 不可变且完整 tenant/Project/Asset/Version scoped；Audit 不含 source/extracted full text、checksum、filename、storage key 或 operation key。
- 离线 Brief extraction 只从 scoped immutable DocumentExtraction 读取文本；模型 port 禁止 tools/external actions，当前只有 deterministic fake。输入/输出有硬上限，输出必须是 raw JSON 并通过 canonical Structured Brief Schema。Run/Attempt 与 candidate 不可变，完整 Prompt、输入、原始输出和 candidate 内容均不进入 Audit；candidate 只能由 owner/admin/member 显式 accept/reject，viewer 只读。
- Candidate review 的 scoped reservation、Brief/Version/Issue mutation、terminal finalize 与 Audit 共用一个 UoW；任一失败全部回滚且不留下 `reserved`。同 key 不同 canonical request digest 返回 409，accepted replay 不重复 mutation。所有 inaccessible/nonexistent path 统一 opaque 404，合法 viewer 的 mutation 返回 403。
- Accept 只创建新的 draft BriefVersion：首次创建 Brief/version 1，后续通过 aggregate version 与 current pointer 双 CAS 创建 successor。已批准 predecessor 的所有持久列保持不变；reject 不创建 Brief 或 Version。公共响应不暴露 digest、idempotency key、actor、correlation 或内部 reservation。
- SourceAsset、Version 与 operation 查询始终含 Organization、Workspace、Project 和父 aggregate scope；跨 tenant 或跨 Project 读取统一 opaque 404。viewer 只读，member 不得 archive，archive 不提供 PATCH/DELETE 替代路径。
- SourceAsset operation 的 idempotency key、digest、内部 `reserved` status 不返回、不记录 Audit。accepted replay 先于 aggregate/current-pointer CAS；每个 accepted outcome 同时引用 asset 与 immutable version。
- Brief attachment 只接受同 tenant、同 Project、active Asset 的正确 Version。repository 使用带 accepted-status 谓词的条件插入，防止 reserved/rejected ingestion 经内部通道单独获得 attachment；application finalize、attachment 和 audit 共用一个 UoW transaction。
- Brief 状态、current pointer 与 issue mutations 使用数据库条件更新；stale pointer/version 返回 409，失败事务不写成功审计。
- DATABASE_URL 不写日志，诊断表示隐藏 password；错误不返回 SQL、约束名或堆栈。
- Audit payload 仅含 changed fields/status/version，不含 secret、Prompt、素材或 Provider response。
- Storyboard/Shot Plan request digest、Idempotency-Key、operation row、Prompt/raw
  provider output never cross the API boundary. URL/shell/code/tool-like text is
  untrusted and rejected; the only provider is an offline deterministic fixture.
- CORS 仍使用显式 origin/method/header，不允许 wildcard credentials。

## 冻结决定

Provider secret 只允许未来受控服务端；每个持久化查询和审计读取必须 tenant-scoped；浏览器不得直连 Provider。

## 已知风险与复审触发

本阶段主要在应用层隔离，未启用 PostgreSQL RLS；数据库管理员也能直接修改 immutable-version 或 audit table。Content-Length 与流式计数不能替代反向代理/ASGI server 的传输层限制。PostgreSQL 与 storage 没有分布式事务，补偿降低但不能消除进程崩溃留下孤儿对象的窗口。系统验证 checksum/size，不做 MIME sniffing、malware scanning 或文档安全解析。首次共享生产前必须替换 local adapter 和临时 headers，新增生产存储/认证威胁模型，并复审 RLS、基础设施 body limit、加密/KMS、恶意内容扫描、清理 reconciliation、保留和审计防篡改。
