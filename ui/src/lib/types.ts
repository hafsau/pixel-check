// Shapes of the replay bundle written by tools/export_run.py.

export type BpName = 'mobile' | 'tablet' | 'desktop' | (string & {});
export type PerBp = Partial<Record<BpName, number>>;

export interface RunSummary {
  id: string;
  title: string;
  match: number;
  per_bp: PerBp;
  created: number; // unix seconds
}

export interface Breakpoint {
  name: BpName;
  width: number;
  height: number;
}

export interface RunResult {
  stop_reason: string | null;
  match: number;
  per_bp: PerBp;
  best: string;
  spend_usd: number;
  spend_model_usd?: number | null;
  spend_sandbox_usd?: number | null;
  wall_s: number;
  history: number[];
}

export interface RoundSummary {
  round: number;
  best: string;
  match: number;
  spend_usd: number;
}

export interface Candidate {
  id: string;
  parent: string | null;
  round: number;
  strategy: string | null;
  match: number;
  mean: number;
  per_bp: PerBp;
  worst: BpName | null;
  disqualified: boolean;
  reason: string | null;
  checkpoint: string | null;
  sandbox_cost: number;
  renders: Partial<Record<BpName, string>>;
  code: string | null;
  components?: Partial<Record<BpName, Record<string, number>>> | null;
  fluidity?: Fluidity | null;
  controls?: Controls | null;
}

export interface Strategy {
  title: string | null;
  instructions: string | null;
}

export interface Critique {
  round: number;
  parent: string | null;
  diagnosis: string | null;
  strategies: Strategy[];
  feedback: string | null;
}

export interface EditBatch {
  round: number;
  kind: 'auto' | 'class' | 'tools';
  applied: number | null;
  edits: unknown[];
}

export interface ModelCall {
  t: number;
  step: string;
  model: string;
  thinking: string | null;
  in: number;
  out: number;
  usd: number;
  latency_s: number;
}

export interface Run {
  type?: 'static';
  id: string;
  title: string;
  label?: string | null;
  page?: string;
  cfg?: Record<string, unknown>;
  pipeline?: Pipeline;
  created: number;
  models: Record<string, string>;
  breakpoints: Breakpoint[];
  design: Partial<Record<BpName, string>>;
  result: RunResult;
  rounds: RoundSummary[];
  candidates: Candidate[];
  critiques: Critique[];
  edits: EditBatch[];
  calls: ModelCall[];
  /** Owned sites only (lib/owned.ts sanitises both; absent in older bundles = null). */
  display?: Display | null;
  real?: Partial<Record<BpName, string>> | null;
}

/** The delivered App.jsx of an owned site: the scored code with the page's own images back in the grey boxes. */
export interface Display {
  code: string;
  assets: string[];
  images: number;
  candidate: string | null;
}

/** How a candidate ended up: scored, disqualified by the gates, or never rendered. */
export type CandidateStatus = 'scored' | 'disqualified' | 'no-render';

export function candidateStatus(c: Candidate): CandidateStatus {
  if (c.disqualified) return 'disqualified';
  if (!c.checkpoint && Object.keys(c.renders).length === 0) return 'no-render';
  return 'scored';
}

// ---------------------------------------------------------------------------------------------
// Static-run extras (tools/export_run.py, Oct 5 schema). All optional: older bundles lack them.

export interface FluidWidth {
  overflow: number;
  overlaps: number;
  centre_drift: number;
  max_gap: number;
  bg_covers: boolean;
  ok: boolean;
}

export interface Fluidity {
  pass: boolean;
  fails: string[];
  widths: Record<string, FluidWidth>;
}

export interface Controls {
  inputs?: number;
  inputs_typeable?: number;
  buttons?: number;
  buttons_focusable?: number;
  links?: number;
  links_with_href?: number;
  clickable_divs?: number;
}

export interface Pipeline {
  compiler: 'fluid' | 'scaffold' | null;
  intent_plan: { cards: { name: string | null; count: number }[]; bands: Record<string, string>; dropped: unknown[]; usd: number | null } | null;
  structure_plans: { tags: Record<string, string>; applied: number | null; segments: number | null }[];
  intent_adoption: { winner: string; adopted: boolean; match: number; fluid_fails: number } | null;
}

// ---------------------------------------------------------------------------------------------
// Replay index (ui/public/runs/index.json). Entries without "type" come from the Oct 1 exporter.

export type BundleType = 'static' | 'interaction' | 'group';

export interface StaticEntry {
  type: 'static';
  id: string;
  title: string;
  label?: string | null;
  page?: string;
  match: number;
  per_bp: PerBp;
  created: number;
  usd?: number | null;
  fluid_pass?: boolean | null;
  thumb?: string | null;
}

export interface InteractionEntryVariant {
  writer: string;
  pass: boolean;
  attempts: number;
  usd: number | null;
  state_scores: PerBp;
}

export interface InteractionEntry {
  type: 'interaction';
  id: string;
  title: string;
  page: string;
  state: string;
  kind: string | null;
  created: number;
  bps: BpName[];
  variants: InteractionEntryVariant[];
  thumb?: string | null;
}

export interface GroupEntry {
  type: 'group';
  id: string;
  title: string;
  page: string;
  created: number;
  given: string | null;
  held: string[];
  review?: string | null;
  variants: { planner: string; notes: string | null; oracle: boolean; held_out_pass: number; held_out_total: number; held_out_delta: number }[];
  thumb?: string | null;
}

export type IndexEntry = StaticEntry | InteractionEntry | GroupEntry;

// ---------------------------------------------------------------------------------------------
// Interaction bundle (tools/export_interaction.py → interaction.json)

export type ScenarioSlot = 'base' | 'open' | 'closed' | 'esc' | 'kbd';

export interface CheckScore {
  bp: BpName;
  check: 'opens' | 'closes' | 'escape' | 'keyboard' | (string & {});
  score: number;
}

export interface SandboxRun {
  op_id: string | null;
  status: string | null;
  elapsed_s: number | null;
  wall_s: number | null;
  cost: number | null;
}

export interface SandboxTotals {
  runs: number;
  vm_s: number;
  wall_s: number;
  usd: number;
}

export interface Attempt {
  attempt: number;
  pass: boolean;
  infra: boolean;
  failures: string[];
  state_scores: PerBp;
  base_scores: PerBp;
  checks: CheckScore[];
  sections: Record<string, string>;
  code: string | null;
  sandbox: SandboxRun | null;
  captures: Partial<Record<BpName, Partial<Record<ScenarioSlot, string>>>>;
  panels?: Partial<Record<BpName, unknown>>;
}

export type Writer = 'template' | 'nemotron' | (string & {});

export interface Variant {
  key: string;
  writer: Writer;
  source: 'sandbox' | 'local';
  oracle: boolean;
  pass: boolean;
  best_attempt: number | null;
  model_usd: number | null;
  sandbox_usd: number | null;
  usd: number | null;
  seconds: number | null;
  kind?: string | null;
  base_expected: PerBp;
  sandbox: SandboxTotals;
  static: { renders: Partial<Record<BpName, string>>; sandbox: SandboxTotals } | null;
  attempts: Attempt[];
}

export interface RepeatRun {
  name: string;
  pass: boolean;
  best_attempt: number | null;
  attempts: number;
  first_pass_attempt: number | null;
  usd: number | null;
  model_usd: number | null;
  sandbox_usd: number | null;
  seconds: number | null;
  matches_variant: string | null;
  attempt_scores: { pass: boolean; state_scores: PerBp; failures: string[] }[];
}

export interface RepeatSet {
  label: string;
  writer: Writer;
  source: string;
  runs: RepeatRun[];
}

export interface Interaction {
  type: 'interaction';
  id: string;
  title: string;
  page: string;
  state: string;
  kind: string | null;
  created: number;
  breakpoints: Breakpoint[];
  design: Partial<Record<BpName, { base: string | null; state: string | null }>>;
  trigger: Partial<Record<BpName, [number, number, number, number] | null>>;
  writer_model?: string;
  variants: Variant[];
  repeats: RepeatSet[];
}

// ---------------------------------------------------------------------------------------------
// Sibling-group bundle (tools/export_group.py → group.json)

export interface GroupMember {
  scores: PerBp;
  delta: PerBp;
  pass: boolean;
  held_out: boolean;
  planned: boolean;
}

export interface GroupVariant {
  key: string;
  planner: string;
  notes: string | null;
  oracle: boolean;
  kind: string | null;
  held_out_pass: number;
  held_out_total: number;
  held_out_mean: number;
  held_out_delta: number;
  base_scores: PerBp;
  members: Record<string, GroupMember>;
  failures: string[];
  model_usd: number | null;
  sandbox_usd: number | null;
  seconds: number | null;
  sandbox: SandboxTotals;
  renders: Partial<Record<BpName, Record<string, string>>>;
  code: string | null;
  plan: { trigger: number | string | null; content: string[] }[];
}

export interface Group {
  type: 'group';
  id: string;
  title: string;
  page: string;
  created: number;
  review: string | null;
  breakpoints: Breakpoint[];
  members: string[];
  given: string | null;
  held: string[];
  design: Partial<Record<BpName, Record<string, string>>>;
  variants: GroupVariant[];
}
