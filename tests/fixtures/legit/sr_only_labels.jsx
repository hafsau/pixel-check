// Red-team r2 #3: accessible markup (screen-reader labels) must not be disqualified.
export default function App() {
  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white xl:px-[420px]">
      <button className="md:hidden"><span className="sr-only">Open menu</span>≡</button>
      <h1 className="mt-10 text-3xl font-bold">Enter your info to sign in</h1>
      <p className="mt-3 text-[#acacac]">Or get started with a new account.</p>
      <label className="sr-only" htmlFor="email">Email address field</label>
      <input id="email" placeholder="Email or mobile number" className="mt-6 h-[54px] w-full rounded bg-[#141414] px-4" />
      <button className="mt-3 h-12 w-full rounded bg-[#e50914] font-medium">Continue<span className="sr-only"> to next step</span></button>
      <a className="mt-8 block">Get Help<span className="sr-only"> (opens help centre)</span></a>
      <span className="sr-only">Skip to content</span><span className="sr-only">Site navigation</span><span className="sr-only">Footer links</span>
    </main>
  );
}
