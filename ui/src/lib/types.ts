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
  kind: 'auto' | 'class';
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
  id: string;
  title: string;
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
}

/** How a candidate ended up: scored, disqualified by the gates, or never rendered. */
export type CandidateStatus = 'scored' | 'disqualified' | 'no-render';

export function candidateStatus(c: Candidate): CandidateStatus {
  if (c.disqualified) return 'disqualified';
  if (!c.checkpoint && Object.keys(c.renders).length === 0) return 'no-render';
  return 'scored';
}
