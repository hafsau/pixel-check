const items = ["Starter", "Team", "Scale", "Enterprise", "Get started", "Compare plans", "Talk to sales", "FAQ"];
export default function App() {
  return (
    <main>
      <div className="md:hidden flex flex-col gap-2">{items.map((t) => <p key={t}>{t}</p>)}</div>
      <div className="hidden md:grid xl:hidden grid-cols-2 gap-4">{items.map((t) => <p key={t}>{t}</p>)}</div>
      <div className="hidden xl:grid grid-cols-4 gap-8">{items.map((t) => <p key={t}>{t}</p>)}</div>
    </main>
  );
}
