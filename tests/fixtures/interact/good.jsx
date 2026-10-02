import { useState, useEffect } from "react";

export default function App() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div className="min-h-screen bg-[#0b0b0b] font-sans">
      <div className="flex flex-row items-center justify-between px-[20px] h-[80px]">
        <span className="text-[20px] text-white font-bold">Brand</span>
        <button type="button" data-trigger="menu" aria-label="Open menu" aria-expanded={open} aria-controls="menu-panel"
                onClick={() => setOpen((o) => !o)} className="w-[40px] h-[34px] bg-[#e7e6d9]" />
      </div>
      <p className="px-[20px] mt-[100px] text-[40px] text-white">Hero title</p>
      {open && (
        <div id="menu-panel" className="fixed inset-x-0 top-[80px] bottom-0 bg-[#0b0b0b] px-[20px] pt-[40px]">
          <a href="#" className="block text-[16px] text-white">AI FACTORIES</a>
          <a href="#" className="block mt-[30px] text-[16px] text-white">PRICING</a>
        </div>
      )}
    </div>
  );
}
