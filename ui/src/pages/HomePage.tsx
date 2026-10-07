import { HowItWorks } from '../components/HowItWorks';
import { RunList } from '../components/RunList';
import { LiveRunPanel } from '../components/LiveRunPanel';
import { HeroSweep } from '../components/hero/HeroSweep';
import { CheckTeaser } from '../components/CheckTeaser';

export function HomePage() {
  return (
    <div className="page">
      <HeroSweep />
      <HowItWorks />
      <RunList />
      <LiveRunPanel />
      <CheckTeaser />
    </div>
  );
}
