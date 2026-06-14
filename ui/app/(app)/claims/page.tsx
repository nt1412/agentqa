"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { Claim } from "@/lib/types";
import { Button, EmptyState, Grid, Spinner, Stat, statusColor } from "@/components/ui";

type Verdict = "confirmed" | "refuted" | "inconclusive";
const VERDICTS: Verdict[] = ["confirmed", "refuted", "inconclusive"];

const COLUMNS: { key: "unverified" | Verdict; label: string; colorVar: string }[] = [
  { key: "unverified", label: "UNVERIFIED", colorVar: "var(--color-text-faint)" },
  { key: "confirmed", label: "CONFIRMED", colorVar: "var(--color-confirmed)" },
  { key: "refuted", label: "REFUTED", colorVar: "var(--color-refuted)" },
  { key: "inconclusive", label: "INCONCLUSIVE", colorVar: "var(--color-inconclusive)" },
];

export default function ClaimsPage() {
  const { currentProject } = useApp();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    api
      .claims(currentProject.id)
      .then((data) => {
        setClaims(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [currentProject]);

  if (!currentProject)
    return <EmptyState title="no project selected" hint="create one in Admin" />;
  if (loading) return <Spinner label="loading claims" />;

  async function handleVerdict(claim: Claim, verdict: Verdict) {
    if (claim.verdict === verdict) return; // no-op: already this verdict
    const prevVerdict = claim.verdict ?? null;
    // optimistic: set the new verdict + bump count (re-verify appends, never erases)
    setClaims((cs) =>
      cs.map((c) =>
        c.id === claim.id
          ? { ...c, verdict, verification_count: (c.verification_count ?? 0) + 1 }
          : c,
      ),
    );
    setVerifying((s) => new Set(s).add(claim.id));
    try {
      await api.verifyClaim(claim.id, verdict);
    } catch {
      // rollback
      setClaims((cs) =>
        cs.map((c) =>
          c.id === claim.id
            ? {
                ...c,
                verdict: prevVerdict,
                verification_count: Math.max(0, (c.verification_count ?? 1) - 1),
              }
            : c,
        ),
      );
    } finally {
      setVerifying((s) => {
        const n = new Set(s);
        n.delete(claim.id);
        return n;
      });
    }
  }

  const byColumn = (key: "unverified" | Verdict) =>
    key === "unverified"
      ? claims.filter((c) => !c.verdict)
      : claims.filter((c) => c.verdict === key);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">CLAIM AUDIT BOARD</h1>
        <p className="label mt-0.5">
          {currentProject.name} &middot; agent claim verification &middot; verdicts are an
          append-only audit trail — re-verify to override (history kept)
        </p>
      </div>

      <Grid cols={4}>
        {COLUMNS.map((col) => (
          <Stat
            key={col.key}
            label={col.label.toLowerCase()}
            value={byColumn(col.key).length}
            color={
              col.key === "unverified"
                ? byColumn("unverified").length > 0
                  ? "var(--color-fail)"
                  : "var(--color-pass)"
                : col.colorVar
            }
          />
        ))}
      </Grid>

      <div className="grid grid-cols-4 gap-4 items-start">
        {COLUMNS.map((col) => {
          const cards = byColumn(col.key);
          return (
            <KanbanColumn
              key={col.key}
              label={col.label}
              colorVar={col.colorVar}
              count={cards.length}
            >
              {cards.length === 0 ? (
                <EmptyState title={`none ${col.label.toLowerCase()}`} />
              ) : (
                <div className="space-y-2.5">
                  {cards.map((claim) => (
                    <ClaimCard
                      key={claim.id}
                      claim={claim}
                      busy={verifying.has(claim.id)}
                      onVerdict={(v) => handleVerdict(claim, v)}
                    />
                  ))}
                </div>
              )}
            </KanbanColumn>
          );
        })}
      </div>
    </div>
  );
}

function KanbanColumn({
  label,
  colorVar,
  count,
  children,
}: {
  label: string;
  colorVar: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 border-t-2 pt-3" style={{ borderColor: colorVar }}>
      <div className="flex items-center justify-between">
        <span
          className="mono text-[0.6875rem] font-semibold uppercase tracking-widest"
          style={{ color: colorVar }}
        >
          {label}
        </span>
        <span
          className="mono text-[0.6875rem] border px-1.5 py-0.5 rounded-sm"
          style={{ borderColor: colorVar, color: colorVar, opacity: 0.8 }}
        >
          {count}
        </span>
      </div>
      {children}
    </div>
  );
}

function ClaimCard({
  claim,
  busy,
  onVerdict,
}: {
  claim: Claim;
  busy: boolean;
  onVerdict: (v: Verdict) => void;
}) {
  const resolved = !!claim.verdict;
  const accent = resolved ? statusColor(claim.verdict as string) : "var(--color-border-bright)";
  return (
    <div
      className="border p-3 flex flex-col gap-3"
      style={{
        borderColor: "var(--color-border)",
        background: "var(--color-bg-elev)",
        borderLeft: `2px solid ${accent}`,
      }}
    >
      <div className="flex items-center justify-between">
        <span className="mono text-[0.6875rem] text-[var(--color-text-faint)]">
          exec #{claim.execution_id}
        </span>
        <span className="mono text-[0.625rem] text-[var(--color-text-faint)]">
          #{claim.id}
          {(claim.verification_count ?? 0) > 0 && ` · ${claim.verification_count}✓`}
        </span>
      </div>

      <p className="mono text-[0.8125rem] leading-relaxed" style={{ color: "var(--color-text)" }}>
        {claim.claim_text}
      </p>

      <div className="flex gap-1.5 flex-wrap">
        {VERDICTS.map((v) => {
          const active = claim.verdict === v;
          return (
            <Button
              key={v}
              variant={active ? "primary" : "ghost"}
              onClick={() => onVerdict(v)}
              disabled={busy || active}
              className="!text-[0.625rem] !px-2.5 !py-1.5"
            >
              {v}
            </Button>
          );
        })}
      </div>

      {resolved && (
        <p className="label text-[0.625rem]" style={{ color: "var(--color-text-faint)" }}>
          pick another verdict to override
        </p>
      )}
    </div>
  );
}
