import { useEffect, useState } from "react";
import Owner from "./Owner.jsx";
import Customer from "./Customer.jsx";

// Two screens, picked by the URL hash: #/owner (default) and #/customer.
export default function App() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const on = () => setHash(location.hash);
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  const customer = hash === "#/customer";
  return (
    <div className="mx-auto max-w-5xl p-4">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">Garba Returns Desk</h1>
        <nav className="flex gap-2 text-sm">
          <a href="#/owner" className={`rounded px-3 py-1 ${!customer ? "bg-stone-900 text-white" : "bg-stone-200"}`}>Owner</a>
          <a href="#/customer" className={`rounded px-3 py-1 ${customer ? "bg-stone-900 text-white" : "bg-stone-200"}`}>Customer</a>
        </nav>
      </header>
      <p className="mb-4 rounded bg-amber-100 px-3 py-2 text-sm text-amber-900">
        SIMULATED DATA: every customer, order and refund here is fake seed data. No real money moves.
      </p>
      {customer ? <Customer /> : <Owner />}
    </div>
  );
}
