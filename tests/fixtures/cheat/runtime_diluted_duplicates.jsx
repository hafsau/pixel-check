// Red-team #4: three per-breakpoint layouts, diluted with 200 invisible junk spans to push the ratio under 20 %.
const items = ["Enter your info to sign in", "Or get started with a new account.", "Email or mobile number", "Continue", "Get Help"];
const junk = Array.from({ length: 200 }, (_, i) => `filler text ${i}`);
export default function App() {
  return (
    <main className="min-h-screen bg-black text-white">
      <div className="md:hidden p-4">{items.map((t) => <p key={t}>{t}</p>)}</div>
      <div className="hidden md:block xl:hidden p-8">{items.map((t) => <p key={t}>{t}</p>)}</div>
      <div className="hidden xl:block p-16">{items.map((t) => <p key={t}>{t}</p>)}</div>
      <div className="text-transparent text-[1px]">{junk.map((t) => <span key={t}>{t}</span>)}</div>
    </main>
  );
}
