/** The footer's one line on what a page called: live runs and check results used real models and sandboxes. */
export function footerNote(path: string): string {
  return /^\/(live|check)\/[^/]+/.test(path)
    ? 'Live mode: this run called real models and sandboxes.'
    : 'Replay mode: recorded runs, no models called.';
}
