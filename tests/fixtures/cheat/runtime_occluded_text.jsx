// Red-team r2 #1: design copy parked under an opaque button; visible copy is lorem ipsum.
export default function App() {
  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white xl:px-[420px]">
      <h1 className="mt-10 text-3xl font-bold">Lorem ipsum dolor sit</h1>
      <p className="mt-3 text-[#acacac]">Consectetur adipiscing elit sed do.</p>
      <div className="mt-6 grid">
        <p className="[grid-area:1/1] text-[8px]">Enter your info to sign in Or get started with a new account. Email or mobile number Get Help</p>
        <button className="[grid-area:1/1] relative h-12 w-full rounded bg-[#e50914] font-medium">Tempor</button>
      </div>
    </main>
  );
}
