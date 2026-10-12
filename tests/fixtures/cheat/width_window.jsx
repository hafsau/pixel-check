// Red team (Oct 12): a class that applies only in a 2 px window around a frame's exact width — pinned to the
// measured size, invisible to the width sweep. Arbitrary breakpoint variants are banned.
export default function App() {
  return (
    <main className="p-4">
      <h1 className="mt-[10px] min-[402px]:max-[403px]:mt-[37px] min-[1071px]:max-[1072px]:mt-[91px]">Welcome back</h1>
    </main>
  );
}
