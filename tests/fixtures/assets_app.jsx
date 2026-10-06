import { useState } from "react";

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div data-pc="0" className="flow-root min-h-screen w-full font-sans bg-[#fafafa]">
      <div data-pc="1" data-seg="S12" className="flow-root w-full bg-transparent min-h-0 mt-[20px] xl:mt-[15px] pt-[0px]">
        <div data-pc="2" className="w-full max-w-none mx-0 pl-[24px] pr-[24px]">
          <div data-pc="3" className="flex flex-row flex-wrap justify-start pl-[0px] pr-[0px] items-start mt-[0px] w-full">
            <div data-pc="4" aria-hidden="true" className="hidden md:block w-[21px] max-w-full h-[18px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 md:mt-[3px] xl:mt-[8px] ml-0 md:ml-[0px] self-auto" />
            <a data-pc="5" href="x" className={`${menuOpen ? "block" : "hidden"} xl:block text-[13px] text-[#595959] font-semibold tracking-[0.016em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[10px] ml-0 xl:ml-[32px] self-auto whitespace-nowrap`}>Text</a>
            <div data-pc="6" aria-hidden="true" className="block md:hidden w-[21px] max-w-full h-[18px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-[3px] md:mt-0 ml-[0px] md:ml-0 self-auto" />
            <div data-pc="7" aria-hidden="true" className="hidden xl:block w-[14px] max-w-full h-[14px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[10px] ml-0 xl:ml-[2px] self-auto" />
            <a data-pc="8" href="x" className={`${menuOpen ? "block" : "hidden"} xl:block text-[13px] text-[#545454] font-normal tracking-[0.011em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[10px] ml-0 xl:ml-[20px] self-auto whitespace-nowrap`}>Text</a>
            <div data-pc="9" aria-hidden="true" className="hidden xl:block w-[14px] max-w-full h-[14px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[10px] ml-0 xl:ml-[3px] self-auto" />
            <a data-pc="10" href="x" className={`${menuOpen ? "block" : "hidden"} xl:block text-[14px] text-[#595959] font-medium tracking-normal leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[9px] ml-0 xl:ml-[20px] self-auto whitespace-nowrap`}>Text</a>
            <a data-pc="11" href="x" className={`${menuOpen ? "block" : "hidden"} xl:block text-[14px] text-[#2c2c2c] font-normal tracking-[-0.027em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[9px] ml-0 xl:ml-[24px] self-auto whitespace-nowrap`}>Text</a>
            <button data-pc="12" type="button" className="hidden xl:flex w-[103px] max-w-full h-[34px] bg-[#ffffff] border-t border-r border-b border-l border-[#ebebeb] rounded-none shadow-none items-center gap-[8px] shrink-0 justify-center px-[12px] cursor-pointer text-left mt-0 xl:mt-[0px] ml-0 xl:ml-auto self-auto">
              <span data-pc="13" className="hidden xl:block text-[14px] text-[#1b1b1b] font-medium tracking-[-0.016em] leading-none text-left no-underline max-w-full min-w-0 whitespace-nowrap">Text</span>
            </button>
            <div data-pc="14" className="hidden xl:flex w-[67px] max-w-full h-[34px] bg-[#ffffff] border-t border-r border-b border-l border-[#ebebeb] rounded-none shadow-none items-center gap-[8px] shrink-0 justify-center px-[12px] mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto">
              <a data-pc="15" href="x" className={`${menuOpen ? "block" : "hidden"} xl:block text-[14px] text-[#2b2b2b] font-normal tracking-[0.04em] leading-none text-left no-underline max-w-full min-w-0 whitespace-nowrap`}>Text</a>
            </div>
            <button data-pc="16" type="button" className="hidden xl:flex w-[77px] max-w-full h-[32px] bg-[#171717] border-0 rounded-[7px] shadow-none items-center gap-[8px] shrink-0 justify-center px-[12px] cursor-pointer text-left mt-0 xl:mt-[1px] ml-0 xl:ml-[11px] self-auto">
              <span data-pc="17" className="hidden xl:block text-[14px] text-[#fcfcfc] font-semibold tracking-[-0.01em] leading-none text-left no-underline max-w-full min-w-0 whitespace-nowrap">Text</span>
            </button>
            <button data-pc="18" type="button" aria-label="x" aria-expanded={menuOpen} onClick={() => setMenuOpen((o) => !o)} className="block xl:hidden w-[24px] max-w-full h-[24px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 cursor-pointer mt-[0px] xl:mt-0 ml-auto xl:ml-0 self-auto" />
          </div>
        </div>
      </div>
      <div data-pc="19" data-seg="S13" className="flow-root w-full bg-transparent min-h-0 mt-[59px] md:mt-[92px] xl:mt-[135px] pt-[0px]">
        <div data-pc="20" className="w-full max-w-none xl:max-w-[1280px] mx-0 xl:mx-auto pl-[24px] md:pl-[26px] pr-[24px] md:pr-[26px]">
          <div data-pc="21" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] w-full">
            <h1 data-pc="22" className="text-[40px] md:text-[63px] text-[#171717] font-medium tracking-[-0.058em] md:tracking-[-0.051em] leading-[1.23] md:leading-[1.02] text-left no-underline max-w-[335px] md:max-w-[538px] min-w-0 mt-[0px] ml-[0px] self-auto">Text<br data-pc="23" className="inline" />Text</h1>
          </div>
        </div>
      </div>
      <div data-pc="24" data-seg="S14" className="flow-root w-full bg-transparent min-h-0 mt-[46px] md:mt-[62px] xl:mt-[72px] pt-[0px]">
        <div data-pc="25" className="w-full max-w-none xl:max-w-[1280px] mx-0 xl:mx-auto pl-[23px] xl:pl-[31px] pr-[23px] xl:pr-[31px]">
          <div data-pc="26" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] w-full">
            <div data-pc="27" data-seg="S15" className="grid grid-cols-1 xl:grid-cols-3 gap-x-0 xl:gap-x-[0px] gap-y-[0px] xl:gap-y-0 w-full bg-transparent xl:bg-[#fafafa] border-t-0 xl:border-t border-r-0 xl:border-r border-b-0 xl:border-b border-l-0 xl:border-l border-transparent xl:border-[#fefefe] rounded-none shadow-none shrink-0 items-stretch mt-[0px] ml-[0px] self-auto">
              <div data-pc="28" className="w-full min-h-[520px] xl:min-h-[436px] bg-[#fafafa] xl:bg-transparent border-t xl:border-t-0 border-r xl:border-r-0 border-b xl:border-b-0 border-l xl:border-l-0 border-[#fcfcfc] md:border-[#ffffff] xl:border-transparent rounded-none shadow-none shrink-0 flow-root">
                <div data-pc="29" className="flex flex-row flex-wrap justify-start xl:justify-end pl-0 pr-0 xl:pr-[0px] items-start mt-[1px] xl:mt-[0px] w-full">
                  <div data-pc="30" aria-hidden="true" className="w-full h-[1px] bg-[#e6e6e6] border-0 rounded-none shadow-none shrink-0 mt-[0px] ml-[2px] xl:ml-[0px] self-auto" />
                </div>
                <div data-pc="31" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[27px] xl:mt-[29px] w-full">
                  <h1 data-pc="32" className="text-[15px] text-[#1b1b1b] font-medium tracking-[-0.065em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] ml-[26px] self-auto whitespace-nowrap">Text</h1>
                </div>
                <div data-pc="33" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[22px] xl:mt-[17px] w-full">
                  <h1 data-pc="34" className="text-[34px] xl:text-[55px] text-[#171717] font-normal xl:font-medium tracking-[-0.08em] xl:tracking-[-0.062em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] ml-[27px] xl:ml-[28px] self-auto whitespace-nowrap">$0</h1>
                </div>
                <div data-pc="35" className="flex flex-row flex-wrap justify-start xl:justify-center pl-0 pr-0 items-start mt-[18px] w-full">
                  <p data-pc="36" className="text-[16px] text-[#5e5e5e] font-medium tracking-[-0.01em] leading-[1.5] text-left no-underline max-w-[286px] min-w-0 mt-[0px] ml-[25px] xl:ml-[0px] self-auto">Text<br data-pc="37" className="inline" />Text</p>
                </div>
                <div data-pc="38" className="flex flex-row flex-wrap justify-start xl:justify-center pl-0 pr-0 items-start mt-[51px] w-full">
                  <div data-pc="39" aria-hidden="true" className="w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-[0px] ml-[26px] xl:ml-[0px] self-auto" />
                  <p data-pc="40" className="text-[15px] text-[#2c2c2c] font-normal tracking-[-0.021em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] ml-[10px] self-auto">Text</p>
                </div>
                <div data-pc="41" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[16px] w-full">
                  <div data-pc="42" aria-hidden="true" className="w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-[0px] ml-[26px] self-auto" />
                  <p data-pc="43" className="text-[14px] text-[#2c2c2c] font-normal tracking-[0.018em] leading-none text-left no-underline max-w-full min-w-0 mt-[1px] ml-[10px] self-auto whitespace-nowrap">Text</p>
                </div>
                <div data-pc="44" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[16px] w-full">
                  <div data-pc="45" aria-hidden="true" className="w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-[0px] ml-[26px] self-auto" />
                  <p data-pc="46" className="text-[15px] text-[#2c2c2c] font-normal tracking-[-0.024em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] ml-[10px] self-auto whitespace-nowrap">Text</p>
                </div>
                <div data-pc="47" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[16px] w-full">
                  <div data-pc="48" aria-hidden="true" className="w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-[0px] ml-[26px] self-auto" />
                  <p data-pc="49" className="text-[15px] text-[#2d2d2d] font-normal tracking-[-0.046em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] ml-[10px] self-auto whitespace-nowrap">Text</p>
                </div>
                <div data-pc="50" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[16px] w-full">
                  <div data-pc="51" aria-hidden="true" className="w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-[0px] ml-[26px] self-auto" />
                  <p data-pc="52" className="text-[15px] text-[#2c2c2c] font-normal tracking-[-0.021em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] ml-[10px] self-auto whitespace-nowrap">Text</p>
                </div>
                <div data-pc="53" className="flex flex-row flex-wrap justify-start pl-0 pr-0 items-start mt-[16px] w-full">
                  <div data-pc="54" aria-hidden="true" className="w-[16px] max-w-full h-[16px] xl:h-[14px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-[0px] ml-[26px] self-auto" />
                  <p data-pc="55" className="text-[14px] text-[#2c2c2c] font-normal tracking-[-0.01em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] ml-[10px] self-auto whitespace-nowrap">Text</p>
                </div>
                <div data-pc="56" className="flex xl:hidden flex-row xl:flex-col flex-wrap xl:flex-nowrap justify-start pl-0 pr-0 items-start mt-[16px] xl:mt-[0px] w-full">
                  <div data-pc="57" aria-hidden="true" className="block xl:hidden w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-[0px] xl:mt-0 ml-[26px] xl:ml-0 self-auto" />
                  <p data-pc="58" className="block xl:hidden text-[14px] text-[#2c2c2c] font-normal tracking-[-0.017em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] xl:mt-0 ml-[10px] xl:ml-0 self-auto whitespace-nowrap">Text</p>
                </div>
                <div data-pc="59" className="flex xl:hidden flex-row xl:flex-col flex-wrap xl:flex-nowrap justify-start pl-0 pr-0 items-start mt-[34px] xl:mt-[0px] w-full">
                  <button data-pc="60" type="button" className="flex xl:hidden w-[139px] max-w-full h-[36px] bg-[#ffffff] border-0 rounded-none shadow-none items-center gap-[8px] shrink-0 justify-center px-[12px] cursor-pointer text-left mt-[0px] xl:mt-0 ml-[26px] xl:ml-0 self-auto">
                    <span data-pc="61" className="block xl:hidden text-[14px] text-[#1c1c1c] font-medium tracking-normal leading-none text-left no-underline max-w-full min-w-0 whitespace-nowrap">Text</span>
                  </button>
                </div>
              </div>
              <div data-pc="62" className="w-full min-h-[67px] md:min-h-[175px] xl:min-h-[413px] bg-[#ffffff] border-0 rounded-none shadow-none shrink-0 flow-root">
                <div data-pc="63" className="flex flex-col flex-nowrap justify-start pl-0 pr-0 items-start mt-[24px] xl:mt-[32px] w-full">
                  <h1 data-pc="64" className="text-[13px] text-[#242424] font-normal tracking-[0.073em] leading-none text-left no-underline max-w-full min-w-0 mt-[0px] ml-[24px] xl:ml-[32px] self-start order-[1] whitespace-nowrap">Text</h1>
                  <div data-pc="65" className="flex w-[58px] max-w-full h-[20px] bg-[#e8e8e8] xl:bg-[#e9e9e9] border-0 rounded-[10px] shadow-none items-center gap-[8px] shrink-0 justify-center px-[12px] mt-[0px] ml-[54px] xl:ml-[62px] self-start order-[0]">
                    <span data-pc="66" className="text-[12px] text-[#1c1c1c] font-normal tracking-[-0.007em] leading-none text-left no-underline max-w-full min-w-0 whitespace-nowrap">Text</span>
                  </div>
                </div>
                <div data-pc="67" className="hidden md:flex xl:hidden flex-col md:flex-row xl:flex-col flex-nowrap md:flex-wrap xl:flex-nowrap justify-start pl-0 pr-0 items-start mt-[0px] md:mt-[20px] xl:mt-[0px] w-full">
                  <h1 data-pc="68" className="hidden md:block xl:hidden text-[34px] text-[#171717] font-normal tracking-[-0.08em] leading-none text-left no-underline max-w-full min-w-0 mt-0 md:mt-[0px] xl:mt-0 ml-0 md:ml-[25px] xl:ml-0 self-auto whitespace-nowrap">$20</h1>
                  <span data-pc="69" className="hidden md:block xl:hidden text-[34px] text-[#171717] font-normal tracking-[-0.08em] leading-none text-left no-underline max-w-full min-w-0 mt-0 md:mt-[14px] xl:mt-0 ml-0 md:ml-[10px] xl:ml-0 self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="70" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[15px] w-full">
                  <p data-pc="71" className="hidden xl:block text-[55px] text-[#171717] font-medium tracking-[-0.057em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[34px] self-auto whitespace-nowrap">$20</p>
                </div>
                <div data-pc="72" className="flex flex-col md:flex-row flex-nowrap md:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] md:mt-[4px] xl:mt-[18px] w-full">
                  <p data-pc="73" className="text-[16px] text-[#5e5e5e] font-normal tracking-[-0.011em] leading-[1.5] text-left no-underline max-w-[197px] md:max-w-[213px] min-w-0 mt-0 md:mt-[0px] ml-0 md:ml-[23px] xl:ml-[31px] self-auto">Text<br data-pc="74" className="hidden md:inline" />Text</p>
                </div>
                <div data-pc="75" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[51px] w-full">
                  <span data-pc="76" className="hidden xl:block text-[15px] text-[#5a5a5a] font-normal tracking-[-0.021em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[32px] self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="77" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[17px] w-full">
                  <div data-pc="78" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[32px] self-auto" />
                  <span data-pc="79" className="hidden xl:block text-[13px] text-[#2c2c2c] font-normal tracking-[0.029em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[2px] ml-0 xl:ml-[10px] self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="80" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[16px] w-full">
                  <div data-pc="81" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[32px] self-auto" />
                  <span data-pc="82" className="hidden xl:block text-[15px] text-[#2c2c2c] font-normal tracking-[-0.019em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto">Text</span>
                </div>
                <div data-pc="83" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[16px] w-full">
                  <div data-pc="84" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[32px] self-auto" />
                  <span data-pc="85" className="hidden xl:block text-[15px] text-[#2c2c2c] font-normal tracking-[-0.026em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="86" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[16px] w-full">
                  <div data-pc="87" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[32px] self-auto" />
                  <span data-pc="88" className="hidden xl:block text-[15px] text-[#2c2c2c] font-normal tracking-[-0.051em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto">Text</span>
                </div>
                <div data-pc="89" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[16px] w-full">
                  <div data-pc="90" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[14px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[32px] self-auto" />
                  <span data-pc="91" className="hidden xl:block text-[15px] text-[#2c2c2c] font-normal tracking-[-0.022em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto whitespace-nowrap">Text</span>
                </div>
              </div>
              <div data-pc="92" className="hidden xl:block w-full min-h-[427px] bg-transparent border-0 rounded-none shadow-none shrink-0 flow-root">
                <div data-pc="93" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[24px] w-full">
                  <h1 data-pc="94" className="hidden xl:block text-[15px] text-[#1f1f1f] font-normal tracking-[-0.016em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[25px] self-auto whitespace-nowrap">Text</h1>
                </div>
                <div data-pc="95" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[18px] w-full">
                  <h1 data-pc="96" className="hidden xl:block text-[55px] text-[#171717] font-medium tracking-[-0.049em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[27px] self-auto whitespace-nowrap">Text</h1>
                </div>
                <div data-pc="97" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start xl:justify-center pl-0 pr-0 items-start mt-[0px] xl:mt-[17px] w-full">
                  <p data-pc="98" className="hidden xl:block text-[16px] text-[#616161] font-normal tracking-[0.01em] leading-[1.5] text-left no-underline max-w-[323px] xl:max-w-[349px] min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[0px] self-auto">Text<br data-pc="99" className="hidden xl:inline" />Text</p>
                </div>
                <div data-pc="100" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[51px] w-full">
                  <span data-pc="101" className="hidden xl:block text-[15px] text-[#5a5a5a] font-normal tracking-[-0.023em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[25px] self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="102" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[17px] w-full">
                  <div data-pc="103" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[25px] self-auto" />
                  <span data-pc="104" className="hidden xl:block text-[14px] text-[#2b2b2b] font-normal tracking-[-0.02em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="105" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[16px] w-full">
                  <div data-pc="106" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[25px] self-auto" />
                  <span data-pc="107" className="hidden xl:block text-[15px] text-[#2f2f2f] font-normal tracking-[-0.024em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="108" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[16px] w-full">
                  <div data-pc="109" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[25px] self-auto" />
                  <span data-pc="110" className="hidden xl:block text-[15px] text-[#2c2c2c] font-normal tracking-[-0.022em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="111" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[16px] w-full">
                  <div data-pc="112" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[25px] self-auto" />
                  <span data-pc="113" className="hidden xl:block text-[14px] text-[#2c2c2c] font-normal tracking-[-0.015em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto whitespace-nowrap">Text</span>
                </div>
                <div data-pc="114" className="hidden xl:flex flex-col xl:flex-row flex-nowrap xl:flex-wrap justify-start pl-0 pr-0 items-start mt-[0px] xl:mt-[16px] w-full">
                  <div data-pc="115" aria-hidden="true" className="hidden xl:block w-[16px] max-w-full h-[14px] bg-[#d4d4d8] border-0 rounded-none shadow-none shrink-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[25px] self-auto" />
                  <span data-pc="116" className="hidden xl:block text-[15px] text-[#343434] font-normal tracking-[-0.011em] leading-none text-left no-underline max-w-full min-w-0 mt-0 xl:mt-[0px] ml-0 xl:ml-[10px] self-auto whitespace-nowrap">Text</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
