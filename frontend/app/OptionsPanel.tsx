"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

type Calculation = {
  input: { strategy: string; symbol: string; currency: string; spot: string; strike: string; premium: string; fees: string; cost_basis: string | null; expiry: string; source: string; quote_at: string; goal: string };
  calculated_at: string; days_to_expiry: number; units: number;
  net_premium: string; premium_yield_pct: string; yield_basis: string;
  capital_reference: string; cash_required: string | null; effective_assignment_price: string;
  best_expiry_pl: string; max_loss: string; break_even: string | null;
  best_cost_basis_pl: string | null; cost_basis_break_even: string | null; cost_basis_max_loss: string | null;
  warnings: string[];
  scenarios: { price: string; option_pl: string; total_pl: string; cost_basis_pl: string | null; hold_shares_pl: string | null; assignment: string }[];
};
type Result = { calculation: Calculation; response?: string; ai_warning?: string | null; history_warning?: string };
type HistoryItem = { id: string; created_at: string; task_excerpt: string };
type Saved = { id: string; created_at: string; result: Result };
const API = "http://localhost:8000/agents/options";
const initial = {
  strategy: "covered_call", symbol: "", currency: "USD", spot: "", strike: "", premium: "",
  contracts: "1", contract_size: "100", fees: "0", expiry: "", quote_at: "", source: "",
  goal: "income", shares_owned: "", cost_basis: "", cash_available: "",
};
type Fields = typeof initial;
const inputClass = "mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-white disabled:opacity-50";
const buttonClass = "rounded-lg bg-blue-600 px-4 py-2 text-sm hover:bg-blue-500 disabled:opacity-40";
const goals: Record<string, string> = { income: "Præmieindtægt", keep_shares: "Beholde aktierne", sell_shares: "Sælge aktierne til strike", buy_shares: "Købe aktier til strike" };

async function readHistory(): Promise<HistoryItem[]> {
  const response = await fetch(API + "/history", { cache: "no-store" });
  if (!response.ok) throw new Error("Optionshistorikken kunne ikke indlæses.");
  return response.json();
}

export default function OptionsPanel({ online }: { online: boolean }) {
  const [fields, setFields] = useState<Fields>(initial);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [opening, setOpening] = useState(false);
  const [saved, setSaved] = useState<Saved | null>(null);

  useEffect(() => {
    let active = true;
    readHistory().then(data => { if (active) setItems(data); })
      .catch(() => { if (active) setHistoryError("Optionshistorikken kunne ikke indlæses."); })
      .finally(() => { if (active) setLoadingHistory(false); });
    return () => { active = false; };
  }, []);

  async function refresh() {
    setLoadingHistory(true); setHistoryError("");
    try { setItems(await readHistory()); }
    catch { setHistoryError("Optionshistorikken kunne ikke indlæses."); }
    finally { setLoadingHistory(false); }
  }

  function edit(key: keyof Fields, value: string) {
    setFields(current => ({ ...current, [key]: value }));
    setResult(null); setError("");
  }

  function example() {
    const now = new Date();
    const future = new Date(now);
    future.setDate(future.getDate() + 30);
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    setFields({ ...initial, symbol: "DEMO", spot: "100", strike: "105", premium: "2",
      fees: "5", shares_owned: "100", cost_basis: "95", cash_available: "11000",
      expiry: future.toISOString().slice(0, 10), quote_at: local,
      source: "Fiktivt regneeksempel – ikke markedsdata" });
    setConfirmed(false); setResult(null); setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const assess = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "run";
    setBusy(true); setResult(null); setError("");
    try {
      const payload = {
        ...fields, symbol: fields.symbol.trim(), source: fields.source.trim(),
        contracts: Number(fields.contracts), contract_size: Number(fields.contract_size),
        shares_owned: fields.strategy === "covered_call" ? Number(fields.shares_owned) : 0,
        cost_basis: fields.strategy === "covered_call" ? fields.cost_basis : null,
        cash_available: fields.strategy === "cash_secured_put" ? fields.cash_available : null,
        quote_at: new Date(fields.quote_at).toISOString(), standard_contract: confirmed,
      };
      const response = await fetch(API + (assess ? "/run" : "/calculate"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail :
          Array.isArray(body.detail) ? body.detail.map((item: { msg: string }) => item.msg).join(" ") :
          "Opgaven kunne ikke behandles.";
        throw new Error(detail);
      }
      setResult(body);
      if (assess) await refresh();
    } catch (failure) {
      setError(failure instanceof Error && !(failure instanceof TypeError) ? failure.message : "Kunne ikke forbinde til Options Agent.");
    } finally { setBusy(false); }
  }

  async function openSaved(id: string) {
    setOpening(true); setHistoryError(""); setSaved(null);
    try {
      const response = await fetch(API + "/history/" + encodeURIComponent(id), { cache: "no-store" });
      if (!response.ok) throw new Error("Det gemte resultat kunne ikke åbnes.");
      setSaved(await response.json());
    } catch { setHistoryError("Det gemte resultat kunne ikke åbnes."); }
    finally { setOpening(false); }
  }

  const numeric = (key: keyof Fields, label: string, min = "0", step = "0.0001") => (
    <label className="text-sm text-zinc-300" key={key}>{label}
      <input className={inputClass} type="number" required min={min} step={step}
        value={fields[key]} onChange={event => edit(key, event.target.value)} />
    </label>
  );

  return <section id="options-agent" className="mt-12 rounded-xl border border-blue-500/30 bg-zinc-900 p-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-xl font-semibold">Options Agent</h2>
      <button type="button" disabled={busy} onClick={example} className="text-sm text-blue-400 disabled:opacity-40">Indlæs fiktivt eksempel</button>
    </div>
    <p className="mt-2 text-sm text-zinc-400">Covered calls og cash-secured puts. Manuelle data, ingen Saxo-forbindelse eller ordreafgivelse.</p>
    <form onSubmit={submit} className="mt-5">
      <fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <legend className="sr-only">Handelsoplysninger</legend>
        <label className="text-sm text-zinc-300">Strategi
          <select className={inputClass} value={fields.strategy} onChange={e => edit("strategy", e.target.value)}>
            <option value="covered_call">Covered call</option><option value="cash_secured_put">Cash-secured put</option>
          </select>
        </label>
        <label className="text-sm text-zinc-300">Aktie / ticker
          <input className={inputClass} required maxLength={24} value={fields.symbol} onChange={e => edit("symbol", e.target.value)} />
        </label>
        <label className="text-sm text-zinc-300">Fælles valuta for alle beløb
          <select className={inputClass} value={fields.currency} onChange={e => edit("currency", e.target.value)}>
            {["USD", "DKK", "EUR", "GBP"].map(value => <option key={value}>{value}</option>)}
          </select>
        </label>
        {numeric("spot", "Aktuel aktiekurs", "0.0001")}
        {numeric("strike", "Strike pr. aktie", "0.0001")}
        {numeric("premium", "Forventet salgspræmie PR. AKTIE")}
        {numeric("contracts", "Antal solgte kontrakter", "1", "1")}
        {numeric("contract_size", "Aktier pr. kontrakt (kontrollér kontrakten)", "1", "1")}
        {numeric("fees", "Samlede gebyrer, inkl. evt. tildeling")}
        <label className="text-sm text-zinc-300">Udløbsdato
          <input className={inputClass} type="date" required value={fields.expiry} onChange={e => edit("expiry", e.target.value)} />
        </label>
        <label className="text-sm text-zinc-300">Kurstidspunkt (din lokale tid)
          <input className={inputClass} type="datetime-local" required value={fields.quote_at} onChange={e => edit("quote_at", e.target.value)} />
        </label>
        <label className="text-sm text-zinc-300">Datakilde / prisgrundlag
          <input className={inputClass} required maxLength={120} placeholder="Fx Saxo, bid-kurs" value={fields.source} onChange={e => edit("source", e.target.value)} />
        </label>
        {fields.strategy === "covered_call" ? <>
          {numeric("shares_owned", "Ejede aktier til rådighed som dækning", "1", "1")}
          {numeric("cost_basis", "Købspris pr. aktie for den dækkede del", "0.0001")}
        </> : numeric("cash_available", "Frie kontanter i valgt valuta")}
        <label className="text-sm text-zinc-300">Dit vigtigste mål
          <select className={inputClass} value={fields.goal} onChange={e => edit("goal", e.target.value)}>
            {Object.entries(goals).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="flex items-start gap-2 text-sm text-zinc-300 sm:col-span-2 lg:col-span-3">
          <input className="mt-1" type="checkbox" required checked={confirmed} onChange={e => { setConfirmed(e.target.checked); setResult(null); }} />
          Kontrakten er en ujusteret aktieoption med fysisk levering. Præmien er pr. aktie, og kontraktstørrelsen er kontrolleret. Indeksoptioner, spreads og justerede kontrakter understøttes ikke.
        </label>
        <div className="flex flex-wrap gap-3 sm:col-span-2 lg:col-span-3">
          <button type="submit" value="calculate" disabled={busy || !online} className={buttonClass}>Beregn</button>
          <button type="submit" value="run" disabled={busy || !online} className={buttonClass}>Beregn + AI-vurdering</button>
        </div>
      </fieldset>
    </form>
    <p className="mt-3 text-xs text-zinc-500">Beregn bruger ingen AI. Beregn + AI-vurdering gemmer input og resultat lokalt. AI-modellen modtager handelsoplysningerne via dit Codex-login.</p>
    {busy && <p role="status" className="mt-4 text-blue-300">Behandler opgaven… AI-vurdering kan tage op til 120 sekunder.</p>}
    {error && <p role="alert" className="mt-4 text-red-400">{error}</p>}
    {result && <Analysis result={result} />}
    <div className="mt-8 border-t border-zinc-700 pt-6">
      <div className="flex items-center justify-between gap-3"><h3 className="font-semibold">Optionshistorik</h3>
        <button type="button" disabled={loadingHistory || busy} onClick={refresh} className="text-sm text-blue-400 disabled:opacity-40">Opdatér</button>
      </div>
      <p className="my-2 text-xs text-zinc-500">Seneste 50 vurderinger. Input og svar gemmes lokalt i klartekst.</p>
      {loadingHistory && <p role="status">Indlæser…</p>}
      {historyError && <p role="alert" className="text-red-400">{historyError}</p>}
      {!loadingHistory && !historyError && items.length === 0 && <p className="text-sm text-zinc-400">Ingen gemte optionsvurderinger endnu.</p>}
      <ul className="space-y-2">{items.map(item => <li key={item.id} className="rounded-lg bg-zinc-950 p-3">
        <p className="text-xs text-zinc-500">{new Date(item.created_at).toLocaleString("da-DK")}</p>
        <p className="my-1 break-words text-sm">{item.task_excerpt}</p>
        <button type="button" disabled={opening} onClick={() => openSaved(item.id)} className="text-sm text-blue-400 disabled:opacity-40">Åbn gemt vurdering</button>
      </li>)}</ul>
      {opening && <p role="status">Åbner vurdering…</p>}
      {saved && <div className="mt-5 border-t border-zinc-700 pt-4">
        <h3 className="font-semibold">Gemt vurdering · {new Date(saved.created_at).toLocaleString("da-DK")}</h3>
        <Analysis result={saved.result} />
        <button type="button" onClick={() => setSaved(null)} className="mt-3 text-blue-400">Luk gemt vurdering</button>
      </div>}
    </div>
  </section>;
}

function Analysis({ result }: { result: Result }) {
  const c = result.calculation;
  const call = c.input.strategy === "covered_call";
  const money = (value: string | null) => value === null ? "Ingen break-even i modellen" :
    new Intl.NumberFormat("da-DK", { style: "currency", currency: c.input.currency }).format(Number(value));
  const cards: [string, string | null][] = [
    ["Nettopræmie efter gebyrer", c.net_premium],
    ["Bedste udløbsresultat" + (call ? " fra dagens kurs" : ""), c.best_expiry_pl],
    ["Maksimalt tab" + (call ? " fra dagens kurs" : ""), c.max_loss],
    ["Break-even" + (call ? " fra dagens kurs" : ""), c.break_even],
    [call ? "Aktiernes aktuelle værdi" : "Kontanter krævet inkl. gebyrer", call ? c.capital_reference : c.cash_required],
    [call ? "Effektiv salgspris pr. aktie ved tildeling" : "Effektiv købspris pr. aktie ved tildeling", c.effective_assignment_price],
  ];
  if (call) cards.push(["Bedste resultat fra købspris", c.best_cost_basis_pl],
    ["Break-even fra købspris", c.cost_basis_break_even], ["Maksimalt tab fra købspris", c.cost_basis_max_loss]);
  return <div className="mt-5 rounded-lg border border-zinc-700 bg-zinc-950 p-4">
    <h3 className="font-semibold">{c.input.symbol.toUpperCase()} · {call ? "Covered call" : "Cash-secured put"} · {c.units} aktier</h3>
    <p className="mt-2 text-sm text-zinc-400">Kurs {money(c.input.spot)} · Strike {money(c.input.strike)} · Præmie pr. aktie {money(c.input.premium)} · Udløb {c.input.expiry} ({c.days_to_expiry} dage ved beregning)</p>
    <p className="mt-1 text-sm text-zinc-400">Mål: {goals[c.input.goal]} · Gebyrer: {money(c.input.fees)}{call && <> · Købspris: {money(c.input.cost_basis)}</>}</p>
    <p className="mt-1 break-words text-xs text-zinc-500">Kilde: {c.input.source} · Kurstid: {new Date(c.input.quote_at).toLocaleString("da-DK")} · Beregnet: {new Date(c.calculated_at).toLocaleString("da-DK")}</p>
    <p className="mt-1 text-xs text-zinc-500">Kun de {c.units} kontraktdækkede aktier indgår. Før skat, uden udbytte, renter eller valutaeffekt.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{cards.map(([label, value]) => <div key={label} className="rounded-lg bg-zinc-900 p-3">
      <p className="text-xs text-zinc-400">{label}</p><p className="mt-1 font-semibold">{money(value)}</p>
    </div>)}</div>
    <p className="mt-3 text-sm text-zinc-300">Nettopræmie: {c.premium_yield_pct}% af {c.yield_basis.toLowerCase()} for perioden. Ikke forventet samlet afkast eller årsafkast.</p>
    <h4 className="mt-5 font-semibold">Scenarier ved udløb</h4>
    <div className="mt-2 overflow-x-auto"><table className="w-full text-left text-sm">
      <caption className="sr-only">Resultater ved alternative aktiekurser ved udløb</caption>
      <thead className="text-zinc-400"><tr><th className="p-2">Aktiekurs</th><th className="p-2">Option netto</th><th className="p-2">{call ? "Samlet fra dagens kurs" : "Samlet resultat"}</th>{call && <><th className="p-2">Samlet fra købspris</th><th className="p-2">Aktier uden call, fra i dag</th></>}<th className="p-2">Tildeling</th></tr></thead>
      <tbody>{c.scenarios.map((row, index) => <tr key={index} className="border-t border-zinc-800">
        <td className="p-2 whitespace-nowrap">{money(row.price)}</td><td className="p-2 whitespace-nowrap">{money(row.option_pl)}</td><td className="p-2 whitespace-nowrap">{money(row.total_pl)}</td>
        {call && <><td className="p-2 whitespace-nowrap">{money(row.cost_basis_pl)}</td><td className="p-2 whitespace-nowrap">{money(row.hold_shares_pl)}</td></>}
        <td className="p-2">{row.assignment}</td>
      </tr>)}</tbody>
    </table></div>
    <details className="mt-4" open><summary className="cursor-pointer text-sm font-semibold text-amber-300">Forudsætninger og risici</summary>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-400">{c.warnings.map(w => <li key={w}>{w}</li>)}</ul>
    </details>
    {result.history_warning && <p role="alert" className="mt-3 text-amber-300">{result.history_warning}</p>}
    {result.ai_warning && <p role="alert" className="mt-3 text-amber-300">Beregningen er klar, men AI-vurderingen mangler: {result.ai_warning}</p>}
    {result.response && <div className="mt-5 border-t border-zinc-700 pt-4"><h4 className="font-semibold">AI-vurdering · kontrollér mod tallene ovenfor</h4><p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-zinc-300">{result.response}</p></div>}
  </div>;
}
