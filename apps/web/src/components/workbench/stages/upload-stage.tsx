import { Button } from "../../ui/button";
import { Panel } from "../../ui/panel";
import type { StageProps } from "./stage-props";

function truncateChecksum(checksum: string): string {
  if (checksum.length <= 18) return checksum;
  return `${checksum.slice(0, 10)}…${checksum.slice(-6)}`;
}

type UploadStageProps = Pick<
  StageProps,
  "snapshot" | "sourceFile" | "busy" | "onFileChange" | "onUpload"
>;

export function UploadStage({
  snapshot,
  sourceFile,
  busy,
  onFileChange,
  onUpload,
}: UploadStageProps) {
  return (
    <Panel className="stage-card upload-card">
      <div className="upload-intro">
        <div className="upload-mark" aria-hidden="true">
          +
        </div>
        <div>
          <h3>登记结构化制作输入</h3>
          <p>
            上传会先创建可追溯的 Source Asset，再保存字节对象。它不会触发 Parse
            或接受 Brief。
          </p>
        </div>
      </div>
      <label className="file-picker">
        <span>选择 Structured Brief JSON</span>
        <input
          type="file"
          accept="application/json,.json"
          onChange={onFileChange}
        />
        <small>
          {sourceFile
            ? `${sourceFile.name} · ${sourceFile.size.toLocaleString()} bytes`
            : "尚未选择文件"}
        </small>
      </label>
      <div className="action-row">
        <Button
          label={busy ? "登记中…" : "登记并上传源文件"}
          onClick={onUpload}
          disabled={busy || !sourceFile}
        />
      </div>
      {snapshot.sourceAsset ? (
        <dl className="source-ledger">
          <div>
            <dt>Source Asset</dt>
            <dd>{snapshot.sourceAsset.source_asset.display_name}</dd>
          </div>
          <div>
            <dt>Checksum</dt>
            <dd>
              <code
                title={snapshot.sourceAsset.current_version.checksum_value}
                aria-label={`完整 Checksum：${snapshot.sourceAsset.current_version.checksum_value}`}
              >
                {truncateChecksum(
                  snapshot.sourceAsset.current_version.checksum_value,
                )}
              </code>
            </dd>
          </div>
          <div>
            <dt>Object state</dt>
            <dd>{snapshot.sourceObject?.state ?? "未上传"}</dd>
          </div>
        </dl>
      ) : null}
    </Panel>
  );
}
