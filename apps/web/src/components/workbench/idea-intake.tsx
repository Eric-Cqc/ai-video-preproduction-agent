"use client";
import { useState } from "react";
import type { IdeaEdits, IdeaIntake } from "../../lib/api/idea-intake-client";
import { Button } from "../ui/button";

const example =
  "为一家独立咖啡店策划 30 秒小红书短片，面向附近通勤的年轻人。开场是清晨街道与第一杯手冲，用真实日常传达慢下来的一刻。结尾邀请观众来店里尝尝，不夸大功效。";
export function IdeaComposer({
  busy,
  onCreate,
}: {
  busy: boolean;
  onCreate: (idea: string) => void;
}) {
  const [idea, setIdea] = useState("");
  return (
    <section className="idea-composer">
      <div className="composer-heading">
        <span className="artifact-badge">01 · Creative starting point</span>
        <h3>从一句想法，开始一部作品。</h3>
        <p>
          说清你想传达什么、给谁看、在哪里播放。先整理成
          Brief，再由你决定创意方向。
        </p>
      </div>
      <label htmlFor="creative-idea">创作想法</label>
      <textarea
        id="creative-idea"
        value={idea}
        onChange={(event) => setIdea(event.target.value)}
        maxLength={8000}
        rows={6}
        placeholder="例如：为一家独立咖啡店策划 30 秒品牌短片…"
        disabled={busy}
      />
      <div className="composer-footer">
        <button
          type="button"
          className="text-button"
          onClick={() => setIdea(example)}
          disabled={busy}
        >
          填入演示想法
        </button>
        <span>{idea.length.toLocaleString()} / 8,000</span>
        <Button
          label="整理为 Brief 草稿"
          pendingLabel="整理中…"
          pending={busy}
          disabled={busy || !idea.trim()}
          onClick={() => onCreate(idea.trim())}
        />
      </div>
      <p className="mode-note">
        按服务端配置整理想法；使用在线模型时会发送输入内容。请核对假设，不会生成视频。
      </p>
    </section>
  );
}

export function IdeaBriefEditor({
  intake,
  busy,
  onSave,
  onConfirm,
}: {
  intake: IdeaIntake;
  busy: boolean;
  onSave: (edits: IdeaEdits) => void;
  onConfirm: () => void;
}) {
  const initial: IdeaEdits = {
    objective: intake.objective,
    platform: intake.platform,
    audience: intake.audience,
    duration_seconds: intake.duration_seconds,
    content_type: intake.content_type,
    tone: intake.tone,
    key_messages: intake.key_messages,
    call_to_action: intake.call_to_action,
    constraints: intake.constraints,
    must_include: intake.must_include,
    must_avoid: intake.must_avoid,
    assumptions: intake.assumptions,
    missing_fields: intake.missing_fields,
  };
  const [edits, setEdits] = useState<IdeaEdits>(initial);
  const invalidDuration =
    edits.duration_seconds !== null &&
    (!Number.isInteger(edits.duration_seconds) ||
      edits.duration_seconds < 15 ||
      edits.duration_seconds > 60);
  const dirty = JSON.stringify(edits) !== JSON.stringify(initial);
  const stringFields = [
    ["objective", "核心目标"],
    ["audience", "目标受众"],
    ["platform", "发布渠道"],
    ["content_type", "内容形式"],
    ["call_to_action", "行动号召"],
  ] as const;
  const listFields = [
    ["tone", "语气"],
    ["key_messages", "关键信息"],
    ["must_include", "必须包含"],
    ["must_avoid", "避免内容"],
    ["constraints", "制作限制"],
  ] as const;
  return (
    <section className="stage-card idea-brief">
      <span className="artifact-badge">
        Human decision · Draft v{intake.version}
      </span>
      <h3>把想法变成清晰的约定</h3>
      <p>
        核对事实、补全空白，再确认这个 Brief。确认会创建不可变的 Brief 版本。
      </p>
      <blockquote className="original-idea">{intake.raw_idea}</blockquote>
      {intake.assumptions.length || intake.missing_fields.length ? (
        <div className="assumption-note">
          <strong>需要你的判断</strong>
          <ul>
            {intake.assumptions.map((x) => (
              <li key={x}>{x}</li>
            ))}
            {intake.missing_fields.map((x) => (
              <li key={x}>待补充：{x}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="idea-field-grid">
        {stringFields.map(([key, label]) => (
          <label key={key}>
            {label}
            <input
              value={edits[key] ?? ""}
              disabled={busy}
              onChange={(event) =>
                setEdits({ ...edits, [key]: event.target.value || null })
              }
            />
          </label>
        ))}
        <label>
          时长（秒，15–60）
          <input
            type="number"
            min={15}
            max={60}
            value={edits.duration_seconds ?? ""}
            disabled={busy}
            onChange={(event) =>
              setEdits({
                ...edits,
                duration_seconds: event.target.value
                  ? Number(event.target.value)
                  : null,
              })
            }
          />
        </label>
      </div>
      <details className="creative-details">
        <summary>创意与制作约束</summary>
        <div className="idea-field-grid">
          {listFields.map(([key, label]) => (
            <label key={key}>
              {label}（每行一项）
              <textarea
                value={edits[key].join("\n")}
                disabled={busy}
                rows={3}
                onChange={(event) =>
                  setEdits({
                    ...edits,
                    [key]: event.target.value
                      .split("\n")
                      .filter((x) => x.trim()),
                  })
                }
              />
            </label>
          ))}
        </div>
      </details>
      <div className="action-row">
        <Button
          label="保存 Brief 修改"
          onClick={() => onSave(edits)}
          disabled={busy || !dirty || invalidDuration}
        />
        <Button
          label="确认 Brief，进入创意方向"
          onClick={onConfirm}
          disabled={busy || dirty || invalidDuration}
        />
      </div>
      <p className="mode-note">
        {invalidDuration
          ? "Structured Brief v1 支持 15–60 秒，请调整时长。"
          : dirty
            ? "请先保存修改，再确认当前版本。"
            : "未填时长时按 30 秒模板保存。确认仅创建 Brief；Concept 选择与批准仍由你完成。"}
      </p>
    </section>
  );
}
