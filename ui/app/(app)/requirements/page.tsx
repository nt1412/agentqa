"use client";

import Link from "next/link";
import { Fragment, useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { CoverageGap, Requirement, ReqSpec, TraceabilityRow } from "@/lib/types";
import {
  Cell,
  EmptyState,
  Grid,
  Panel,
  Row,
  Spinner,
  Stat,
  StatusBadge,
  Table,
  Tag,
} from "@/components/ui";

export default function RequirementsPage() {
  const { currentProject } = useApp();

  const [specs, setSpecs] = useState<ReqSpec[]>([]);
  const [selectedSpec, setSelectedSpec] = useState<ReqSpec | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [gaps, setGaps] = useState<CoverageGap[]>([]);
  const [coverage, setCoverage] = useState<Record<number, number[]>>({});
  const [expandedReq, setExpandedReq] = useState<number | null>(null);
  const [loadingSpecs, setLoadingSpecs] = useState(true);
  const [loadingReqs, setLoadingReqs] = useState(false);

  // Load specs + gaps + traceability (req → covered cases) when project changes
  useEffect(() => {
    if (!currentProject) return;
    setLoadingSpecs(true);
    setSelectedSpec(null);
    setRequirements([]);
    setExpandedReq(null);
    (async () => {
      const [specsData, gapsData, traceData] = await Promise.all([
        api.reqSpecs(currentProject.id).catch(() => [] as ReqSpec[]),
        api.coverageGaps(currentProject.id).catch(() => [] as CoverageGap[]),
        api.traceability(currentProject.id).catch(() => [] as TraceabilityRow[]),
      ]);
      setSpecs(specsData);
      setGaps(gapsData);
      setCoverage(
        Object.fromEntries(traceData.map((t) => [t.requirement_id, t.covered_case_ids])),
      );
      setLoadingSpecs(false);
    })();
  }, [currentProject]);

  // Load requirements when spec is selected
  useEffect(() => {
    if (!selectedSpec) {
      setRequirements([]);
      return;
    }
    setLoadingReqs(true);
    api
      .requirements(selectedSpec.id)
      .then((data) => {
        setRequirements(data);
        setLoadingReqs(false);
      })
      .catch(() => {
        setRequirements([]);
        setLoadingReqs(false);
      });
  }, [selectedSpec]);

  if (!currentProject) return <EmptyState title="no project selected" hint="create one in Admin" />;
  if (loadingSpecs) return <Spinner label="loading requirements" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">requirements manager</h1>
        <p className="label mt-0.5">{currentProject.name} · specification coverage</p>
      </div>

      <Grid cols={3}>
        <Stat
          label="specifications"
          value={specs.length}
        />
        <Stat
          label="requirements"
          value={selectedSpec ? requirements.length : "—"}
          hint={selectedSpec ? `in ${selectedSpec.doc_id}` : "select a spec"}
        />
        <Stat
          label="coverage gaps"
          value={gaps.length}
          color={gaps.length > 0 ? "var(--color-fail)" : "var(--color-pass)"}
        />
      </Grid>

      <div className="grid grid-cols-[280px_1fr] gap-6">
        {/* Left panel: spec list */}
        <Panel title="req specs">
          {specs.length === 0 ? (
            <EmptyState title="no specs found" hint="add specs via the backend" />
          ) : (
            <div className="space-y-2">
              {specs.map((spec) => {
                const isSelected = selectedSpec?.id === spec.id;
                return (
                  <button
                    key={spec.id}
                    type="button"
                    onClick={() => setSelectedSpec(isSelected ? null : spec)}
                    className="w-full text-left border px-3 py-2.5 transition-colors"
                    style={{
                      borderColor: isSelected
                        ? "var(--color-accent)"
                        : "var(--color-border)",
                      background: isSelected
                        ? "color-mix(in srgb, var(--color-accent) 8%, transparent)"
                        : "var(--color-bg-elev)",
                    }}
                  >
                    <div className="mono text-sm" style={{ color: isSelected ? "var(--color-accent)" : "var(--color-text)" }}>
                      {spec.doc_id}
                    </div>
                    <div className="label mt-0.5 truncate">{spec.name}</div>
                    {spec.scope && (
                      <div
                        className="mono mt-1 text-[0.625rem] truncate"
                        style={{ color: "var(--color-text-faint)" }}
                      >
                        {spec.scope}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </Panel>

        {/* Right panel: requirements for selected spec */}
        <Panel
          title={
            selectedSpec
              ? `requirements · ${selectedSpec.doc_id}`
              : "requirements"
          }
          pad={false}
        >
          {!selectedSpec ? (
            <div className="p-4">
              <EmptyState title="select a spec to view requirements" />
            </div>
          ) : loadingReqs ? (
            <div className="p-4">
              <Spinner label="loading requirements" />
            </div>
          ) : requirements.length === 0 ? (
            <div className="p-4">
              <EmptyState title="no requirements in this spec" />
            </div>
          ) : (
            <Table head={["req id", "name", "version", "status", "coverage"]}>
              {requirements.map((req) => {
                const ver = req.current_version;
                const covered = coverage[req.id] ?? [];
                const isOpen = expandedReq === req.id;
                return (
                  <Fragment key={req.id}>
                    <Row onClick={() => setExpandedReq(isOpen ? null : req.id)}>
                      <Cell mono>{req.req_doc_id}</Cell>
                      <Cell>{req.name}</Cell>
                      <Cell mono>
                        {ver ? `v${ver.version}` : <span style={{ color: "var(--color-text-faint)" }}>—</span>}
                      </Cell>
                      <Cell>
                        {ver?.status ? (
                          <StatusBadge status={ver.status} />
                        ) : (
                          <Tag>draft</Tag>
                        )}
                      </Cell>
                      <Cell mono>
                        <span
                          style={{
                            color:
                              covered.length > 0
                                ? "var(--color-pass)"
                                : "var(--color-fail)",
                          }}
                        >
                          {covered.length > 0
                            ? `${covered.length} case${covered.length === 1 ? "" : "s"}`
                            : "gap"}
                        </span>
                        <span
                          className="ml-2 inline-block text-[var(--color-text-faint)] transition-transform"
                          style={{ transform: isOpen ? "rotate(90deg)" : "none" }}
                        >
                          ›
                        </span>
                      </Cell>
                    </Row>
                    {isOpen && (
                      <tr>
                        <td colSpan={5} className="px-3 pb-3 pt-1 bg-[var(--color-bg-elev-2)]">
                          <div className="label mb-1.5">covered by test cases</div>
                          {covered.length === 0 ? (
                            <p className="label italic" style={{ color: "var(--color-fail)" }}>
                              coverage gap — no test cases linked to this requirement
                            </p>
                          ) : (
                            <div className="flex flex-wrap gap-2">
                              {covered.map((cid) => (
                                <Link
                                  key={cid}
                                  href={`/cases/${cid}`}
                                  className="mono text-[0.75rem] border px-2 py-1 transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
                                  style={{
                                    borderColor: "var(--color-border-bright)",
                                    color: "var(--color-text-dim)",
                                  }}
                                >
                                  case #{cid} →
                                </Link>
                              ))}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </Table>
          )}
        </Panel>
      </div>
    </div>
  );
}
