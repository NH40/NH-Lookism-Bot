import { useState } from "react";
import { Panel, fmt } from "../../components/ui";
import type { ShopContracts } from "../../types";
import { AmountSheet, Timer, type TabProps } from "./shared";

const PRESETS = [10, 100, 1000, 10000];

export function ContractsTab({ data, coins, run, busy }: TabProps & { data: ShopContracts }) {
	const [rank, setRank] = useState(() => {
		const affordable = [...data.ranks].reverse().find((r) => r.unit_price <= coins);
		return (affordable ?? data.ranks[0])?.rank ?? "";
	});
	const [qty, setQty] = useState(100);
	const [custom, setCustom] = useState(false);
	const [sheet, setSheet] = useState(false);
	const current = data.ranks.find((r) => r.rank === rank) ?? data.ranks[0];
	const unit = current?.unit_price ?? 0;
	const total = unit * qty;
	const enough = coins >= total;

	const buy = (quantity: number) => run("/shop/contract/buy", { rank: current.rank, quantity });

	return (
		<>
			<Panel title="Контракты" tone="gold">
				<div className="shop-note muted" style={{ marginBottom: 10 }}>
					Наёмники на {data.hours} ч сражаются за банду. Потолок ранга — по твоему влиянию: <b>до {data.ceiling}</b>.
					{data.discount > 0 && <> Скидка рода: −{Math.round(data.discount * 100)}%.</>}
				</div>
				<div className="shop-label">Ранг</div>
				<div className="shop-pills">
					{data.ranks.map((r) => (
						<button key={r.rank} type="button" className={`pill ${r.rank === current?.rank ? "on" : ""}`} onClick={() => setRank(r.rank)}>
							{r.rank}
						</button>
					))}
				</div>
				<div className="shop-label">Количество</div>
				<div className="shop-pills">
					{PRESETS.map((p) => (
						<button key={p} type="button" className={`pill ${!custom && qty === p ? "on" : ""}`} onClick={() => { setQty(p); setCustom(false); }}>
							{p.toLocaleString("ru-RU")}
						</button>
					))}
					<button type="button" className={`pill ${custom ? "on" : ""}`} onClick={() => setSheet(true)}>
						{custom ? fmt(qty) : "Своё"}
					</button>
				</div>
				{current && (
					<div className="shop-quote">
						<div className="line">
							<span className="muted">{current.rank} × {qty.toLocaleString("ru-RU")} · мощь {fmt(current.power)}</span>
							<span>{fmt(unit)} за бойца</span>
						</div>
						<div className="line" style={{ marginTop: 6 }}>
							<span className="muted">Итого на {data.hours} ч</span>
							<span className="total">{fmt(total)}</span>
						</div>
					</div>
				)}
				<button
					className={`btn block ${enough ? "gold" : "off"}`}
					style={{ marginTop: 10 }}
					type="button"
					disabled={!enough || busy || !current}
					onClick={() => buy(qty)}
				>
					{enough ? `Нанять за ${fmt(total)}` : "Не хватает NHCoin — забери доход"}
				</button>
			</Panel>

			<Panel title="Действующие">
				{data.active.length === 0 ? (
					<div className="shop-empty">Активных контрактов нет.</div>
				) : (
					data.active.map((a, i) => (
						<div className="stat" key={`${a.rank}-${i}`}>
							{a.quantity.toLocaleString("ru-RU")} × {a.rank}
							<b className="muted"><Timer seconds={a.expires_in_seconds} /></b>
						</div>
					))
				)}
			</Panel>

			{sheet && current && (
				<AmountSheet
					title={`Наём: ранг ${current.rank}`}
					hint={<>Цена {fmt(unit)} за бойца · хватит на <b>{unit ? fmt(Math.min(data.max_quantity, Math.floor(coins / unit))) : 0}</b></>}
					max={data.max_quantity}
					busy={busy}
					confirm={(n) => `Выбрать ${fmt(n)}`}
					onConfirm={(n) => { setQty(n); setCustom(true); setSheet(false); }}
					onClose={() => setSheet(false)}
				/>
			)}
		</>
	);
}
