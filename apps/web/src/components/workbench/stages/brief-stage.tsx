import { BriefSurface } from "../../artifact-views";
import { Button } from "../../ui/button";
import { EmptyStage } from "../../ui/empty-stage";
import type { StageProps } from "./stage-props";

type BriefStageProps = Pick<
  StageProps,
  | "snapshot"
  | "busy"
  | "rejectReason"
  | "rejectNote"
  | "onAccept"
  | "onReject"
  | "onRejectReasonChange"
  | "onRejectNoteChange"
>;

export function BriefStage({
  snapshot,
  busy,
  rejectReason,
  rejectNote,
  onAccept,
  onReject,
  onRejectReasonChange,
  onRejectNoteChange,
}: BriefStageProps) {
  if (snapshot.brief) {
    return (
      <section className="stage-card">
        <div className="gate-heading">
          <div>
            <span className="artifact-badge">Accepted artifact</span>
            <h3>已接受的 Brief</h3>
            <p>这是制作人接受后保存的版本化 Brief；要求问题仍保留在产物中。</p>
          </div>
          <span className="artifact-badge">accepted</span>
        </div>
        <BriefSurface
          content={snapshot.brief.current_version.structured_content}
          issues={snapshot.brief.issues}
        />
        <div className="gate-confirmed" role="status">
          <strong>Brief 已接受</strong>
          <p>后续 Concepts 生成仍需在 Concepts 阶段明确开始。</p>
        </div>
      </section>
    );
  }

  if (!snapshot.candidate) {
    return (
      <section className="stage-card">
        <EmptyStage message="完成 Parse 后，这里会出现待审查的 Brief 候选。" />
      </section>
    );
  }

  return (
    <section className="stage-card">
      <div className="gate-heading">
        <div>
          <span className="artifact-badge">Human review required</span>
          <h3>审查 Brief 候选</h3>
          <p>
            候选字段和要求问题均来自当前提取运行。只有你的操作会创建 Brief
            版本。
          </p>
        </div>
        {snapshot.candidateReview ? (
          <span className="artifact-badge">
            {snapshot.candidateReview.status}
          </span>
        ) : null}
      </div>
      <BriefSurface
        content={snapshot.candidate.candidate}
        issues={snapshot.candidate.candidate_issues}
        candidate
      />
      {!snapshot.candidateReview &&
      snapshot.artifacts.briefCandidateReviewAction ? (
        <div className="stage-failure" role="status">
          <strong>候选审查状态未验证</strong>
          <p>浏览器中的恢复记录不会被当作服务器状态；请重新明确确认此候选。</p>
        </div>
      ) : null}
      {snapshot.candidateReview?.action === "accept" ? (
        <div className="gate-confirmed" role="status">
          <strong>Brief 已接受</strong>
          <p>后续 Concepts 生成仍需在 Concepts 阶段明确开始。</p>
        </div>
      ) : snapshot.candidateReview?.action === "reject" ? (
        <div className="gate-rejected" role="status">
          <strong>Brief 候选已拒绝</strong>
          <p>请回到 Parse 重新创建一轮候选；本次拒绝不会被静默覆盖。</p>
        </div>
      ) : (
        <div className="review-controls">
          <div className="review-control-grid">
            <div>
              <h4>接受候选</h4>
              <p>接受后会创建版本化 Brief，保留当前候选的审查记录。</p>
              <Button
                label={busy ? "接受中…" : "接受 Brief 候选"}
                onClick={onAccept}
                disabled={busy}
              />
            </div>
            <div>
              <h4>拒绝候选</h4>
              <label>
                原因
                <select
                  value={rejectReason}
                  onChange={(event) => onRejectReasonChange(event.target.value)}
                >
                  <option value="inaccurate">内容不准确</option>
                  <option value="incomplete">内容不完整</option>
                  <option value="unsafe">存在安全问题</option>
                  <option value="irrelevant">与项目无关</option>
                  <option value="duplicate">重复内容</option>
                  <option value="other">其他</option>
                </select>
              </label>
              <label>
                备注（可选）
                <textarea
                  value={rejectNote}
                  onChange={(event) => onRejectNoteChange(event.target.value)}
                  rows={3}
                  maxLength={500}
                />
              </label>
              <Button
                label={busy ? "拒绝中…" : "拒绝 Brief 候选"}
                onClick={onReject}
                disabled={busy}
                tone="warning"
              />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
