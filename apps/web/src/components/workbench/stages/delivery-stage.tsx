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
            label={busy ? "创建中…" : "创建交付包"}
            onClick={onCreateDelivery}
            disabled={busy || latest?.outcome !== "approved"}
          />
        ) : (
          <>
            <Button
              label={busy ? "生成中…" : "生成 ZIP 导出"}
              onClick={onExportDelivery}
              disabled={busy || latest?.outcome !== "approved"}
            />
            {snapshot.exports.map((item) => (
              <button
                className="button secondary download-button"
                type="button"
                key={item.id}
                onClick={() => onDownload(item.id, item.filename)}
                disabled={busy}
              >
                下载 {item.filename}
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
