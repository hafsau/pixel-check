// Red-team r2 #5: every element pinned at measured offsets in one stacked grid cell (not a layout).
const items = [["Enter your info to sign in", "mt-[114px] md:mt-[114px] xl:mt-[130px] ml-[22px] md:ml-[166px] xl:ml-[422px] text-3xl"],
  ["Or get started with a new account.", "mt-[198px] md:mt-[158px] xl:mt-[174px] ml-[21px] md:ml-[165px] xl:ml-[421px]"],
  ["Continue", "mt-[307px] md:mt-[268px] xl:mt-[284px] ml-[20px] md:ml-[164px] xl:ml-[420px] w-[350px] md:w-[440px] h-12 bg-[#e50914]"],
  ["Get Help", "mt-[406px] md:mt-[368px] xl:mt-[384px] ml-[20px] md:ml-[164px] xl:ml-[420px]"]];
export default function App() {
  return (
    <main className="grid min-h-screen bg-black text-white">
      {items.map(([t, c]) => <div key={t} className={`[grid-area:1/1] self-start justify-self-start ${c}`}>{t}</div>)}
    </main>
  );
}
