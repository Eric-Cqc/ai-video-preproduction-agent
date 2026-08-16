# Stage 23 Plan — Frontend UI/UX Redesign (Production Desk)

状态:规划稿,尚未冻结、尚未实施。基于只读审计(2026-08-16)。本文件只回答"下一步做什么、分几步、验收标准是什么",不包含任何代码改动。

## 为什么现在做

Stage 20–22 把后端和人工审查门做到了诚实、可验证。但前端本身还是工程感很重的原型:

- 两个巨石文件承载全部 UI:`foundation-status.tsx`(2554 行,单个 client 组件)、`artifact-views.tsx`(665 行)。9 个阶段的渲染逻辑内联在同一个函数里(`foundation-status.tsx:320-910`)。
- 没有设计令牌层。间距/圆角/字号是几十处手写的散乱 rem 值,没有统一的间距刻度,systematic 改版等于要动几十个分散声明。
- 设计文档与实际代码已经漂移:`FRONTEND_DESIGN_SYSTEM.md` 写的断点是 1024/640px,代码里实际是 1180/850/640px;文档写的主色是 "amber #b56d2a",代码里是 `--gold #c88838`。文档不可信,只能当历史意图参考。
- 视觉上像调试后台而非产品:H1 用 `clamp(2.5rem,5vw,4.8rem)` 的大号衬线字,但正文和标签普遍在 0.66–0.86rem,反差突兀;所有 artifact 类型的兜底展示都是同一种 `<pre>` JSON 转储;长 checksum/UUID/digest 全文内联显示,没有截断+复制交互。
- 状态反馈不一致:全局 `ErrorPanel` 有重试/刷新/换幂等键的恢复动作,但阶段内 `.stage-failure`/`.failed-run` 只是纯文字死胡同,没有任何恢复入口。
- 语义色板有真实冲突:`--rust #a44f2c`(用于拒绝/失败态强调)和 `--danger #a8483b`(用于通用错误)视觉上几乎无法区分,违反了文档自己写的"颜色不能单独承载状态"的原则。
- Brief 表单无条件渲染约 30 个字段分组,大部分是空值兜底文案,信息噪音很高,没有按"已填/未填"做渐进展示。

这些问题不是审美偏好分歧,是可以用证据钉死的具体缺陷,适合系统化重做而不是打补丁。

## 目标(这个 Stage 要交付什么)

把 Production Desk 从"能用但丑陋的调试台"改造成"规范、可信、带动态反馈的现代 SaaS 生产看板"(视觉方向见下文用户拍定的方向),同时:

- 不改变任何后端契约、不新增依赖(除非用户在 Phase 0 前明确批准)、不影响已验证的人工审查门语义。
- 现有测试套件(`foundation-status.test.tsx`、`foundation-status.stage-20.test.tsx`、`workspace-model.test.ts`)保持通过,允许因组件拆分调整选择器方式,但不能删测试来规避失败。
- 无障碍基线(skip link、focus ring、aria-live、aria-current、表单 label 关联)不退化。

## 分阶段范围(建议顺序,每阶段可独立验收、独立回滚)

### Phase 0 — 结构地基(不改视觉,只重构)

目的:在动视觉之前先把巨石拆开,否则后续每一次视觉改动都要在 2500 行文件里做外科手术,风险和审查成本都过高。

- 把 `foundation-status.tsx` 按阶段拆成独立组件文件(每个 stage 一个组件:UploadStage、ParseStage、BriefGateStage、ConceptsStage、ScriptStage、StoryboardStage、ShotPlanStage、ReviewGateStage、DeliveryStage),状态派生逻辑(`workspace-model.ts`)保持不动——它已经是干净的纯函数,不需要重写。
- 把 `artifact-views.tsx` 里的共享原语(`FieldGrid`、`JsonInspector`、`DetailValue`、`IssueList`)独立成小文件,便于后续统一重设计这些原语而不用逐个 artifact 类型改。
- 建立 CSS 自定义属性令牌层:把现有散乱的间距值归纳成一套刻度(如 4/8px 基准),颜色变量去重(解决 rust/danger 冲突),字号建立类型刻度。这一步只做令牌抽取和替换,不改变任何视觉输出——验收标准是重构前后截图/渲染结果一致。
- 更新 `FRONTEND_DESIGN_SYSTEM.md`,使其与代码保持一致(断点、色值),避免文档继续漂移。

产出:一份 P0 就位后的干净基座,后续视觉改动才能安全地小范围提交和审查。

### Phase 1 — P0 视觉/交互修复(高影响、低风险)

- 统一错误/失败恢复模式:阶段内失败态也要有明确的重试/查看详情入口,不再是死胡同文字。
- 长 checksum/UUID/digest 改为截断显示 + 一键复制,不再整串平铺。
- 解决 rust/danger 撞色:合并为一套更清晰可辨的语义色(错误/失败/拒绝三者要能一眼区分,不能靠记忆颜色深浅)。
- Rail 导航:被阻塞的阶段在 rail 按钮本身给出阻塞原因提示,而不是让用户点进去才看到空状态占位。

### Phase 2 — 信息密度与内容展示(中影响)

- Brief 表单等重字段表单改为渐进展示:已填字段正常显示,未填字段分组收起或明确归入"待补充"区块,不再是 30 个空值框铺满页面。
- 重新设计 `JsonInspector` 的呈现层级:让"结构化正常内容"和"原始 JSON 兜底"在视觉上有明确区分(字体、背景色、图标),而不是所有 artifact 类型统一用同一个 debug 感的 `<details><pre>`。
- 统一 loading/busy 反馈:除了按钮文案切换,给正在生成的阶段卡片本身加一个轻量状态标识(不需要引入动画库,用 CSS 即可)。

### Phase 3 — 排版与布局精修(视觉打磨)

- 重新校准字号阶梯,收窄 H1 巨大衬线标题与正文极小字号之间的反差。
- 修正 `.main-panel` 固定 `min-height: 48rem` 造成的空白/裁切问题,改为按内容自适应。
- 移动端 rail 形态按用户决策(见下)重新设计,替代现在的"9 项硬挤 3 列 grid"。
- 响应式断点在 1440/1024/390px 三个参考宽度下逐一验证无横向滚动。

## 视觉方向(已由用户拍定,2026-08-16)

- **常规 SaaS 后台风格**:放弃现有"安静编辑部"方向(衬线大标题 + 米纸色调)。改为无衬线字体、规整的卡片/表格系统、清晰的信息层级——目标是让人一眼认出"这是一个专业生产力工具",而不是编辑部风格的展示页。
- **附带动态效果**:状态切换、卡片展开/收起、rail 切换、按钮反馈等交互点要有恰当的过渡动效(transition/transform 级别,CSS 原生动效优先,不必引入动画库),让操作有反馈感,不是静态快照式的界面。
- **明确拒绝 glassmorphism(毛玻璃效果)**:不使用半透明背景模糊(`backdrop-filter: blur`)、不使用玻璃质感的浮层卡片。表面材质保持不透明、边界清晰(实色背景 + 边框/阴影分层,而不是模糊透光)。

这个决定影响 Phase 0 的令牌层设计(色板、字体、间距刻度要按新方向重新定义,不是从旧文档继承)和 Phase 3 的排版精修(字号阶梯改为无衬线体系)。Phase 1/2 的问题清单(错误恢复、checksum 截断、撞色、信息密度)本身与视觉方向无关,结论不变。

## 仍需用户决策的点

1. **是否引入任何前端依赖**。当前 `apps/web` 零 UI 依赖(无 Tailwind、无组件库、无 icon 库、无动画库)。给定"动态效果"的要求,默认建议:CSS 原生 transition/transform 足够覆盖大部分需求,不引入动画库(如 Framer Motion);如需要更精细的编排动效或 icon 集,再单独评估具体库,不预先引入。
2. **移动端 rail 形态**:维持现有横向 3 列 grid,还是改成文档里提到但代码未落地的 4 列,或改成"仅显示当前阶段 + 其余折叠"的手风琴式导航。SaaS 后台方向通常倾向于侧边栏可折叠 + 顶部面包屑,这个可以在 Phase 0 拆分完成后一并定案。

## 验收契约(草案,供正式冻结时细化)

- 现有测试套件全部保持通过;允许因组件拆分调整选择器,但不允许删测试断言以规避失败。
- `make check` 全绿(typecheck / lint / format-check / build)。
- 无障碍基线不退化:每个 Phase 结束后手动过一遍现有 a11y 检查点(skip link、aria-live、aria-current、focus ring、表单 label)。
- 响应式:1440/1024/390px 参考宽度下无横向滚动。
- 不改动 `product-client.ts` 的契约类型,不新增 Provider/认证/媒体渲染能力——这是纯前端视觉与结构工作,不得借机扩大产品边界。
- 每个 Phase 独立验收,不用等全部 4 个 Phase 完成才检查,避免大爆炸式回归和难以定位的问题。

## 建议的下一步动作(如果批准这个计划)

1. 先做 Phase 0(拆分组件 + 建立令牌层)。这一步不改变任何视觉效果,是后续安全重设计的地基,风险最低,可以先动手。
2. Phase 0 完成并验收后,针对上面 3 个决策点向用户出 2–3 个方向的静态方向稿,拿到明确选择后再进 Phase 1。
3. Phase 1 → 2 → 3 按影响力从高到低推进,每个 Phase 独立验收、独立可回滚,不做一次性大改。

## 证据来源

本计划基于一次只读前端审计(2026-08-16),覆盖:`foundation-status.tsx`、`artifact-views.tsx`、`styles.css`、`page.tsx`、`workspace-model.ts`、`product-client.ts` 类型段、`package.json`,以及 `docs/product/FRONTEND_DESIGN_SYSTEM.md`、`FRONTEND_VISUAL_CRITIQUE.md`、`FRONTEND_VISUAL_DIRECTION.md`、`RC_VISUAL_ACCEPTANCE.md`、`FOUNDATION.md`、`AGENTS.md`。审计过程未修改任何文件。
