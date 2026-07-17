"use client";

import { useEffect, useMemo, useState } from "react";

import type { HealthResult } from "../lib/api/health-client";
import {
  ApiClientError,
  createProductClient,
  type LocalWorkspaceContext,
  type Project,
} from "../lib/api/product-client";

interface FoundationStatusProps {
  environment: string;
  api: HealthResult;
  apiBaseUrl: string;
}

const stages = [
  "Intake",
  "Brief",
  "Concepts",
  "Script",
  "Storyboard",
  "Shot Plan",
  "Review",
  "Delivery",
] as const;

const contextStorageKey = "production-desk-context";

function loadStoredContext(): LocalWorkspaceContext {
  const fallback = { actorSubject: "", organizationId: "", workspaceId: "" };
  if (typeof window === "undefined") return fallback;
  const saved = window.localStorage.getItem(contextStorageKey);
  if (!saved) return fallback;
  try {
    const value = JSON.parse(saved) as Partial<LocalWorkspaceContext>;
    if (
      typeof value.actorSubject === "string" &&
      typeof value.organizationId === "string" &&
      typeof value.workspaceId === "string"
    ) {
      return value as LocalWorkspaceContext;
    }
  } catch {
    window.localStorage.removeItem(contextStorageKey);
  }
  return fallback;
}

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `desk-${Date.now()}`;
}

function messageFor(error: unknown): string {
  if (!(error instanceof ApiClientError)) {
    return "无法连接本地服务。请确认 API 已启动后重试。";
  }
  if (error.status === 403 || error.status === 404) {
    return "当前工作区不可访问，或该记录不存在。请核对本地工作区上下文。";
  }
  if (error.status === 409) {
    return "这项操作已被其他更新改变。刷新项目后再试。";
  }
  if (error.status === 422) {
    return "请检查输入内容是否完整。";
  }
  return "操作未完成。请稍后重试。";
}

function StageRail({ active }: { active: string }) {
  return (
    <nav className="production-rail" aria-label="制作阶段">
      <p className="rail-label">Production rail</p>
      <ol>
        {stages.map((stage, index) => (
          <li key={stage} className={stage === active ? "active" : ""}>
            <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            {stage}
          </li>
        ))}
      </ol>
    </nav>
  );
}

function ContextForm({
  value,
  onChange,
}: {
  value: LocalWorkspaceContext;
  onChange: (value: LocalWorkspaceContext) => void;
}) {
  return (
    <details className="context-panel">
      <summary>本地工作区设置</summary>
      <p>仅用于本机开发环境；不会保存凭据，也不会连接外部服务。</p>
      <div className="context-fields">
        {(
          [
            ["actorSubject", "操作人"],
            ["organizationId", "组织 ID"],
            ["workspaceId", "工作区 ID"],
          ] as const
        ).map(([field, label]) => (
          <label key={field}>
            {label}
            <input
              value={value[field]}
              onChange={(event) =>
                onChange({ ...value, [field]: event.target.value })
              }
              autoComplete="off"
            />
          </label>
        ))}
      </div>
    </details>
  );
}

function ProjectList({
  projects,
  onSelect,
}: {
  projects: readonly Project[];
  onSelect: (project: Project) => void;
}) {
  if (projects.length === 0) {
    return (
      <p className="empty-state">尚无项目。创建一个制作蓝图项目以开始工作。</p>
    );
  }
  return (
    <ul className="project-list" aria-label="项目列表">
      {projects.map((project) => (
        <li key={project.id}>
          <button type="button" onClick={() => onSelect(project)}>
            <strong>{project.name}</strong>
            <span>{project.status}</span>
            <small>{project.description || "尚未添加说明"}</small>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function FoundationStatus({
  environment,
  api,
  apiBaseUrl,
}: FoundationStatusProps) {
  const [context, setContext] =
    useState<LocalWorkspaceContext>(loadStoredContext);
  const [projects, setProjects] = useState<readonly Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [notice, setNotice] = useState(
    "输入本地工作区设置后，可读取或创建项目。",
  );
  const [busy, setBusy] = useState(false);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [download, setDownload] = useState<{
    downloadUrl: string;
    filename: string;
  } | null>(null);
  const client = useMemo(
    () => createProductClient(apiBaseUrl, context),
    [apiBaseUrl, context],
  );

  useEffect(() => {
    window.localStorage.setItem(contextStorageKey, JSON.stringify(context));
  }, [context]);

  async function loadProjects() {
    if (
      !context.organizationId ||
      !context.workspaceId ||
      !context.actorSubject
    ) {
      setNotice("请先完整填写本地工作区设置。");
      return;
    }
    setBusy(true);
    try {
      const result = await client.listProjects();
      setProjects(result.items);
      setSelected(
        (current) =>
          result.items.find((item) => item.id === current?.id) ?? null,
      );
      setNotice(`已读取 ${result.items.length} 个项目。`);
    } catch (error) {
      setNotice(messageFor(error));
    } finally {
      setBusy(false);
    }
  }

  async function createProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectName.trim()) {
      setNotice("请填写项目名称。");
      return;
    }
    setBusy(true);
    try {
      const project = await client.createProject({
        name: projectName.trim(),
        description: projectDescription.trim() || null,
        idempotencyKey: newIdempotencyKey(),
      });
      setProjects((current) => [project, ...current]);
      setSelected(project);
      setProjectName("");
      setProjectDescription("");
      setNotice("项目已创建。下一步请在 Intake 中登记已批准的制作输入。");
    } catch (error) {
      setNotice(messageFor(error));
    } finally {
      setBusy(false);
    }
  }

  async function runGoldenPath() {
    if (!selected || !sourceFile) {
      setNotice("请选择项目和符合 Structured Brief v1 的 JSON 文件。");
      return;
    }
    setBusy(true);
    setDownload(null);
    try {
      const result = await client.runGoldenPath(
        selected.id,
        sourceFile,
        setNotice,
      );
      setDownload(result);
      setNotice("真实制作链已完成，交付 ZIP 可下载。");
    } catch (error) {
      setNotice(messageFor(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="production-shell">
      <a className="skip-link" href="#workspace">
        跳至工作区内容
      </a>
      <header className="masthead">
        <div>
          <p className="eyebrow">AI VIDEO PREPRODUCTION AGENT</p>
          <h1>Production Desk</h1>
        </div>
        <div className="system-state" aria-live="polite">
          <span
            className={
              api.state === "available"
                ? "status-dot ready"
                : "status-dot blocked"
            }
          />
          {api.state === "available"
            ? `本地 API 已连接 · ${environment}`
            : "本地 API 未连接"}
        </div>
      </header>

      <div className="workspace-grid" id="workspace">
        <aside className="left-panel">
          <StageRail active={selected ? "Intake" : "Intake"} />
          <ContextForm value={context} onChange={setContext} />
        </aside>

        <section className="main-panel" aria-labelledby="desk-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Projects home</p>
              <h2 id="desk-title">制作项目</h2>
            </div>
            <button
              className="button secondary"
              type="button"
              disabled={busy}
              onClick={() => void loadProjects()}
            >
              {busy ? "处理中…" : "刷新项目"}
            </button>
          </div>
          <p className="notice" role="status">
            {notice}
          </p>

          <form
            className="project-form"
            onSubmit={(event) => void createProject(event)}
          >
            <label>
              新项目名称
              <input
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="例如：春季品牌片"
              />
            </label>
            <label>
              制作说明（可选）
              <input
                value={projectDescription}
                onChange={(event) => setProjectDescription(event.target.value)}
                placeholder="目标、受众或交付背景"
              />
            </label>
            <button className="button" type="submit" disabled={busy}>
              创建项目
            </button>
          </form>
          <ProjectList projects={projects} onSelect={setSelected} />
        </section>

        <aside className="right-panel" aria-label="项目详情">
          <p className="eyebrow">Project context</p>
          {selected ? (
            <>
              <h2>{selected.name}</h2>
              <p>{selected.description || "尚未添加项目说明。"}</p>
              <dl className="metadata-list">
                <div>
                  <dt>状态</dt>
                  <dd>{selected.status}</dd>
                </div>
                <div>
                  <dt>版本</dt>
                  <dd>v{selected.version}</dd>
                </div>
              </dl>
              <section className="next-step">
                <h3>运行完整制作链</h3>
                <p>
                  选择符合 Structured Brief v1 的 JSON；每一步都通过真实本地 API
                  持久化。
                </p>
                <input
                  aria-label="Structured Brief JSON"
                  type="file"
                  accept="application/json,.json"
                  onChange={(event) =>
                    setSourceFile(event.target.files?.[0] ?? null)
                  }
                />
                <button
                  className="button"
                  type="button"
                  disabled={busy || !sourceFile}
                  onClick={() => void runGoldenPath()}
                >
                  {busy ? "制作中…" : "开始 Golden Path"}
                </button>
                {download ? (
                  <a
                    className="button"
                    href={download.downloadUrl}
                    download={download.filename}
                  >
                    下载 {download.filename}
                  </a>
                ) : null}
              </section>
              <details className="artifact-detail">
                <summary>项目记录</summary>
                <pre>{JSON.stringify(selected, null, 2)}</pre>
              </details>
            </>
          ) : (
            <p className="empty-state">
              选择一个项目后，可查看其版本、后续动作和可审计记录。
            </p>
          )}
          <section className="safety-note">
            <h3>边界</h3>
            <p>
              本工作台只编排前期制作蓝图。不会调用真实模型、网络
              Provider、媒体生成或渲染服务。
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}
