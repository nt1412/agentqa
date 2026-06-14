"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { Claim } from "@/lib/types";
import {
  Button,
  EmptyState,
  Grid,
  Spinner,
  Stat,
  statusColor,
} from "@/components/ui";

type Verdict = "confirmed" | "refuted" | "inconclusive";

interface KanbanCard {
  claim: Claim;
  verdict: Verdict;
}

const COLUMNS: { key: "unverified" | Verdict; label: string; colorVar: string }[] = [
  { key: "unverified", label: "UNVERIFIED", colorVar: "var(--color-text-faint)" },
  { key: "confirmed", label: "CONFIRMED", colorVar: "var(--color-confirmed)" },
  { key: "refuted", label: "REFUTED", colorVar: "var(--color-refuted)" },
  { key: "inconclusive", label: "INCONCLUSIVE", colorVar: "var(--color-inconclusive)" },
];

export default function ClaimsPage() {
  const { currentProject } = useApp();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [resolved, setResolved] = useState<KanbanCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    api
      .unverifiedClaims()
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
    // optimistic: remove from unverified + add to resolved immediately
    setClaims((prev) => prev.filter((c) => c.id !== claim.id));
    setResolved((prev) => [...prev, { claim, verdict }]);
    setVerifying((prev) => new Set(prev).add(claim.id));

    try {
      await api.verifyClaim(claim.id, verdict);
    } catch {
      // rollback on failure
      setResolved((prev) => prev.filter((r) => r.claim.id !== claim.id));
      setClaims((prev) => [claim, ...prev]);
    } finally {
      setVerifying((prev) => {
        const next = new Set(prev);
        next.delete(claim.id);
        return next;
      });
    }
  }

  const confirmedCards = resolved.filter((r) => r.verdict === "confirmed");
  const refutedCards = resolved.filter((r) => r.verdict === "refuted");
  const inconclusiveCards = resolved.filter((r) => r.verdict === "inconclusive");

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">
          CLAIM AUDIT BOARD
        </h1>
        <p className="label mt-0.5">
          {currentProject.name} &middot; agent claim verification
        </p>
      </div>

      {/* stat */}
      <Grid cols={4}>
        <Stat
          label="unverified claims"
          value={claims.length}
          color={claims.length > 0 ? "var(--color-fail)" : "var(--color-pass)"}
          hint={claims.length === 0 ? "all clear" : "awaiting review"}
        />
        <Stat
          label="confirmed"
          value={confirmedCards.length}
          color="var(--color-confirmed)"
        />
        <Stat
          label="refuted"
          value={refutedCards.length}
          color="var(--color-refuted)"
        />
        <Stat
          label="inconclusive"
          value={inconclusiveCards.length}
          color="var(--color-inconclusive)"
        />
      </Grid>

      {/* kanban board */}
      <div className="grid grid-cols-4 gap-4 items-start">
        {/* UNVERIFIED column */}
        <KanbanColumn
          label={COLUMNS[0].label}
          colorVar={COLUMNS[0].colorVar}
          count={claims.length}
        >
          {claims.length === 0 ? (
            <EmptyState
              title="no unverified claims"
              hint="all claims have been audited"
            />
          ) : (
            <div className="space-y-2.5">
              {claims.map((claim) => (
                <UnverifiedCard
                  key={claim.id}
                  claim={claim}
                  busy={verifying.has(claim.id)}
                  onVerdict={(v) => handleVerdict(claim, v)}
                />
              ))}
            </div>
          )}
        </KanbanColumn>

        {/* CONFIRMED column */}
        <KanbanColumn
          label={COLUMNS[1].label}
          colorVar={COLUMNS[1].colorVar}
          count={confirmedCards.length}
        >
          {confirmedCards.length === 0 ? (
            <EmptyState title="none confirmed" />
          ) : (
            <div className="space-y-2">
              {confirmedCards.map(({ claim }) => (
                <ResolvedCard key={claim.id} claim={claim} verdict="confirmed" />
              ))}
            </div>
          )}
        </KanbanColumn>

        {/* REFUTED column */}
        <KanbanColumn
          label={COLUMNS[2].label}
          colorVar={COLUMNS[2].colorVar}
          count={refutedCards.length}
        >
          {refutedCards.length === 0 ? (
            <EmptyState title="none refuted" />
          ) : (
            <div className="space-y-2">
              {refutedCards.map(({ claim }) => (
                <ResolvedCard key={claim.id} claim={claim} verdict="refuted" />
              ))}
            </div>
          )}
        </KanbanColumn>

        {/* INCONCLUSIVE column */}
        <KanbanColumn
          label={COLUMNS[3].label}
          colorVar={COLUMNS[3].colorVar}
          count={inconclusiveCards.length}
        >
          {inconclusiveCards.length === 0 ? (
            <EmptyState title="none inconclusive" />
          ) : (
            <div className="space-y-2">
              {inconclusiveCards.map(({ claim }) => (
                <ResolvedCard key={claim.id} claim={claim} verdict="inconclusive" />
              ))}
            </div>
          )}
        </KanbanColumn>
      </div>
    </div>
  );
}

/* ---- Kanban Column ---- */
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
    <div
      className="flex flex-col gap-3 border-t-2 pt-3"
      style={{ borderColor: colorVar }}
    >
      {/* column header */}
      <div className="flex items-center justify-between">
        <span
          className="mono text-[0.6875rem] font-semibold uppercase tracking-widest"
          style={{ color: colorVar }}
        >
          {label}
        </span>
        <span
          className="mono text-[0.6875rem] border px-1.5 py-0.5 rounded-sm"
          style={{
            borderColor: colorVar,
            color: colorVar,
            opacity: 0.8,
          }}
        >
          {count}
        </span>
      </div>

      {children}
    </div>
  );
}

/* ---- Unverified Claim Card ---- */
function UnverifiedCard({
  claim,
  busy,
  onVerdict,
}: {
  claim: Claim;
  busy: boolean;
  onVerdict: (v: Verdict) => void;
}) {
  return (
    <div
      className="border p-3 flex flex-col gap-3"
      style={{
        borderColor: "var(--color-border-bright)",
        background: "var(--color-bg-elev)",
      }}
    >
      {/* exec id */}
      <div className="flex items-center justify-between">
        <span className="mono text-[0.6875rem] text-[var(--color-text-faint)]">
          exec #{claim.execution_id}
        </span>
        <span className="mono text-[0.625rem] text-[var(--color-text-faint)]">
          #{claim.id}
        </span>
      </div>

      {/* claim text */}
      <p
        className="mono text-[0.8125rem] leading-relaxed"
        style={{ color: "var(--color-text)" }}
      >
        {claim.claim_text}
      </p>

      {/* verdict buttons */}
      <div className="flex gap-1.5 flex-wrap">
        <Button
          variant="primary"
          onClick={() => onVerdict("confirmed")}
          disabled={busy}
          className="!text-[0.625rem] !px-2.5 !py-1.5"
        >
          confirm
        </Button>
        <Button
          variant="ghost"
          onClick={() => onVerdict("refuted")}
          disabled={busy}
          className="!text-[0.625rem] !px-2.5 !py-1.5"
        >
          refute
        </Button>
        <Button
          variant="ghost"
          onClick={() => onVerdict("inconclusive")}
          disabled={busy}
          className="!text-[0.625rem] !px-2.5 !py-1.5"
        >
          inconclusive
        </Button>
      </div>
    </div>
  );
}

/* ---- Resolved Claim Card ---- */
function ResolvedCard({
  claim,
  verdict,
}: {
  claim: Claim;
  verdict: Verdict;
}) {
  const color = statusColor(verdict);
  return (
    <div
      className="border px-3 py-2.5 opacity-80"
      style={{
        borderColor: "var(--color-border)",
        background: "var(--color-bg)",
        borderLeft: `2px solid ${color}`,
      }}
    >
      <div className="mono text-[0.625rem] text-[var(--color-text-faint)] mb-1">
        exec #{claim.execution_id} &middot; #{claim.id}
      </div>
      <p
        className="mono text-[0.75rem] leading-relaxed"
        style={{ color: "var(--color-text-dim)" }}
      >
        {claim.claim_text}
      </p>
    </div>
  );
}
