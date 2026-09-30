// Self-test screen: exercises fonts, colours, and md:/xl: layout changes.
export default function App() {
  const plans = [["Starter", "$0"], ["Team", "$24"], ["Scale", "$96"]];
  return (
    <main className="min-h-screen bg-white text-slate-900 px-6 py-8 md:px-12 xl:px-24">
      <header className="flex items-center justify-between">
        <span className="text-lg font-semibold">Pixel-Check</span>
        <nav className="hidden md:flex gap-6 text-sm text-slate-600"><a>Docs</a><a>Pricing</a><a>Sign in</a></nav>
      </header>
      <h1 className="mt-10 text-3xl md:text-4xl xl:text-5xl font-bold tracking-tight">One codebase. Every breakpoint.</h1>
      <p className="mt-3 font-mono text-sm text-slate-500">render.mjs --selftest</p>
      <section className="mt-8 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {plans.map(([name, price]) => (
          <div key={name} className="rounded-xl border border-slate-200 p-5">
            <div className="text-sm font-medium text-slate-500">{name}</div>
            <div className="mt-2 text-2xl font-semibold">{price}<span className="text-sm text-slate-400">/mo</span></div>
            <button className="mt-4 w-full rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white">Choose</button>
          </div>
        ))}
      </section>
    </main>
  );
}
