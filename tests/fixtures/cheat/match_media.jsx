import { useEffect, useState } from "react";
export default function App() {
  const [w, setW] = useState(1280);
  useEffect(() => setW(window.innerWidth), []);
  return w < 768 ? <div>Mobile layout</div> : <div>Desktop layout</div>;
}
