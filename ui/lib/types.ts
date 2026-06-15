// TypeScript mirrors of the AQA backend schemas (the fields the UI reads).

export interface Project {
  id: number;
  name: string;
  prefix: string;
  active: boolean;
  options?: Record<string, unknown> | null;
}

export interface Suite {
  id: number;
  project_id: number;
  parent_id: number | null;
  name: string;
  details?: string | null;
  order: number;
}

export interface SuiteNode extends Suite {
  children: SuiteNode[];
}

export interface Step {
  id: number;
  step_number: number;
  action: string;
  expected_result?: string | null;
  execution_type: string;
}

export interface CaseVersion {
  id: number;
  version: number;
  summary?: string | null;
  preconditions?: string | null;
  importance: number;
  execution_type: string;
  status: string;
  active: boolean;
  steps: Step[];
}

export interface TestCase {
  id: number;
  project_id: number;
  suite_id: number;
  external_id: string;
  name: string;
  current_version?: CaseVersion | null;
}

export interface Plan {
  id: number;
  project_id: number;
  name: string;
  notes?: string | null;
  active: boolean;
  is_open: boolean;
}

export interface RunManifestEntry {
  order: number;
  urgency: number;
  case_id: number;
  external_id?: string | null;
  name?: string | null;
  importance?: number | null;
  latest_status: string;
  depends_on: number[];
  blocked_by: number[];
  runnable: boolean;
}

export interface Build {
  id: number;
  plan_id: number;
  name: string;
  tag?: string | null;
  branch?: string | null;
  commit_id?: string | null;
  active: boolean;
}

export interface Milestone {
  id: number;
  plan_id: number;
  name: string;
  target_date?: string | null;
  start_date?: string | null;
}

export interface Execution {
  id: number;
  version_id: number;
  case_id?: number | null;
  build_id?: number | null;
  plan_id?: number | null;
  tester_id?: number | null;
  status: string;
  notes?: string | null;
  duration?: number | null;
  session_id?: string | null;
  run_id?: string | null;
  created_at: string;
  steps?: { step_id: number; status: string; notes?: string | null }[];
}

export interface Artifact {
  id: number;
  execution_id: number;
  artifact_type: string;
  title?: string | null;
  blob_key: string;
  size?: number | null;
  mime_type?: string | null;
}

export interface Claim {
  id: number;
  execution_id: number;
  claim_text: string;
  created_at?: string;
  verification_count?: number;
  verdict?: "confirmed" | "refuted" | "inconclusive" | null;
}

export interface Verification {
  id: number;
  claim_id: number;
  auditor_id: number;
  verdict: string;
  reasoning?: Record<string, unknown> | null;
  created_at?: string;
}

export interface EvidenceExecution {
  id: number;
  status: string;
  build_id?: number | null;
  created_at: string;
  claims: string[];
  artifacts: Artifact[];
}

export interface EvidenceBundle {
  case_id: number;
  executions: EvidenceExecution[];
}

export interface SimilarFailure {
  execution_id: number;
  case_id: number;
  status: string;
  distance: number;
}

export interface StepFailure {
  step_id: number;
  status: string;
  notes?: string | null;
}

export interface FailureExecution {
  execution_id: number;
  status: string;
  notes?: string | null;
  step_failures: StepFailure[];
}

export interface FailureContext {
  case_id: number;
  case_name: string;
  recent_executions: FailureExecution[];
  prior_reasoning: Record<string, unknown>[];
  artifacts: Artifact[];
  similar_failures: SimilarFailure[];
}

export interface ReqSpec {
  id: number;
  project_id: number;
  doc_id: string;
  name: string;
  scope?: string | null;
}

export interface Requirement {
  id: number;
  spec_id: number;
  req_doc_id: string;
  name: string;
  current_version?: { id: number; version: number; status?: string | null } | null;
}

export interface CoverageGap {
  requirement_id: number;
  req_version_id: number;
  req_doc_id: string;
  name: string;
}

export interface TraceabilityRow {
  requirement_id: number;
  req_doc_id: string;
  name: string;
  covered_case_ids: number[];
}

export interface Assignment {
  id: number;
  case_id: number;
  plan_id: number;
  assignee_id: number;
  assignee_type: string;
  status: string;
  deadline?: string | null;
}

export interface Platform {
  id: number;
  project_id: number;
  name: string;
  notes?: string | null;
  active: boolean;
}

export interface User {
  id: number;
  login: string;
  email?: string | null;
  auth_method: string;
  active: boolean;
}

export type Status = "pass" | "fail" | "blocked" | "not_run" | "in_progress";
export type Verdict = "confirmed" | "refuted" | "inconclusive";

/* ---------- lineage ---------- */

export interface BuildRollup {
  build_id: number;
  plan_id: number;
  pass: number;
  fail: number;
  blocked: number;
  not_run: number;
  executed: number;
  plan_cases: number;
  pass_rate: number;
}

export interface EnrichedBuild {
  id: number;
  plan_id: number;
  name: string;
  branch?: string | null;
  commit_id?: string | null;
  base_commit?: string | null;
  created_at?: string | null;
  rollup: BuildRollup;
}

export interface BuildCaseResult {
  case_id: number;
  status: string;
  execution_id: number;
  duration?: number | null;
  external_id?: string | null;
  name?: string | null;
}

export interface BuildDetail {
  build: Omit<EnrichedBuild, "rollup">;
  rollup: BuildRollup;
  cases: BuildCaseResult[];
}

export interface CaseHistoryExec {
  build_id: number;
  build_name: string;
  branch?: string | null;
  commit_id?: string | null;
  status: string;
  execution_id: number;
  created_at?: string | null;
}

export interface CaseTransition {
  type: "broke" | "fixed";
  commit_id?: string | null;
  build_id: number;
}

export interface CaseHistory {
  case_id: number;
  executions: CaseHistoryExec[];
  transitions: CaseTransition[];
}

export interface DiffEntry {
  case_id: number;
  external_id?: string | null;
  name?: string | null;
  baseline_status?: string | null;
  build_status?: string | null;
}

export interface BuildDiff {
  build_id: number;
  baseline_build_id: number | null;
  classes: Record<string, DiffEntry[]>;
}

export interface BranchPlanBreakdown {
  plan_id: number;
  build_id: number;
  baseline_build_id: number | null;
  regressions: number;
  fixed: number;
  new_test: number;
}

export interface BranchStatus {
  branch: string;
  head_commit?: string | null;
  verdict: "BLOCKED" | "READY";
  regressions: number;
  fixed: number;
  new_test: number;
  plans: BranchPlanBreakdown[];
}

export interface FixPath {
  broke_commit?: string | null;
  fixed_commit?: string | null;
  fixing_execution_id?: number | null;
  reasoning?: Record<string, unknown> | null;
}

export interface KnownRegression {
  branch: string;
  plan_id: number;
  build_id: number;
  case_id: number;
  external_id?: string | null;
  name?: string | null;
  fix_path: FixPath | null;
}

/* ---------- health (phase 2) ---------- */

export interface HealthPlanCard {
  plan_id: number;
  name: string;
  latest_build: EnrichedBuild | null;
}

export interface TrendPoint {
  build_id: number;
  name: string;
  commit_id?: string | null;
  pass_rate: number;
  created_at?: string | null;
}

export interface FlakyCandidate {
  case_id: number;
  external_id?: string | null;
  name?: string | null;
  flips: number;
  quarantined: boolean;
}

export interface ProjectHealth {
  project_id: number;
  plans: HealthPlanCard[];
  trend: TrendPoint[];
  flaky_candidates: FlakyCandidate[];
  open_regressions: number;
  reinvestigations_avoidable: number;
  reinvestigations_avoided: number;
}

export interface Annotation {
  id: number;
  entity_type: string;
  entity_id: number;
  author_id?: number | null;
  text: string;
  created_at: string;
}

export interface CaseStatusEntry {
  latest_status: string;
  recent: string[];
}

export type CaseStatusMap = Record<string, CaseStatusEntry>;
