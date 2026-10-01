import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Candidate, Run } from './types';

/** Milliseconds per candidate at 1×. */
export const STEP_MS = 1400;
export const SPEEDS = [1, 4] as const;
export type Speed = (typeof SPEEDS)[number];

export interface PlaybackState {
  /** Index into run.candidates of the candidate being shown. */
  index: number;
  total: number;
  playing: boolean;
  speed: Speed;
  shown: Candidate;
  /** Highest round whose candidates have all been revealed (-1 = none yet). */
  completedRound: number;
  /** Best candidate as of the last completed round (null while round 0 is still running). */
  best: Candidate | null;
  /** Match history up to the completed round. */
  history: number[];
  play: () => void;
  pause: () => void;
  toggle: () => void;
  setSpeed: (s: Speed) => void;
  seek: (i: number) => void;
  step: (d: number) => void;
  selectCandidate: (id: string) => void;
}

/**
 * Replays a run candidate by candidate. The "current best" only advances when a whole
 * round has been revealed, mirroring how the loop selects at round end.
 */
export function usePlayback(run: Run, startAtEnd = false): PlaybackState {
  const total = run.candidates.length;
  const [index, setIndex] = useState(startAtEnd ? total - 1 : 0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(1);

  const byId = useMemo(() => new Map(run.candidates.map((c) => [c.id, c])), [run]);
  const lastIndexOfRound = useMemo(() => {
    const m = new Map<number, number>();
    run.candidates.forEach((c, i) => m.set(c.round, i));
    return m;
  }, [run]);

  useEffect(() => {
    if (!playing) return;
    if (index >= total - 1) {
      setPlaying(false);
      return;
    }
    const t = window.setTimeout(() => setIndex((i) => Math.min(total - 1, i + 1)), STEP_MS / speed);
    return () => window.clearTimeout(t);
  }, [playing, index, speed, total]);

  const completedRound = useMemo(() => {
    let r = -1;
    for (const round of [...lastIndexOfRound.keys()].sort((a, b) => a - b)) {
      if ((lastIndexOfRound.get(round) ?? Infinity) <= index) r = round;
      else break;
    }
    return r;
  }, [lastIndexOfRound, index]);

  const best = useMemo(() => {
    if (completedRound < 0) return null;
    const rs = run.rounds.find((r) => r.round === completedRound);
    return (rs && byId.get(rs.best)) ?? null;
  }, [completedRound, run, byId]);

  const history = useMemo(() => {
    const h = run.result.history?.length ? run.result.history : run.rounds.map((r) => r.match);
    return h.slice(0, completedRound + 1);
  }, [run, completedRound]);

  const seek = useCallback((i: number) => setIndex(Math.max(0, Math.min(total - 1, i))), [total]);
  const step = useCallback(
    (d: number) => {
      setPlaying(false);
      setIndex((i) => Math.max(0, Math.min(total - 1, i + d)));
    },
    [total],
  );
  const play = useCallback(() => {
    setIndex((i) => (i >= total - 1 ? 0 : i));
    setPlaying(true);
  }, [total]);
  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => (playing ? pause() : play()), [playing, pause, play]);
  const selectCandidate = useCallback(
    (id: string) => {
      const i = run.candidates.findIndex((c) => c.id === id);
      if (i >= 0) {
        setPlaying(false);
        setIndex(i);
      }
    },
    [run],
  );

  return {
    index,
    total,
    playing,
    speed,
    shown: run.candidates[Math.min(index, total - 1)],
    completedRound,
    best,
    history,
    play,
    pause,
    toggle,
    setSpeed,
    seek,
    step,
    selectCandidate,
  };
}

/** Ids on the path from the final best candidate back to its root. */
export function bestPath(run: Run): Set<string> {
  const byId = new Map(run.candidates.map((c) => [c.id, c]));
  const out = new Set<string>();
  let cur = byId.get(run.result.best);
  while (cur && !out.has(cur.id)) {
    out.add(cur.id);
    cur = cur.parent ? byId.get(cur.parent) : undefined;
  }
  return out;
}

/** "auto#0" → "auto"; keeps the label short for the tree. */
export function strategyLabel(s: string | null): string {
  if (!s) return 'candidate';
  return s.replace(/#\d+$/, '');
}
