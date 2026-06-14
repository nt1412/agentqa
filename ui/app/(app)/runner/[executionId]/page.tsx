"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Artifact, Execution } from "@/lib/types";
import {
  Cell,
  EmptyState,
  Panel,
  Row,
  Spinner,
  StatusBadge,
  Table,
  Tag,
} from "@/components/ui";

export default function ExecutionRunnerPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const id = Number(executionId);

  const [execution, setExecution] = useState<Execution | null | undefined>(undefined); // undefined=loading, null=not-found
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loadingArtifacts, setLoadingArtifacts] = useState(true);

  /* -------- fetch execution -------- */
  useEffect(() => {
    if (!id) return;
    api.execution(id)
      .then((e) => setExecution(e))
      .catch(() => setExecution(null));
  }, [id]);

  /* -------- fetch artifacts after execution loads -------- */
  useEffect(() => {
    if (!execution) return;
    setLoadingArtifacts(true);
    api.artifacts(execution.id)
      .then((a) => setArtifacts(a))
      .catch(() => setArtifacts([]))
      .finally(() => setLoadingArtifacts(false));
  }, [execution]);

  /* -------- loading / not-found -------- */
  if (execution === undefined) return <Spinner label={`loading execution #${id}`} />;
  if (execution === null) return <EmptyState title={`execution #${id} not found`} hint="check the id and try again" />;

  const steps = execution.steps ?? [];

  return (
    <div className="space-y-6">
      {/* page header */}
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">
          EXECUTION RUNNER · #{execution.id}
        </h1>
        <p className="label mt-0.5">
          v{execution.version_id}
          {execution.build_id ? ` · build b${execution.build_id}` : ""}
          {execution.plan_id ? ` · plan #${execution.plan_id}` : ""}
        </p>
      </div>

      {/* execution detail */}
      <Panel title="execution detail">
        <div className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3">
          <div>
            <div className="label mb-1">status</div>
            <StatusBadge status={execution.status} />
          </div>
          <div>
            <div className="label mb-1">version</div>
            <span className="mono text-sm">v{execution.version_id}</span>
          </div>
          <div>
            <div className="label mb-1">build</div>
            <span className="mono text-sm">{execution.build_id ? `b${execution.build_id}` : "—"}</span>
          </div>
          <div>
            <div className="label mb-1">created</div>
            <span className="mono text-sm text-[var(--color-text-dim)]">
              {new Date(execution.created_at).toLocaleString()}
            </span>
          </div>
          {execution.duration != null && (
            <div>
              <div className="label mb-1">duration</div>
              <span className="mono text-sm">{execution.duration}s</span>
            </div>
          )}
          {execution.session_id && (
            <div>
              <div className="label mb-1">session</div>
              <span className="mono text-sm text-[var(--color-text-faint)]">{execution.session_id}</span>
            </div>
          )}
        </div>
        {execution.notes && (
          <div className="mt-4 border-t border-[var(--color-border)] pt-4">
            <div className="label mb-1.5">notes</div>
            <p className="text-sm text-[var(--color-text-dim)] leading-relaxed">{execution.notes}</p>
          </div>
        )}
      </Panel>

      {/* step results */}
      <Panel title="step results" pad={false}>
        {steps.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no step results recorded" />
          </div>
        ) : (
          <Table head={["step", "status", "notes"]}>
            {steps.map((s) => (
              <Row key={s.step_id}>
                <Cell mono className="text-[var(--color-text-faint)] w-16">
                  #{s.step_id}
                </Cell>
                <Cell>
                  <StatusBadge status={s.status} />
                </Cell>
                <Cell className="text-[var(--color-text-dim)] text-sm">
                  {s.notes ?? "—"}
                </Cell>
              </Row>
            ))}
          </Table>
        )}
      </Panel>

      {/* artifacts */}
      <Panel title="artifacts" pad={false}>
        {loadingArtifacts ? (
          <div className="p-4">
            <Spinner label="loading artifacts" />
          </div>
        ) : artifacts.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no artifacts" />
          </div>
        ) : (
          <Table head={["type", "title", "mime", "size"]}>
            {artifacts.map((a) => (
              <Row key={a.id}>
                <Cell>
                  <Tag>{a.artifact_type}</Tag>
                </Cell>
                <Cell className="text-[var(--color-text-dim)] text-sm">
                  {a.title ?? "—"}
                </Cell>
                <Cell mono className="text-[var(--color-text-faint)]">
                  {a.mime_type ?? "—"}
                </Cell>
                <Cell mono className="text-[var(--color-text-faint)]">
                  {a.size != null ? `${(a.size / 1024).toFixed(1)} KB` : "—"}
                </Cell>
              </Row>
            ))}
          </Table>
        )}
      </Panel>
    </div>
  );
}
