import { Ticket } from "lucide-react";
import { fmt } from "../../components/ui";
import type { ShopTickets } from "../../types";
import type { TabProps } from "./shared";

const PACKS = [1, 5, 10] as const;

/** Тикеты за NHCoin: одна цена, дневной лимит (пользователь 2026-11-19). */
export function TicketsCard({ data, coins, run, busy }: TabProps & { data: ShopTickets }) {
	const packs = [...PACKS.filter((n) => n < data.left), ...(data.left > 0 ? [data.left] : [])];
	return (
		<div className="shop-item">
			<div className="shop-item-head">
				<span className="name"><Ticket size={16} color="var(--gold-2)" />Тикеты</span>
				<span className="muted" style={{ fontSize: 11, fontWeight: 700 }}>
					{fmt(data.price)} за шт · сегодня ещё {data.left} из {data.limit}
				</span>
			</div>
			{data.left > 0 ? (
				<div className="shop-tiers">
					{packs.map((n) => {
						const cost = n * data.price;
						const ok = coins >= cost && !busy;
						return (
							<button key={n} type="button" className={`btn small ${ok ? "gold" : "ghost off"}`} disabled={!ok}
								onClick={() => run("/shop/tickets/buy", { amount: n })}>
								{n === data.left && n > 10 ? `Все ${n}` : `×${n}`} · {fmt(cost)}
							</button>
						);
					})}
				</div>
			) : (
				<div className="shop-empty">Лимит на сегодня выкуплен — завтра снова.</div>
			)}
		</div>
	);
}
