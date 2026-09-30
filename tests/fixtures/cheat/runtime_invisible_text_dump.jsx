// Red-team #1: every target string dumped as invisible text to farm text credit.
const dump = ["Enter your info to sign in", "Or get started with a new account.", "Email or mobile number", "Continue", "Get Help", "Questions? Call", "FAQ", "Help Center"];
export default function App() {
  return (
    <main className="min-h-screen bg-black">
      <div className="h-[48px] w-[440px] mx-auto mt-[284px] bg-[#e50914]" />
      <div className="opacity-[0.01]">{dump.map((t) => <span key={t}>{t}</span>)}</div>
    </main>
  );
}
