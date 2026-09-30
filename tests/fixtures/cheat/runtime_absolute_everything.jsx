const boxes = [[60, 40, "Pricing"], [60, 120, "Starter"], [400, 120, "Team"], [740, 120, "Scale"], [60, 300, "FAQ"]];
export default function App() {
  return (
    <main className="relative h-screen">
      {boxes.map(([x, y, t]) => <div key={t} className="absolute" style={{ left: x, top: y }}>{t}</div>)}
    </main>
  );
}
