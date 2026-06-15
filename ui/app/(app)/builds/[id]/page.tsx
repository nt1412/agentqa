"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BuildDetail } from "@/lib/types";
import {
  Button,
  Cell,
  CommitRef,
  EmptyState,
  Grid,
  Panel,
  Row,
  Select,
  Spinner,
  Stat,
  StatusBadge,
  Table,
} from "@/components/ui";

function RerunControl({
  buildId,
  caseId,
  agents = [],
}: {
  buildId: number;
  caseId?: number;
  agents?: { id: number; login: string }[];
}) {
  const [assignee, setAssignee] = useState<number | "">("");
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setAssignee((a) => (a === "" ? agents[0]?.id ?? "" : a));
  }, [agents]);

  async function go() {
    if (assignee === "") return;
    setBusy(true);
    try {
      const created = await api.requestRerun(buildId, Number(assignee), caseId);
      setDone(`queued ${created.length}`);
    } catch {
      setDone("failed");
    } finally {
      setBusy(false);
    }
  }

  if (done) return <span className="label !text-[var(--color-accent)]">re-run {done} ✓</span>;
  return (
    <div className="flex items-center gap-2">
      <Select
        value={assignee}
        onChange={(e) => setAssignee(e.target.value === "" ? "" : Number(e.target.value))}
        className="!w-auto !py-1.5 !text-[0.75rem]"
      >
        {agents.length === 0 && <option value="">no agents</option>}
        {agents.map((a) => (
          <option key={a.id} value={a.id}>
            {a.login}
          </option>
        ))}
      </Select>
      <Button variant="ghost" onClick={go} disabled={busy || assignee === ""}>
        {busy ? "…" : caseId ? "re-run case" : "re-run build"}
      </Button>
    </div>
  );
}

export default function BuildDetailPage() {
  const params = useParams();
  const router = useRouter();
  const buildId = Number(params.id);
  const [detail, setDetail] = useState<BuildDetail | null>(null);
  const [agents, setAgents] = useState<{ id: number; login: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .buildDetail(buildId)
      .then(setDetail)
      .finally(() => setLoading(false));
    api.agents().then(setAgents).catch(() => setAgents([]));
  }, [buildId]);

  if (loading) return <Spinner label="loading build" />;
  if (!detail) return <EmptyState title="build not found" />;

  const { build, rollup, cases } = detail;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="mono text-lg font-semibold tracking-wide">{build.name}</h1>
          <div className="mt-1 flex items-center gap-3">
            <CommitRef sha={build.commit_id} branch={build.branch} />
            {build.base_commit && (
              <span className="label !text-[var(--color-text-faint)]">
                base {build.base_commit.slice(0, 7)}
              </span>
            )}
            <span className="label !text-[var(--color-text-faint)]">
              {build.created_at ? new Date(build.created_at).toLocaleString() : ""}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => router.push(`/builds/${buildId}/compare`)}>
            compare → baseline
          </Button>
          <RerunControl buildId={buildId} agents={agents} />
        </div>
      </div>

      <Grid cols={5}>
        <Stat label="pass rate" value={`${rollup.pass_rate}%`} color={rollup.fail ? "var(--color-fail)" : "var(--color-pass)"} />
        <Stat label="passing" value={rollup.pass} color="var(--color-pass)" />
        <Stat label="failing" value={rollup.fail} color="var(--color-fail)" />
        <Stat label="blocked" value={rollup.blocked} color="var(--color-blocked)" />
        <Stat label="not run" value={rollup.not_run} color="var(--color-notrun)" hint={`of ${rollup.plan_cases} in plan`} />
      </Grid>

      <Panel title="case results (latest in this build)" pad={false}>
        {cases.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no results recorded for this build" />
          </div>
        ) : (
          <Table head={["id", "case", "status", "duration", ""]}>
            {cases.map((c) => (
              <Row key={c.case_id} onClick={() => router.push(`/evidence/${c.case_id}`)}>
                <Cell mono className="text-[var(--color-text-faint)]">
                  {c.external_id}
                </Cell>
                <Cell>{c.name}</Cell>
                <Cell>
                  <StatusBadge status={c.status} />
                </Cell>
                <Cell mono className="text-[var(--color-text-faint)]">
                  {c.duration != null ? `${c.duration}ms` : "—"}
                </Cell>
                <Cell>
                  <div onClick={(e) => e.stopPropagation()}>
                    <RerunControl buildId={buildId} caseId={c.case_id} agents={agents} />
                  </div>
                </Cell>
              </Row>
            ))}
          </Table>
        )}
      </Panel>
    </div>
  );
}
