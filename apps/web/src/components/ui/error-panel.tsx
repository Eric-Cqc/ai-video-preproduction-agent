import { ApiClientError } from "../../lib/api/product-client";

interface ErrorPanelProps {
  error: ApiClientError | Error;
  onRefresh: () => void;
  onRetry: () => void;
  onNewKey: () => void;
}

export function ErrorPanel({
  error,
  onRefresh,
  onRetry,
  onNewKey,
}: ErrorPanelProps) {
  const apiError = error instanceof ApiClientError ? error : null;
  return (
    <section
      className="error-panel"
      role="alert"
      aria-labelledby="error-title"
      aria-describedby="error-recovery"
    >
      <div>
        <p className="eyebrow">操作未完成</p>
        <h3 id="error-title">{apiError?.code ?? "本地工作流错误"}</h3>
        <p>{error.message}</p>
        {apiError?.correlationId ? (
          <p className="correlation-line">
            Correlation ID：{apiError.correlationId}
          </p>
        ) : null}
        <p className="error-recovery" id="error-recovery">
          恢复会重新读取服务器状态；若操作可安全重放，也可直接重试。
        </p>
      </div>
      <div className="error-actions">
        <button className="button secondary" type="button" onClick={onRefresh}>
          恢复并刷新状态
        </button>
        <button className="button secondary" type="button" onClick={onRetry}>
          重试安全操作
        </button>
        {apiError?.isConflict ? (
          <button className="button warning" type="button" onClick={onNewKey}>
            使用新操作键重试
          </button>
        ) : null}
      </div>
    </section>
  );
}
