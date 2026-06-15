"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { EnrichedBuild, Plan } from "@/lib/types";
import {
  Cell,
  CommitRef,
  EmptyState,
  Panel,
  RollupBar,
  Row,
  Select,
  Spinner,
  Table,
} from "@/components/ui";

export default function BuildsPage() {
  const { currentProject } = useApp();
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [planId, setPlanId] = useState<number | null>(null);
  const [builds, setBuilds] = useState<EnrichedBuild[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!currentProject) return;
    (async () => {
      const ps = await api.plans(currentProject.id);
      setPlans(ps);
      setPlanId(ps[0]?.id ?? null);
    })();
  }, [currentProject]);

  useEffect(() => {
    if (planId === null) return;
    setLoading(true);
    (async () => {
      try {
        setBuilds(await api.buildTimeline(planId));
      } finally {
        setLoading(false);
      }
    })();
  }, [planId]);

  if (!currentProject) return <EmptyState title="no project selected" hint="choose one above" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">build timeline</h1>
        <p className="label mt-0.5">{currentProject.prefix} · run → build → commit lineage</p>
      </div>

      <Panel
        title="builds"
        pad={false}
        actions={
          plans.length > 0 && (
            <Select
              value={planId ?? ""}
              onChange={(e) => setPlanId(Number(e.target.value))}
              className="!w-auto !py-1 !text-[0.8125rem]"
            >
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          )
        }
      >
        {loading ? (
          <div className="p-4">
            <Spinner label="loading builds" />
          </div>
        ) : builds.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no builds in this plan" hint="record a run to populate the timeline" />
          </div>
        ) : (
          <Table head={["build", "commit", "result", "tests", "when"]}>
            {builds.map((b) => (
              <Row key={b.id} onClick={() => router.push(`/builds/${b.id}`)}>
                <Cell mono>{b.name}</Cell>
                <Cell>
                  <CommitRef
                    sha={b.commit_id}
                    branch={b.branch}
                    repoUrl={currentProject.options?.repo_url as string | undefined}
                  />
                </Cell>
                <Cell>
                  <RollupBar rollup={b.rollup} />
                </Cell>
                <Cell mono className="text-[var(--color-text-dim)]">
                  <span style={{ color: "var(--color-pass)" }}>{b.rollup.pass}</span>
                  {" / "}
                  <span style={{ color: b.rollup.fail ? "var(--color-fail)" : undefined }}>
                    {b.rollup.fail}
                  </span>
                  {" / "}
                  <span style={{ color: b.rollup.blocked ? "var(--color-blocked)" : undefined }}>
                    {b.rollup.blocked}
                  </span>
                  <span className="text-[var(--color-text-faint)]"> · {b.rollup.plan_cases}</span>
                </Cell>
                <Cell mono className="text-[var(--color-text-faint)]">
                  {b.created_at ? new Date(b.created_at).toLocaleString() : "—"}
                </Cell>
              </Row>
            ))}
          </Table>
        )}
      </Panel>
      <p className="label !text-[var(--color-text-faint)]">
        tests column: <span style={{ color: "var(--color-pass)" }}>pass</span> /{" "}
        <span style={{ color: "var(--color-fail)" }}>fail</span> /{" "}
        <span style={{ color: "var(--color-blocked)" }}>blocked</span> · plan size
      </p>
    </div>
  );
}
