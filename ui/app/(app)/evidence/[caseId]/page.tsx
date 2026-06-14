"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type {
  Artifact,
  EvidenceBundle,
  EvidenceExecution,
  FailureContext,
  SimilarFailure,
} from "@/lib/types";
import {
  EmptyState,
  Spinner,
  StatusBadge,
  Tag,
  statusColor,
} from "@/components/ui";

type Tab = "reasoning" | "artifacts" | "similar";

export default function EvidencePage() {
  const { currentProject } = useApp();
  const { caseId: caseIdStr } = useParams<{ caseId: string }>();
  const caseId = Number(caseIdStr);

  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [context, setContext] = useState<FailureContext | null>(null);
  const [similar, setSimilar] = useState<SimilarFailure[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("reasoning");

  useEffect(() => {
    if (Number.isNaN(caseId)) return;
    setLoading(true);
    (async () => {
      const [ev, ctx, sim] = await Promise.all([
        api.evidence(caseId).catch(() => null),
        api.failureContext(caseId).catch(() => null),
        api.similarFailures(caseId).catch(() => [] as SimilarFailure[]),
      ]);
      setBundle(ev);
      setContext(ctx);
      setSimilar(sim);
      setLoading(false);
    })();
  }, [caseId]);

  if (!currentProject)
    return <EmptyState title="no project selected" hint="create one in Admin" />;
  if (Number.isNaN(caseId))
    return <EmptyState title="invalid case id" />;
  if (loading) return <Spinner label="loading evidence" />;
  if (!bundle)
    return <EmptyState title="no evidence found" hint={`case #${caseId} has no recorded executions`} />;

  const allArtifacts: Artifact[] = context?.artifacts ?? [];

  return (
    <div className="space-y-5">
      {/* header */}
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">
          EVIDENCE &middot; CASE #{caseId}
        </h1>
        {context && (
          <p className="label mt-0.5">
            {context.case_name} &middot; {bundle.executions.length} execution
            {bundle.executions.length !== 1 ? "s" : ""} on record
          </p>
        )}
      </div>

      {/* split layout */}
      <div className="grid gap-5" style={{ gridTemplateColumns: "1.2fr 1fr" }}>
        {/* LEFT — execution cards */}
        <div className="space-y-3">
          <div
            className="label pb-1.5 border-b"
            style={{ borderColor: "var(--color-border-bright)" }}
          >
            executions
          </div>

          {bundle.executions.length === 0 ? (
            <EmptyState title="no executions in bundle" />
          ) : (
            bundle.executions.map((exec: EvidenceExecution) => (
              <ExecutionCard key={exec.id} exec={exec} />
            ))
          )}
        </div>

        {/* RIGHT — tabbed analysis */}
        <div className="flex flex-col gap-3">
          {/* tab bar */}
          <div
            className="flex gap-0 border-b"
            style={{ borderColor: "var(--color-border-bright)" }}
          >
            {(["reasoning", "artifacts", "similar"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className="label px-4 py-2.5 border-b-2 transition-colors"
                style={{
                  borderColor: tab === t ? "var(--color-accent)" : "transparent",
                  color:
                    tab === t
                      ? "var(--color-accent)"
                      : "var(--color-text-faint)",
                }}
              >
                {t === "reasoning"
                  ? "reasoning"
                  : t === "artifacts"
                    ? `artifacts${allArtifacts.length ? ` (${allArtifacts.length})` : ""}`
                    : `similar${similar.length ? ` (${similar.length})` : ""}`}
              </button>
            ))}
          </div>

          {/* tab content */}
          <div className="flex-1 overflow-auto">
            {tab === "reasoning" && (
              <ReasoningTab context={context} />
            )}
            {tab === "artifacts" && (
              <ArtifactsTab artifacts={allArtifacts} />
            )}
            {tab === "similar" && (
              <SimilarTab similar={similar} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- Execution Card ---- */
function ExecutionCard({ exec }: { exec: EvidenceExecution }) {
  const isFail = exec.status === "fail";
  const isBlocked = exec.status === "blocked";
  const accentColor =
    isFail
      ? "var(--color-fail)"
      : isBlocked
        ? "var(--color-blocked)"
        : "var(--color-border)";

  return (
    <div
      className="border p-4"
      style={{
        borderColor: "var(--color-border)",
        background: "var(--color-bg-elev)",
        borderLeft: `2px solid ${accentColor}`,
      }}
    >
      {/* card header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <StatusBadge status={exec.status} />
          <div className="flex items-center gap-3 mt-1">
            <span className="mono text-sm font-semibold">#{exec.id}</span>
            {exec.build_id && (
              <span className="mono text-[0.75rem] text-[var(--color-text-faint)]">
                build {exec.build_id}
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className="mono text-[0.6875rem] text-[var(--color-text-faint)]">
            {new Date(exec.created_at).toLocaleString()}
          </div>
          {exec.artifacts.length > 0 && (
            <div className="mono text-[0.625rem] text-[var(--color-text-faint)] mt-1">
              {exec.artifacts.length} artifact{exec.artifacts.length !== 1 ? "s" : ""}
            </div>
          )}
        </div>
      </div>

      {/* claims */}
      {exec.claims.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <div
            className="label border-t pt-2"
            style={{ borderColor: "var(--color-border)" }}
          >
            claims
          </div>
          {exec.claims.map((claim, i) => (
            <div
              key={i}
              className="flex items-start gap-2 py-1 px-2 border"
              style={{
                borderColor: "var(--color-border)",
                background: "var(--color-bg)",
              }}
            >
              <span
                className="mono text-[0.625rem] flex-shrink-0 mt-0.5"
                style={{ color: "var(--color-accent)" }}
              >
                &#8853;
              </span>
              <span className="mono text-[0.75rem] text-[var(--color-text-dim)] leading-relaxed">
                {claim}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---- Reasoning Tab ---- */
function ReasoningTab({ context }: { context: FailureContext | null }) {
  if (!context || context.prior_reasoning.length === 0) {
    return (
      <EmptyState
        title="no prior reasoning"
        hint="prior AI reasoning will appear here after failed executions"
      />
    );
  }

  return (
    <div className="space-y-3">
      {context.prior_reasoning.map((entry, idx) => (
        <div
          key={idx}
          className="border"
          style={{ borderColor: "var(--color-border)" }}
        >
          <div
            className="flex items-center justify-between border-b px-3 py-1.5"
            style={{ borderColor: "var(--color-border)" }}
          >
            <span className="label">reasoning entry {idx + 1}</span>
            <span
              className="mono text-[0.625rem] uppercase tracking-wider"
              style={{ color: "var(--color-text-faint)" }}
            >
              {Object.keys(entry).join(" · ")}
            </span>
          </div>
          <pre
            className="mono p-3 text-[0.6875rem] leading-relaxed overflow-x-auto whitespace-pre-wrap break-words"
            style={{ color: "var(--color-text-dim)" }}
          >
            {JSON.stringify(entry, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

/* ---- Artifacts Tab ---- */
function ArtifactsTab({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) {
    return (
      <EmptyState
        title="no artifacts"
        hint="execution artifacts will appear here"
      />
    );
  }

  return (
    <div className="space-y-2">
      {artifacts.map((a) => (
        <div
          key={a.id}
          className="border p-3 flex items-start justify-between gap-3"
          style={{
            borderColor: "var(--color-border)",
            background: "var(--color-bg-elev)",
          }}
        >
          <div className="flex flex-col gap-1.5 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Tag color="var(--color-accent)">{a.artifact_type}</Tag>
              {a.mime_type && (
                <Tag>{a.mime_type}</Tag>
              )}
            </div>
            <span className="mono text-sm text-[var(--color-text)] truncate">
              {a.title ?? a.blob_key}
            </span>
            <span className="mono text-[0.6875rem] text-[var(--color-text-faint)]">
              key: {a.blob_key}
            </span>
          </div>
          {a.size != null && (
            <div className="flex-shrink-0 text-right">
              <span className="mono text-[0.75rem] text-[var(--color-text-faint)]">
                {formatBytes(a.size)}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ---- Similar Failures Tab ---- */
function SimilarTab({ similar }: { similar: SimilarFailure[] }) {
  if (similar.length === 0) {
    return (
      <EmptyState
        title="no similar failures found"
        hint="semantic vector search finds related failures across the project"
      />
    );
  }

  return (
    <div className="space-y-2">
      <p
        className="label pb-2 border-b"
        style={{ borderColor: "var(--color-border)", color: "var(--color-text-faint)" }}
      >
        ranked by semantic distance &mdash; lower = more similar
      </p>
      {similar.map((sf, idx) => {
        const distanceNorm = Math.min(sf.distance, 1);
        const barWidth = `${Math.round((1 - distanceNorm) * 100)}%`;

        return (
          <a
            key={`${sf.case_id}-${sf.execution_id}`}
            href={`/evidence/${sf.case_id}`}
            className="block border p-3 transition-colors hover:bg-[var(--color-bg-elev-2)]"
            style={{ borderColor: "var(--color-border)" }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span
                    className="mono text-[0.625rem] text-[var(--color-text-faint)]"
                    style={{ minWidth: "1.25rem" }}
                  >
                    #{idx + 1}
                  </span>
                  <span className="mono text-sm font-semibold text-[var(--color-accent)]">
                    case #{sf.case_id}
                  </span>
                  <span className="mono text-[0.75rem] text-[var(--color-text-faint)]">
                    exec #{sf.execution_id}
                  </span>
                </div>
                <StatusBadge status={sf.status} />
              </div>

              <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                <span
                  className="mono text-sm font-semibold"
                  style={{ color: statusColor(sf.status) }}
                >
                  {sf.distance.toFixed(3)}
                </span>
                <span className="label" style={{ color: "var(--color-text-faint)" }}>
                  distance
                </span>
              </div>
            </div>

            {/* similarity bar */}
            <div
              className="mt-2.5 h-0.5 w-full rounded-full"
              style={{ background: "var(--color-border-bright)" }}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: barWidth,
                  background: statusColor(sf.status),
                  opacity: 0.7,
                }}
              />
            </div>
          </a>
        );
      })}
    </div>
  );
}

/* ---- helpers ---- */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
