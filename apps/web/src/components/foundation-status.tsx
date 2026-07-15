import type { HealthResult } from "../lib/api/health-client";

interface FoundationStatusProps {
  environment: string;
  api: HealthResult;
}

export function FoundationStatus({ environment, api }: FoundationStatusProps) {
  return (
    <main className="shell">
      <section className="card" aria-labelledby="foundation-title">
        <p className="eyebrow">Engineering foundation</p>
        <h1 id="foundation-title">AI Video Preproduction Agent</h1>
        <p className="summary">
          System health only. No AI video product features are enabled.
        </p>
        <dl className="status-grid">
          <div>
            <dt>Environment</dt>
            <dd>{environment}</dd>
          </div>
          <div>
            <dt>Web status</dt>
            <dd>
              <span className="indicator ok" />
              Ready
            </dd>
          </div>
          {api.state === "available" ? (
            <>
              <div>
                <dt>API connectivity</dt>
                <dd>
                  <span className="indicator ok" />
                  Connected
                </dd>
              </div>
              <div>
                <dt>API service</dt>
                <dd>{api.health.service}</dd>
              </div>
              <div>
                <dt>API version</dt>
                <dd>{api.health.version}</dd>
              </div>
              <div>
                <dt>Contract version</dt>
                <dd>{api.health.contract_version}</dd>
              </div>
            </>
          ) : (
            <div className="error" role="alert">
              <dt>API connectivity</dt>
              <dd>
                <span className="indicator error-dot" />
                Unavailable — {api.message}
              </dd>
            </div>
          )}
        </dl>
      </section>
    </main>
  );
}
