"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { Platform } from "@/lib/types";
import {
  Button,
  Cell,
  EmptyState,
  Field,
  Input,
  Panel,
  Row,
  Spinner,
  StatusBadge,
  Table,
  Tag,
} from "@/components/ui";

type Tab = "projects" | "platforms" | "api key" | "operator";
const TABS: Tab[] = ["projects", "platforms", "api key", "operator"];

/* ---- Repo URL setter (current project) ---- */
function RepoUrlSetter() {
  const { currentProject, refreshProjects } = useApp();
  const [url, setUrl] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setUrl((currentProject?.options?.repo_url as string) ?? "");
    setSaved(false);
  }, [currentProject]);

  if (!currentProject) return null;

  async function save() {
    if (!currentProject) return;
    const options = { ...(currentProject.options ?? {}), repo_url: url.trim() };
    await api.updateProject(currentProject.id, { options });
    await refreshProjects();
    setSaved(true);
  }

  return (
    <Panel title={`repository · ${currentProject.prefix}`}>
      <div className="space-y-3">
        <p className="mono text-[0.8125rem] text-[var(--color-text-dim)]">
          Base repo URL — makes commit SHAs across the console clickable
          (<span className="text-[var(--color-text-faint)]">{"<url>/commit/<sha>"}</span>).
        </p>
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <Field label="repo url">
              <Input
                placeholder="https://github.com/owner/repo"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setSaved(false);
                }}
              />
            </Field>
          </div>
          <Button onClick={save} variant="ghost">
            {saved ? "saved ✓" : "save"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}

/* ---- Projects tab ---- */
function ProjectsTab() {
  const { projects, refreshProjects } = useApp();
  const [name, setName] = useState("");
  const [prefix, setPrefix] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!name.trim() || !prefix.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.createProject(name.trim(), prefix.trim().toUpperCase());
      await refreshProjects();
      setName("");
      setPrefix("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "create failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* existing projects */}
      <Panel title="projects" pad={false}>
        {projects.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no projects" hint="create one below" />
          </div>
        ) : (
          <Table head={["id", "name", "prefix", "status"]}>
            {projects.map((p) => (
              <Row key={p.id}>
                <Cell mono className="text-[var(--color-text-faint)]">
                  {p.id}
                </Cell>
                <Cell mono>{p.name}</Cell>
                <Cell mono>
                  <Tag>{p.prefix}</Tag>
                </Cell>
                <Cell>
                  <StatusBadge status={p.active ? "pass" : "not_run"} />
                </Cell>
              </Row>
            ))}
          </Table>
        )}
      </Panel>

      {/* new project form */}
      <Panel title="new project">
        <div className="space-y-4">
          <div className="grid grid-cols-[1fr_160px] gap-4">
            <Field label="name">
              <Input
                placeholder="My Project"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="prefix">
              <Input
                placeholder="PRJ"
                value={prefix}
                onChange={(e) => setPrefix(e.target.value.toUpperCase())}
                maxLength={8}
                disabled={saving}
              />
            </Field>
          </div>
          {error && (
            <div className="mono text-[0.75rem] text-[var(--color-fail)]">{error}</div>
          )}
          <Button
            onClick={handleCreate}
            disabled={saving || !name.trim() || !prefix.trim()}
          >
            {saving ? "creating…" : "create project"}
          </Button>
        </div>
      </Panel>

      {/* repo URL for the selected project */}
      <RepoUrlSetter />
    </div>
  );
}

/* ---- Platforms tab ---- */
function PlatformsTab() {
  const { currentProject } = useApp();
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    api
      .platforms(currentProject.id)
      .then(setPlatforms)
      .catch(() => setPlatforms([]))
      .finally(() => setLoading(false));
  }, [currentProject]);

  if (!currentProject)
    return <EmptyState title="no project selected" hint="create one in the projects tab" />;
  if (loading) return <Spinner label="loading platforms" />;

  return (
    <Panel title="platforms" pad={false}>
      {platforms.length === 0 ? (
        <div className="p-4">
          <EmptyState title="no platforms configured" />
        </div>
      ) : (
        <Table head={["name", "notes", "active"]}>
          {platforms.map((p) => (
            <Row key={p.id}>
              <Cell mono>{p.name}</Cell>
              <Cell className="text-[var(--color-text-dim)] text-[0.8125rem]">
                {p.notes ?? <span className="text-[var(--color-text-faint)]">—</span>}
              </Cell>
              <Cell>
                <StatusBadge status={p.active ? "pass" : "not_run"} />
              </Cell>
            </Row>
          ))}
        </Table>
      )}
    </Panel>
  );
}

/* ---- API Key tab ---- */
function ApiKeyTab() {
  const [key, setKey] = useState<string | null>(null);
  const [issuing, setIssuing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleIssue() {
    setIssuing(true);
    setError(null);
    setKey(null);
    try {
      const { api_key } = await api.issueKey();
      setKey(api_key);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "failed to issue key");
    } finally {
      setIssuing(false);
    }
  }

  return (
    <Panel title="api key">
      <div className="space-y-4">
        <p className="mono text-[0.8125rem] text-[var(--color-text-dim)]">
          Issue a long-lived bearer token for programmatic access. Keys are shown only once.
        </p>

        <Button onClick={handleIssue} disabled={issuing} variant="ghost">
          {issuing ? "issuing…" : "issue new key"}
        </Button>

        {error && (
          <div className="mono text-[0.75rem] text-[var(--color-fail)]">{error}</div>
        )}

        {key && (
          <div className="space-y-2">
            <div
              className="mono break-all border border-[var(--color-border-bright)] bg-[var(--color-bg)] px-4 py-3 text-[0.8125rem] text-[var(--color-accent)]"
              style={{ letterSpacing: "0.02em" }}
            >
              {key}
            </div>
            <div
              className="mono text-[0.6875rem]"
              style={{ color: "var(--color-blocked)" }}
            >
              shown once — copy it now. this key will not be displayed again.
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

/* ---- Operator tab ---- */
function OperatorTab() {
  const { user } = useApp();

  if (!user) {
    return <EmptyState title="not authenticated" />;
  }

  return (
    <Panel title="operator">
      <div className="space-y-4">
        <div className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-3">
          <div className="label flex items-center">login</div>
          <div className="mono text-[0.8125rem] text-[var(--color-text)]">{user.login}</div>

          <div className="label flex items-center">email</div>
          <div className="mono text-[0.8125rem] text-[var(--color-text)]">
            {user.email ?? <span className="text-[var(--color-text-faint)]">—</span>}
          </div>

          <div className="label flex items-center">auth method</div>
          <div className="mono text-[0.8125rem]">
            <Tag>{user.auth_method}</Tag>
          </div>

          <div className="label flex items-center">account status</div>
          <div>
            <StatusBadge status={user.active ? "pass" : "not_run"} />
          </div>
        </div>
      </div>
    </Panel>
  );
}

/* ---- Main admin page ---- */
export default function Admin() {
  const [activeTab, setActiveTab] = useState<Tab>("projects");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">admin</h1>
        <p className="label mt-0.5">system configuration · control panel</p>
      </div>

      {/* tab bar */}
      <div className="flex gap-1 border-b border-[var(--color-border)]">
        {TABS.map((t) => {
          const active = t === activeTab;
          return (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              className={[
                "mono px-4 py-2 text-[0.75rem] uppercase tracking-wider transition-colors border-b-2 -mb-px",
                active
                  ? "border-[var(--color-accent)] text-[var(--color-accent)]"
                  : "border-transparent text-[var(--color-text-faint)] hover:text-[var(--color-text-dim)]",
              ].join(" ")}
            >
              {t}
            </button>
          );
        })}
      </div>

      {/* tab panels */}
      {activeTab === "projects" && <ProjectsTab />}
      {activeTab === "platforms" && <PlatformsTab />}
      {activeTab === "api key" && <ApiKeyTab />}
      {activeTab === "operator" && <OperatorTab />}
    </div>
  );
}
