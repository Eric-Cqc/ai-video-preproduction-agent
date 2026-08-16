import { ApiClientError } from "../../lib/api/product-client";

interface ErrorPanelProps {
  error: ApiClientError | Error;
  onRefresh: () => void;
  onRetry: () => void;
  onNewKey: () => void;
  canRetry?: boolean;
}

type ErrorPresentation = {
  recovery: string;
  variant: "warning" | "danger";
  showRefresh: boolean;
  showRetry: boolean;
  showNewKey: boolean;
};

function presentError(
  error: ApiClientError | Error,
  canRetry: boolean,
): ErrorPresentation {
  if (!(error instanceof ApiClientError)) {
    return {
      recovery: "请确认网络连接后重试；重新读取状态不会重放任何写入。",
      variant: "danger",
      showRefresh: true,
      showRetry: canRetry,
      showNewKey: false,
    };
  }

  if (error.status === 409) {
    return {
      recovery:
        error.recovery ??
        "先重新读取服务器状态；确认仍需执行后，再使用新的操作键重新提交。",
      variant: "warning",
      showRefresh: true,
      showRetry: false,
      showNewKey: canRetry,
    };
  }

  if (error.status === 400 || error.status === 422) {
    return {
      recovery:
        "请更正本次输入或当前工作区设置后再次提交；无需生成新的操作键。",
      variant: "warning",
      showRefresh: false,
      showRetry: false,
      showNewKey: false,
    };
  }

  if (error.status === 401 || error.status === 403) {
    return {
      recovery: "请确认试点访问凭据和当前工作区访问权限，然后重新读取状态。",
      variant: "warning",
      showRefresh: true,
      showRetry: false,
      showNewKey: false,
    };
  }

  if (error.status === 404) {
    return {
      recovery:
        "当前项目或工作区可能已不可用；重新读取状态后选择可访问的项目。",
      variant: "warning",
      showRefresh: true,
      showRetry: false,
      showNewKey: false,
    };
  }

  if (error.status === 429) {
    return {
      recovery:
        "请求过于频繁。请稍候后重试同一安全操作；不会创建新的制作产物。",
      variant: "warning",
      showRefresh: false,
      showRetry: canRetry,
      showNewKey: false,
    };
  }

  return {
    recovery: "请先重新读取服务器状态；若状态未变化，可安全重试同一操作。",
    variant: "danger",
    showRefresh: true,
    showRetry: canRetry,
    showNewKey: false,
  };
}

export function ErrorPanel({
  error,
  onRefresh,
  onRetry,
  onNewKey,
  canRetry = false,
}: ErrorPanelProps) {
  const apiError = error instanceof ApiClientError ? error : null;
  const presentation = presentError(error, canRetry);
  return (
    <section
      className={`error-panel error-panel-${presentation.variant}`}
      role="alert"
      aria-live="assertive"
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
          {presentation.recovery}
        </p>
      </div>
      <div className="error-actions">
        {presentation.showRefresh ? (
          <button
            className="button secondary"
            type="button"
            onClick={onRefresh}
          >
            重新读取状态
          </button>
        ) : null}
        {presentation.showRetry ? (
          <button className="button secondary" type="button" onClick={onRetry}>
            重试同一安全操作
          </button>
        ) : null}
        {presentation.showNewKey && apiError?.isConflict ? (
          <button className="button warning" type="button" onClick={onNewKey}>
            使用新操作键重新提交
          </button>
        ) : null}
      </div>
    </section>
  );
}
