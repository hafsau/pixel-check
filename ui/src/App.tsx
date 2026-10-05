import { matchPath, usePath } from './lib/router';
import { SiteHeader } from './components/SiteHeader';
import { SiteFooter } from './components/SiteFooter';
import { HomePage } from './pages/HomePage';
import { RunPage } from './pages/RunPage';
import { ResultPage } from './pages/ResultPage';
import { NotFound } from './pages/NotFound';
import { InteractionPage } from './pages/InteractionPage';
import { GroupPage } from './pages/GroupPage';
import { LiveRunPage } from './pages/LiveRunPage';

function Routes() {
  const path = usePath();
  if (path === '/' || path === '') return <HomePage />;
  let m = matchPath('/run/:id/result', path);
  if (m) return <ResultPage key={m.id} id={m.id} />;
  m = matchPath('/live/:id/result', path);
  if (m) return <LiveRunPage key={`${m.id}-r`} id={m.id} result />;
  m = matchPath('/live/:id', path);
  if (m) return <LiveRunPage key={m.id} id={m.id} />;
  m = matchPath('/interaction/:id', path);
  if (m) return <InteractionPage key={m.id} id={m.id} />;
  m = matchPath('/group/:id', path);
  if (m) return <GroupPage key={m.id} id={m.id} />;
  m = matchPath('/run/:id', path);
  if (m) return <RunPage key={m.id} id={m.id} />;
  return <NotFound />;
}

export default function App() {
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:shadow-card">
        Skip to content
      </a>
      <SiteHeader />
      <main id="main" tabIndex={-1} className="pb-8 outline-none">
        <Routes />
      </main>
      <SiteFooter />
    </>
  );
}
