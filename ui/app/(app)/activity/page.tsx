"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { Execution } from "@/lib/types";
import {
  EmptyState,
  Grid,
  Select,
  Spinner,
  Stat,
  StatusBadge,
  statusColor,
} from "@/components/ui";

interface FeedEntry extends Execution {
  planName: string;
}

type StatusFilter = "all" | "pass" | "fail" | "blocked";

export default function ActivityPage() {
  const { currentProject } = useApp();
  const [feed, setFeed] = useState<FeedEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("all");

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    (async () => {
      const plans = await api.plans(currentProject.id);
      const execLists = await Promise.all(
        plans.map((p) =>
          api
            .planExecutions(p.id)
            .then((execs) => execs.map((e) => ({ ...e, planName: p.name })))
            .catch(() => [] as FeedEntry[]),
        ),
      );
      const merged = execLists
        .flat()
        .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
      setFeed(merged);
      setLoading(false);
    })();
  }, [currentProject]);

  if (!currentProject)
    return <EmptyState title="no project selected" hint="create one in Admin" />;
  if (loading) return <Spinner label="loading activity feed" />;

  const total = feed.length;
  const pass = feed.filter((e) => e.status === "pass").length;
  const fail = feed.filter((e) => e.status === "fail").length;
  const blocked = feed.filter((e) => e.status === "blocked").length;

  const visible =
    filter === "all" ? feed : feed.filter((e) => e.status === filter);

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="mono text-lg font-semibold tracking-wide">
            AGENT ACTIVITY
          </h1>
          <p className="label mt-0.5">
            {currentProject.name} · execution timeline
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="label">filter</span>
          <Select
            value={filter}
            onChange={(e) => setFilter(e.target.value as StatusFilter)}
            className="!w-36"
          >
            <option value="all">all statuses</option>
            <option value="pass">pass</option>
            <option value="fail">fail</option>
            <option value="blocked">blocked</option>
          </Select>
        </div>
      </div>

      {/* stat tiles */}
      <Grid cols={4}>
        <Stat label="total executions" value={total} />
        <Stat label="passing" value={pass} color="var(--color-pass)" />
        <Stat label="failing" value={fail} color="var(--color-fail)" />
        <Stat label="blocked" value={blocked} color="var(--color-blocked)" />
      </Grid>

      {/* timeline feed */}
      {visible.length === 0 ? (
        <EmptyState
          title="no executions match"
          hint={filter !== "all" ? `try removing the ${filter} filter` : undefined}
        />
      ) : (
        <div className="relative">
          {/* vertical spine */}
          <div
            className="absolute left-[9px] top-0 bottom-0 w-px"
            style={{ background: "var(--color-border-bright)" }}
          />

          <div className="space-y-0">
            {visible.map((entry, idx) => {
              const isFail = entry.status === "fail";
              const isBlocked = entry.status === "blocked";
              const dotColor = statusColor(entry.status);
              const rowTint = isFail
                ? "border-l-2"
                : isBlocked
                  ? "border-l-2"
                  : "";
              const borderVar = isFail
                ? "var(--color-fail)"
                : isBlocked
                  ? "var(--color-blocked)"
                  : "transparent";

              return (
                <div
                  key={`${entry.id}-${idx}`}
                  className={`relative flex items-start gap-4 pl-8 pr-4 py-3 transition-colors hover:bg-[var(--color-bg-elev-2)] ${rowTint}`}
                  style={{
                    borderLeft: (isFail || isBlocked)
                      ? `2px solid ${borderVar}`
                      : undefined,
                    background:
                      isFail
                        ? "color-mix(in srgb, var(--color-fail) 4%, transparent)"
                        : isBlocked
                          ? "color-mix(in srgb, var(--color-blocked) 4%, transparent)"
                          : undefined,
                  }}
                >
                  {/* timeline dot */}
                  <span
                    className="absolute left-[5px] top-[18px] flex h-[9px] w-[9px] items-center justify-center"
                  >
                    <span
                      className="block h-[9px] w-[9px] rounded-full border-2"
                      style={{
                        borderColor: dotColor,
                        background:
                          entry.status === "pass"
                            ? dotColor
                            : "var(--color-bg)",
                        boxShadow: `0 0 6px -1px ${dotColor}`,
                      }}
                    />
                  </span>

                  {/* status badge */}
                  <div className="flex-shrink-0 pt-0.5 w-28">
                    <StatusBadge status={entry.status} />
                  </div>

                  {/* main content */}
                  <div className="flex flex-1 items-center gap-6 min-w-0">
                    <span
                      className="mono text-sm font-semibold flex-shrink-0"
                      style={{ color: "var(--color-text)" }}
                    >
                      #{entry.id}
                    </span>

                    <span
                      className="label flex-shrink-0 truncate max-w-[180px]"
                      title={entry.planName}
                      style={{ color: "var(--color-text-dim)" }}
                    >
                      {entry.planName}
                    </span>

                    <div className="flex items-center gap-4 flex-shrink-0">
                      <span className="mono text-[0.75rem] text-[var(--color-text-faint)]">
                        v{entry.version_id}
                      </span>
                      {entry.build_id && (
                        <span className="mono text-[0.75rem] text-[var(--color-text-faint)]">
                          b{entry.build_id}
                        </span>
                      )}
                      {entry.run_id && (
                        <span
                          className="mono text-[0.625rem] border px-1.5 py-0.5 uppercase tracking-wider"
                          style={{
                            borderColor: "var(--color-border-bright)",
                            color: "var(--color-text-faint)",
                          }}
                        >
                          {entry.run_id.slice(0, 8)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* timestamp */}
                  <span className="mono text-[0.6875rem] text-[var(--color-text-faint)] flex-shrink-0 pt-0.5">
                    {new Date(entry.created_at).toLocaleString()}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
