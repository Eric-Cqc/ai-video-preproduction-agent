import { ReviewSurface } from "../../artifact-views";
import { Button } from "../../ui/button";
import { latestReview } from "../../../lib/workspace-model";
import type { StageProps } from "./stage-props";

type ReviewStageProps = Pick<
  StageProps,
  | "snapshot"
  | "busy"
  | "reviewSummary"
  | "reviewChanges"
  | "onReviewSummaryChange"
  | "onReviewChangesChange"
  | "onApprove"
  | "onRequestChanges"
  | "onCompleteRevision"
  | "onCancelRevision"
>;

export function ReviewStage({
  snapshot,
  busy,
  reviewSummary,
  reviewChanges,
  onReviewSummaryChange,
  onReviewChangesChange,
  onApprove,
  onRequestChanges,
  onCompleteRevision,
  onCancelRevision,
}: ReviewStageProps) {
  const latest = latestReview(snapshot);

  return (
    <section className="stage-card">
      {snapshot.revisionRequest?.status === "open" ? (
        <section className="revision-panel" aria-labelledby="revision-title">
          <div className="stage-card-topline">
            <div>
              <span className="artifact-badge">Open revision request</span>
              <h3 id="revision-title">修改请求待处理</h3>
              <p>
                这是服务器返回的可审计修改请求；完成后会创建新的 successor
                版本。
              </p>
            </div>
            <span className="artifact-badge">
              {snapshot.revisionRequest.artifact_type}
            </span>
          </div>
          <dl className="revision-details">
            <div>
              <dt>审查摘要</dt>
              <dd>
                {snapshot.revisionRequest.summary ??
                  latest?.summary ??
                  "未提供摘要"}
              </dd>
            </div>
            <div>
              <dt>请求修改</dt>
              <dd>
                <pre>
                  {JSON.stringify(
                    snapshot.revisionRequest.requested_changes ??
                      latest?.requested_changes ??
                      {},
                    null,
                    2,
                  )}
                </pre>
              </dd>
            </div>
          </dl>
          <div className="action-row">
            <Button
              label={busy ? "完成中…" : "完成修改并创建 successor 版本"}
              onClick={onCompleteRevision}
              disabled={busy}
            />
            <Button
              label={busy ? "处理中…" : "取消修改请求"}
              onClick={onCancelRevision}
              disabled={busy}
              tone="warning"
            />
          </div>
        </section>
      ) : null}
      <ReviewSurface
        review={latest}
        script={snapshot.script}
        storyboard={snapshot.storyboard}
        shotPlan={snapshot.shotPlan}
      />
      {latest?.outcome === "approved" ? (
        <div className="gate-confirmed" role="status">
          <strong>Planning bundle 已批准</strong>
          <p>Delivery 现在可以创建精确的交付包。</p>
        </div>
      ) : (
        <div className="review-controls bundle-review-controls">
          <label>
            审查摘要
            <textarea
              value={reviewSummary}
              onChange={(event) => onReviewSummaryChange(event.target.value)}
              rows={3}
              maxLength={1000}
            />
          </label>
          <div className="review-control-grid">
            <div>
              <h4>批准规划包</h4>
              <p>批准会记录当前三个版本的精确 lineage，并解锁 Delivery。</p>
              <Button
                label={busy ? "提交中…" : "批准 Planning bundle"}
                onClick={onApprove}
                disabled={
                  busy ||
                  !snapshot.script ||
                  !snapshot.storyboard ||
                  !snapshot.shotPlan ||
                  !reviewSummary.trim()
                }
              />
            </div>
            <div>
              <h4>请求修改</h4>
              <label>
                修改原因
                <textarea
                  value={reviewChanges}
                  onChange={(event) =>
                    onReviewChangesChange(event.target.value)
                  }
                  rows={3}
                  maxLength={1000}
                  placeholder="例如：Storyboard 第 2 场需要与脚本动作保持一致。"
                />
              </label>
              <Button
                label={busy ? "提交中…" : "请求修改"}
                onClick={onRequestChanges}
                disabled={
                  busy ||
                  !snapshot.script ||
                  !snapshot.storyboard ||
                  !snapshot.shotPlan ||
                  !reviewChanges.trim()
                }
                tone="warning"
              />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
