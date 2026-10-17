import { Check, ChevronLeft, ChevronRight, Clock, Gavel, Inbox, ShoppingCart, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ExAuction, ExLot, ExTrade, ExchangeData } from "../../types";
import { BackHeader, Panel, Screen, countdown, fmt } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import { OfferForm } from "./OfferForm";
import "./Exchange.css";

type Tab = "lots" | "auctions" | "trades" | "mine";
const TABS: { id: Tab; label: string }[] = [
	{ id: "lots", label: "Лоты" },
	{ id: "auctions", label: "Аукционы" },
	{ id: "trades", label: "Обмены" },
	{ id: "mine", label: "Мои" },
];

/** Секунды, прошедшие с момента, когда пришли данные (для живых таймеров без перезапроса). */
function useElapsed(stamp: unknown): number {
	const [elapsed, setElapsed] = useState(0);
	const start = useRef(Date.now());
	useEffect(() => {
		start.current = Date.now();
		setElapsed(0);
		const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - start.current) / 1000)), 1000);
		return () => window.clearInterval(id);
	}, [stamp]);
	return elapsed;
}

function Empty({ text }: { text: string }) {
	return (
		<Panel>
			<div className="ex-empty">
				<Inbox size={34} />
				<div className="muted">{text}</div>
			</div>
		</Panel>
	);
}

function Pager({ page, hasMore, onPage }: { page: number; hasMore: boolean; onPage: (p: number) => void }) {
	if (page === 0 && !hasMore) return null;
	return (
		<div className="row ex-pager">
			<button className="btn ghost small" type="button" disabled={page === 0} onClick={() => onPage(page - 1)}>
				<ChevronLeft size={16} /> Назад
			</button>
			<span className="muted">стр. {page + 1}</span>
			<button className="btn ghost small" type="button" disabled={!hasMore} onClick={() => onPage(page + 1)}>
				Вперёд <ChevronRight size={16} />
			</button>
		</div>
	);
}

export function ExchangePage() {
	const [tab, setTab] = useState<Tab>("lots");
	const [lotPage, setLotPage] = useState(0);
	const [auctionPage, setAuctionPage] = useState(0);
	const { data, status, error, reload } = useApi<ExchangeData>(`/exchange?lot_page=${lotPage}&auction_page=${auctionPage}`);
	const { run, busy } = useAction(reload);
	const elapsed = useElapsed(data);

	return (
		<Screen status={status} error={error}>
			{data && (
				<div className="page">
					<BackHeader title="Биржа" to={ROUTE_MORE} />
					<div className="seg" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
						{TABS.map((t) => (
							<button key={t.id} type="button" className={`pill ${tab === t.id ? "on" : ""}`} onClick={() => setTab(t.id)}>
								{t.label}
							</button>
						))}
					</div>

					{tab === "lots" && (
						<>
							{data.lots.length === 0 ? (
								<Empty text="Пока лотов нет. Выстави первый — он появится у всех игроков." />
							) : (
								data.lots.map((l) => <LotRow key={l.id} lot={l} busy={busy} onBuy={() => run("/exchange/lots/buy", { id: l.id })} />)
							)}
							<Pager page={lotPage} hasMore={data.lots_has_more} onPage={setLotPage} />
							<OfferForm mode="lot" cfg={data.config} onDone={reload} />
						</>
					)}

					{tab === "auctions" && (
						<>
							{data.auctions.length === 0 ? (
								<Empty text="Активных аукционов нет." />
							) : (
								data.auctions.map((a) => (
									<AuctionRow key={a.id} a={a} left={a.seconds_left - elapsed} busy={busy} onBid={(amount) => run("/exchange/auctions/bid", { id: a.id, amount })} />
								))
							)}
							<Pager page={auctionPage} hasMore={data.auctions_has_more} onPage={setAuctionPage} />
							<OfferForm mode="auction" cfg={data.config} onDone={reload} />
						</>
					)}

					{tab === "trades" && (
						<>
							<Panel title="Входящие" tone="green">
								{data.incoming.length === 0 ? (
									<div className="muted ex-hint">Предложений тебе нет.</div>
								) : (
									data.incoming.map((t) => (
										<TradeRow key={t.id} t={t} left={t.seconds_left - elapsed} incoming busy={busy} onAccept={() => run("/exchange/trades/accept", { id: t.id })} onDecline={() => run("/exchange/trades/decline", { id: t.id })} />
									))
								)}
							</Panel>
							<Panel title="Исходящие" tone="violet">
								{data.outgoing.length === 0 ? (
									<div className="muted ex-hint">Ты никому ничего не предлагал.</div>
								) : (
									data.outgoing.map((t) => <TradeRow key={t.id} t={t} left={t.seconds_left - elapsed} busy={busy} onDecline={() => run("/exchange/trades/decline", { id: t.id })} />)
								)}
							</Panel>
							<OfferForm mode="trade" cfg={data.config} onDone={reload} />
						</>
					)}

					{tab === "mine" && (
						<>
							<Panel title={`Мои лоты · ${data.my_lots.length}/${data.config.max_lots}`}>
								{data.my_lots.length === 0 ? (
									<div className="muted ex-hint">Лотов нет.</div>
								) : (
									data.my_lots.map((l) => (
										<div key={l.id} className="ex-row">
											<div className="ex-main">
												<b>{l.item.full}</b>
												<span className="muted">за {l.price_full}</span>
											</div>
											<button className="btn red small" type="button" disabled={busy} onClick={() => void run("/exchange/lots/cancel", { id: l.id })}>
												<Trash2 size={15} /> Снять
											</button>
										</div>
									))
								)}
							</Panel>
							<Panel title={`Мои аукционы · ${data.my_auctions.length}/${data.config.max_auctions}`} tone="violet">
								{data.my_auctions.length === 0 ? (
									<div className="muted ex-hint">Аукционов нет.</div>
								) : (
									data.my_auctions.map((a) => (
										<div key={a.id} className="ex-row">
											<div className="ex-main">
												<b>{a.item.full}</b>
												<span className="muted">{a.current_bid ? `ставка ${a.price_full}` : `старт ${a.price_full}`}</span>
											</div>
											<span className="chip ex-time">
												<Clock size={14} /> {countdown(a.seconds_left - elapsed)}
											</span>
											{!a.current_bid && (
												<button className="btn red small" type="button" disabled={busy} onClick={() => run("/exchange/auctions/cancel", { id: a.id })}>
													Снять
												</button>
											)}
										</div>
									))
								)}
							</Panel>
						</>
					)}
				</div>
			)}
		</Screen>
	);
}

function LotRow({ lot, busy, onBuy }: { lot: ExLot; busy: boolean; onBuy: () => unknown }) {
	const [confirm, setConfirm] = useState(false);
	return (
		<Panel>
			<div className="ex-row">
				<div className="ex-main">
					<b>{lot.item.full}</b>
					<span className="muted">продавец: {lot.seller}</span>
				</div>
				<div className="ex-price">{lot.price_full}</div>
			</div>
			{confirm ? (
				<div className="grid-2">
					<button className="btn ghost" type="button" onClick={() => setConfirm(false)}>
						<X size={16} /> Отмена
					</button>
					<button className="btn green" type="button" disabled={busy} onClick={() => void Promise.resolve(onBuy()).then(() => setConfirm(false))}>
						<Check size={16} /> Купить
					</button>
				</div>
			) : (
				<button className="btn block" type="button" onClick={() => setConfirm(true)}>
					<ShoppingCart size={16} /> Купить за {lot.price_full}
				</button>
			)}
		</Panel>
	);
}

function AuctionRow({ a, left, busy, onBid }: { a: ExAuction; left: number; busy: boolean; onBid: (amount: number) => unknown }) {
	const [amount, setAmount] = useState(String(a.next_bid));
	useEffect(() => {
		setAmount(String(a.next_bid))
	}, [a.next_bid]);
	return (
		<Panel tone="violet">
			<div className="ex-row">
				<div className="ex-main">
					<b>{a.item.full}</b>
					<span className="muted">продавец: {a.seller}</span>
				</div>
				<span className="chip ex-time">
					<Clock size={14} /> {countdown(left)}
				</span>
			</div>
			<div className="grid-2 ex-fields">
				<div className="chip ex-chip">
					<span className="muted">Ставка</span>
					<b className="ex-gold">{a.current_bid ? a.price_full : "нет"}</b>
				</div>
				<div className="chip ex-chip">
					<span className="muted">{a.leading ? "Ты лидируешь" : "Минимум"}</span>
					<b>
						{fmt(a.next_bid)} {a.price_label}
					</b>
				</div>
			</div>
			<div className="ex-bid">
				<input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} aria-label="Ставка" />
				<button className="btn violet" type="button" disabled={busy || left <= 0 || Number(amount) < a.next_bid} onClick={() => void onBid(Number(amount))}>
					<Gavel size={16} /> Ставка
				</button>
			</div>
		</Panel>
	);
}

function TradeRow({ t, left, incoming, busy, onAccept, onDecline }: { t: ExTrade; left: number; incoming?: boolean; busy: boolean; onAccept?: () => unknown; onDecline: () => unknown }) {
	return (
		<div className="ex-trade">
			<div className="ex-row">
				<div className="ex-main">
					<b>{t.item.full}</b>
					<span className="muted">
						{incoming ? "от" : "кому"}: {t.other} · за {t.price_full}
					</span>
				</div>
				<span className="chip ex-time">
					<Clock size={14} /> {countdown(left)}
				</span>
			</div>
			<div className={incoming ? "grid-2" : ""}>
				{incoming && (
					<button className="btn green small" type="button" disabled={busy} onClick={() => void onAccept?.()}>
						<Check size={15} /> Принять
					</button>
				)}
				<button className="btn red small block" type="button" disabled={busy} onClick={() => void onDecline()}>
					<X size={15} /> {incoming ? "Отказать" : "Отозвать"}
				</button>
			</div>
		</div>
	);
}
