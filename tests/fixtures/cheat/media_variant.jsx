// Red team (Oct 12): an arbitrary @media variant targeting one exact width.
export default function App() {
  return (
    <main className="p-4">
      <h1 className="text-[20px] [@media(width:1071px)]:text-[41px] max-md:text-[19px]">Welcome back</h1>
    </main>
  );
}
