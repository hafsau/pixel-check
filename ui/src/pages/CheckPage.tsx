import { CheckPanel } from '../components/CheckPanel';

/** /check — the "Check a build" form. */
export function CheckPage() {
  return (
    <div className="page pt-6">
      <p className="eyebrow mb-3">Check mode</p>
      <CheckPanel />
    </div>
  );
}
