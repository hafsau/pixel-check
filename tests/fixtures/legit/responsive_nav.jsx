const links = ["Docs", "Pricing", "Blog"];
const plans = [["Starter", "$0", "For individuals"], ["Team", "$24", "For small teams"], ["Scale", "$96", "For companies"]];
export default function App() {
  return (
    <main className="min-h-screen bg-white px-6 py-6 md:px-12">
      <header className="flex items-center justify-between">
        <span className="font-semibold">Acme</span>
        <nav className="hidden md:flex gap-6 text-sm">{links.map((l) => <a key={l}>{l}</a>)}</nav>
        <button className="md:hidden rounded border px-3 py-1 text-sm">Menu</button>
      </header>
      <div className="md:hidden mt-2 flex gap-4 text-xs text-slate-500">{links.map((l) => <a key={l}>{l}</a>)}</div>
      <h1 className="mt-10 text-3xl font-bold xl:text-5xl">Simple pricing for every team</h1>
      <p className="mt-3 text-slate-600">Start free. Upgrade when you need more seats, projects or support.</p>
      <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {plans.map(([n, p, d]) => (
          <div key={n} className="relative rounded-xl border p-5">
            {n === "Team" && <span className="absolute right-4 top-4 rounded bg-indigo-100 px-2 text-xs">Popular</span>}
            <div className="text-sm text-slate-500">{n}</div>
            <div className="mt-1 text-2xl font-semibold">{p}<span className="text-sm">/mo</span></div>
            <p className="mt-2 text-sm">{d}</p>
            <button className="mt-4 w-full rounded-lg bg-indigo-600 py-2 text-white">Choose {n}</button>
          </div>
        ))}
      </section>
    </main>
  );
}
