import { useState } from "react";
import { Sheet } from "../../components/Sheet";
import { Panel, fmt } from "../../components/ui";
import type { ShopDepositResource, ShopDeposits } from "../../types";
import { Timer, parseAmount, type TabProps } from "./shared";

const pct = (r: number) => `${Math.round(r * 1000) / 10}%`;

export function DepositsTab({ data, run, busy }: TabProps & { data: ShopDeposits }) {
	const [open, setOpen] = useState(false);
	const [res, setRes] = useState<ShopDepositResource | null>(null);
	const [hours, setHours] = useState(data.terms[data.terms.length - 1]);
	const [raw, setRaw] = useState("");

	const coinsRes = data.resources.find((r) => r.code === "coins") ?? data.resources[0];
	const full = data.deposits.length >= data.max_active;
	const max = res ? Math.min(res.cap, res.have) : 0;
	const amount = parseAmount(raw);
	const valid = !!res && amount > 0 && amount <= max;
	const rate = res ? res.rates[String(hours)] ?? 0 : 0;

	const close = () => { setOpen(false); setRes(null); setRaw(""); };
	const submit = async () => {
		if (!res) return;
		const r = await run("/shop/deposit/open", { resource: res.code, hours, amount });
		if (r) close();
	};

	return (
		<>
			<Panel title="Ставки" tone="gold">
				<div className="shop-rates">
					{data.terms.map((h, i) => (
						<div key={h} className={`shop-rate ${i === data.terms.length - 1 ? "top" : ""}`}>
							<div className="disp">{pct(coinsRes?.rates[String(h)] ?? 0)}</div>
							{h} ч
						</div>
					))}
				</div>
				<div className="shop-note muted" style={{ marginTop: 10 }}>
					Ставки — для NHCoin, остальные ресурсы дают вдвое меньше. Забрать раньше срока можно — вернётся только тело вклада.
					До {data.max_active} вкладов одновременно.
				</div>
			</Panel>

			<Panel title="Сколько можно вложить">
				{data.resources.map((r) => (
					<div className="stat" key={r.code}>
						{r.name}
						<b>{fmt(r.cap)}</b>
					</div>
				))}
			</Panel>

			<button className={`btn block ${full ? "off" : "gold"}`} type="button" disabled={full || busy} onClick={() => setOpen(true)}>
				{full ? "Все слоты вкладов заняты" : "Открыть вклад"}
			</button>

			<Panel title="Активные вклады">
				{data.deposits.length === 0 ? (
					<div className="shop-empty">Активных вкладов нет.</div>
				) : (
					data.deposits.map((d) => (
						<div className="shop-cell" key={d.id}>
							<div className="shop-cell-head">
								<div className="grow">
									{d.name}: {fmt(d.amount)} → <span style={{ color: "var(--gold-2)" }}>{fmt(d.payout)}</span>
									<div className="sub">{d.hours} ч · +{pct(d.rate)} · {d.ready ? "готов" : <>ещё <Timer seconds={d.left_seconds} /></>}</div>
								</div>
								<button className={`btn small ${d.ready ? "green" : "ghost"}`} type="button" disabled={busy} onClick={() => run("/shop/deposit/claim", { id: d.id })}>
									{d.ready ? "Забрать" : "Досрочно"}
								</button>
							</div>
						</div>
					))
				)}
			</Panel>

			{open && (
				<Sheet title="Новый вклад" onClose={close}>
					<div className="shop-sheet-body">
						<div className="shop-label" style={{ margin: 0 }}>Ресурс</div>
						<div className="shop-pick">
							{data.resources.map((r) => (
								<button key={r.code} type="button" className={res?.code === r.code ? "on" : ""} onClick={() => { setRes(r); setRaw(""); }}>
									<span>{r.name}</span>
									<span className="muted">{fmt(r.have)} / до {fmt(r.cap)}</span>
								</button>
							))}
						</div>
						<div className="shop-label" style={{ margin: 0 }}>Срок</div>
						<div className="shop-pills">
							{data.terms.map((h) => (
								<button key={h} type="button" className={`pill ${h === hours ? "on" : ""}`} onClick={() => setHours(h)}>
									{h} ч{res ? ` · +${pct(res.rates[String(h)] ?? 0)}` : ""}
								</button>
							))}
						</div>
						<input
							className="shop-input"
							inputMode="numeric"
							placeholder={res ? `1 — ${fmt(max)}` : "Сначала выбери ресурс"}
							value={raw}
							disabled={!res}
							onChange={(e) => setRaw(e.target.value.replace(/[^\d\s]/g, ""))}
						/>
						{valid && (
							<div className="shop-quote">
								<div className="line">
									<span className="muted">Заберёшь через {hours} ч</span>
									<span className="total">{fmt(Math.floor(amount * (1 + rate)))}</span>
								</div>
							</div>
						)}
						<div className="grid-2">
							<button className="btn ghost" type="button" disabled={!res} onClick={() => setRaw(String(max))}>Максимум</button>
							<button className={`btn gold ${valid && !busy ? "" : "off"}`} type="button" disabled={!valid || busy} onClick={submit}>
								Открыть
							</button>
						</div>
					</div>
				</Sheet>
			)}
		</>
	);
}
