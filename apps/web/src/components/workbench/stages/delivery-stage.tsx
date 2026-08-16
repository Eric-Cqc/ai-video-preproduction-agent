import { DeliverySurface } from "../../artifact-views";
import { Button } from "../../ui/button";
import { latestReview } from "../../../lib/workspace-model";
import type { StageProps } from "./stage-props";

type DeliveryStageProps = Pick<
  StageProps,
  | "snapshot"
  | "busy"
  | "onCreateDelivery"
  | "onExportDelivery"
  | "onDownload"
  | "download"
>;

export function DeliveryStage({
  snapshot,
  busy,
  onCreateDelivery,
  onExportDelivery,
  onDownload,
  download,
}: DeliveryStageProps) {
  const latest = latestReview(snapshot);

  return (
    <section className="stage-card">
      <DeliverySurface
        deliveryPackage={snapshot.deliveryPackage}
        exports={snapshot.exports}
      />
      <div className="delivery-actions">
        {!snapshot.deliveryPackage ? (
          <Button
            label="创建交付包"
            onClick={onCreateDelivery}
            disabled={busy || latest?.outcome !== "approved"}
            pending={busy}
            pendingLabel="创建中…"
          />
        ) : (
          <>
            <Button
              label="生成 ZIP 导出"
              onClick={onExportDelivery}
              disabled={busy || latest?.outcome !== "approved"}
              pending={busy}
              pendingLabel="生成中…"
            />
            {snapshot.exports.map((item) => (
              <button
                className={`button secondary download-button${busy ? " button-pending" : ""}`}
                type="button"
                key={item.id}
                onClick={() => onDownload(item.id, item.filename)}
                disabled={busy}
                aria-busy={busy || undefined}
              >
                {busy ? (
                  <span className="button-spinner" aria-hidden="true" />
                ) : null}
                {busy ? "准备下载中…" : `下载 ${item.filename}`}
              </button>
            ))}
            {download ? (
              <a
                className="button download-link"
                href={download.downloadUrl}
                download={download.filename}
              >
                再次下载 {download.filename}
              </a>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}
