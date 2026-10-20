import { FlaskConical, ScrollText, Ticket } from "lucide-react";
import { useState } from "react";
import { Panel, Screen, StatRow, fmt } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";
import { AmountSheet, ConfirmSheet } from "./shared";

interface ClanShop {
	treasury: number;
	members: number;
	can_buy: boolean;
	tickets: { tickets: number; price: number }[];
	ticket_price: number;
	ticket_step: number;
	tickets_bought_today: number;
	tickets_max: number;
	tickets_daily_limit: number;
	potions: { kind: string; name: string; tiers: { tier: number; price: number }[] }[];
	contracts: { hours: number; ceiling: string; ranks: { rank: string; price: number }[] };
}

const ROMAN = ["", "I", "II", "III", "IV", "V"];

/** Вкладка «Магазин» клана — тот же магазин, что в боте: тикеты и зелья всем, контрактники в роту. */
export function ShopTab({ onChanged }: { onChanged: () => Promise<void> }) {
	const { data, status, error, reload } = useApi<ClanShop>("/clan/shop");
	const { run, busy } = useAction(async () => {
		await reload();
		await onChanged();
	});
	const [confirm, setConfirm] = useState<{ title: string; text: string; path: string; body: unknown } | null>(null);
	const [mercRank, setMercRank] = useState<{ rank: string; price: number } | null>(null);
	const [ticketsN, setTicketsN] = useState("");
	return (
		<Screen status={data ? "ready" : status} error={error}>
			{data && (
				<>
					<Panel title="Казна" tone="gold">
						<StatRow label="В казне" value={`${fmt(data.treasury)} NHCoin`} />
						<StatRow label="Участников" value={data.members} />
						{!data.can_buy && <div className="muted clan-hint">Покупают владелец и заместитель — цены за всех участников сразу.</div>}
					</Panel>
					<Panel title="Тикеты всем">
						<div className="grid-3" style={{ gap: 6 }}>
							{data.tickets.map((t) => (
								<button key={t.tickets} type="button" className="btn small" disabled={busy || !data.can_buy || t.price > data.treasury}
									onClick={() => setConfirm({ title: "Тикеты всем", text: `Каждому из ${data.members} участников по ${t.tickets} тикет. за ${fmt(t.price)} NHCoin из казны?`, path: "/clan/shop/tickets", body: { tickets: t.tickets } })}>
									<Ticket size={14} /> {t.tickets} · {fmt(t.price)}
								</button>
							))}
						</div>
						{(() => {
							const n = Math.floor(Number(ticketsN)) || 0;
							// Как на сервере: каждый следующий тикет за сутки дороже на шаг (арифметическая прогрессия).
							const price = (n * data.ticket_price + (data.ticket_step * n * (n - 1)) / 2) * data.members;
							return (
								<>
									<div className="qty-row" style={{ gridTemplateColumns: "minmax(0, 1fr) auto" }}>
										<input className="mass-input" inputMode="numeric" value={ticketsN} placeholder={`Своё число (до ${data.tickets_max})`} aria-label="Тикетов каждому"
											onChange={(e) => setTicketsN(e.target.value.replace(/\D/g, ""))} />
										<button type="button" className="btn small" disabled={busy || !data.can_buy || n < 1 || n > data.tickets_max || price > data.treasury}
											onClick={() => setConfirm({ title: "Тикеты всем", text: `Каждому из ${data.members} участников по ${n} тикет. за ${fmt(price)} NHCoin из казны?`, path: "/clan/shop/tickets", body: { tickets: n } })}>
											<Ticket size={14} /> {n > 0 ? fmt(price) : "Купить"}
										</button>
									</div>
									<div className="muted clan-hint">Следующий тикет всем = {fmt(data.ticket_price * data.members)} NHCoin, каждый следующий за сутки дороже на {fmt(data.ticket_step * data.members)}. Куплено сегодня: {fmt(data.tickets_bought_today)} из {fmt(data.tickets_daily_limit)}.</div>
								</>
							);
						})()}
					</Panel>
					<Panel title="Зелья всем" tone="violet">
						{data.potions.map((p) => (
							<div key={p.kind} style={{ marginBottom: 8 }}>
								<div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}><FlaskConical size={13} /> {p.name}</div>
								<div className="grid-3" style={{ gap: 6 }}>
									{p.tiers.map((t) => (
										<button key={t.tier} type="button" className="btn ghost small" disabled={busy || !data.can_buy || t.price > data.treasury}
											onClick={() => setConfirm({ title: p.name, text: `${p.name} ${ROMAN[t.tier]} тира всем ${data.members} участникам за ${fmt(t.price)} NHCoin из казны?`, path: "/clan/shop/potion", body: { kind: p.kind, tier: t.tier } })}>
											{ROMAN[t.tier]} · {fmt(t.price)}
										</button>
									))}
								</div>
							</div>
						))}
					</Panel>
					<Panel title={`Контрактники в роту · ${data.contracts.hours} ч`}>
						<div className="muted clan-hint">Воюют за роту и уходят по сроку; забрать себе нельзя. Потолок ранга — {data.contracts.ceiling}. Цена за бойца:</div>
						<div className="grid-3" style={{ gap: 6 }}>
							{data.contracts.ranks.map((r) => (
								<button key={r.rank} type="button" className="btn ghost small" disabled={busy || !data.can_buy} onClick={() => setMercRank(r)}>
									<ScrollText size={13} /> {r.rank} · {fmt(r.price)}
								</button>
							))}
						</div>
					</Panel>
				</>
			)}
			{confirm && (
				<ConfirmSheet title={confirm.title} text={confirm.text} confirmLabel="Купить" tone="gold" busy={busy}
					onConfirm={async () => { await run(confirm.path, confirm.body); setConfirm(null); }} onClose={() => setConfirm(null)} />
			)}
			{mercRank && data && (
				<AmountSheet title={`Контрактники ${mercRank.rank}`} hint={`${fmt(mercRank.price)} NHCoin за бойца, в казне ${fmt(data.treasury)}`}
					max={Math.floor(data.treasury / Math.max(1, mercRank.price))} confirmLabel="Нанять" busy={busy}
					onSubmit={async (quantity) => { await run("/clan/shop/contracts", { rank: mercRank.rank, quantity }); setMercRank(null); }}
					onClose={() => setMercRank(null)} />
			)}
		</Screen>
	);
}
