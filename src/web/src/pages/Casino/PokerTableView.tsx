import { Crown, LogOut, Timer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PokerTable } from "../../types";
import { Panel, countdown, fmt } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";
import { CardRow } from "./PlayingCard";

const STREET_NAMES: Record<string, string> = { preflop: "Префлоп", flop: "Флоп", turn: "Тёрн", river: "Ривер" };
const POLL_MS = 3000;

/** Стол покера: состояние опрашивается раз в 3 с, ходы — fold / check|call / raise. */
export function PokerTableView({ tableId, onLeft }: { tableId: number; onLeft: () => void | Promise<void> }) {
	const { data: t, status, error, reload } = useApi<PokerTable>(`/casino/poker/table/${tableId}`);
	const { run, busy } = useAction(reload);
	const [raise, setRaise] = useState("");
	const closedNotified = useRef(false);

	useEffect(() => {
		const id = window.setInterval(() => void reload(), POLL_MS);
		return () => window.clearInterval(id);
	}, [reload]);

	useEffect(() => {
		if (t?.status === "closed" && !closedNotified.current) {
			closedNotified.current = true;
			void onLeft();
		}
	}, [t?.status, onLeft]);

	useEffect(() => {
		if (t && t.can_raise) setRaise(String(t.min_raise_to));
	}, [t?.hand_no, t?.street, t?.min_raise_to, t?.can_raise]); // eslint-disable-line react-hooks/exhaustive-deps

	if (status === "error") return <Panel tone="red">{error}</Panel>;
	if (!t || t.status === "closed") return <Panel>Стол закрыт.</Panel>;

	const act = (action: string, amount = 0) => run("/casino/poker/act", { table_id: t.id, hand_no: t.hand_no, action, amount });
	const leave = async () => {
		await run("/casino/poker/leave", { table_id: t.id });
		await onLeft();
	};

	if (t.status === "waiting") {
		return (
			<Panel title={`Стол #${t.id}`} tone="green">
				<div className="cs-lobby-main">
					<b>Ждём игроков {t.seats.length}/{t.max_players}</b>
					<span className="muted">
						вход {fmt(t.buy_in)} · блайнды {fmt(t.small_blind)}/{fmt(t.big_blind)} · старт через {countdown(t.starts_in)}
					</span>
				</div>
				{t.seats.map((s) => (
					<div key={s.seat} className="pk-seat">
						<b>{s.name}{s.me ? " (ты)" : ""}</b>
						<span>{fmt(s.stack)}</span>
					</div>
				))}
				<button className="btn red block" type="button" disabled={busy} onClick={() => void leave()}>
					<LogOut size={16} /> Выйти, вернуть бай-ин
				</button>
			</Panel>
		);
	}

	return (
		<>
			<Panel title={`Раздача ${t.hand_no} · ${STREET_NAMES[t.street] ?? t.street}`} tone="green">
				<div className="pk-pot">
					Банк <b>{fmt(t.pot)}</b>
				</div>
				<div className="pk-board">{t.board.length ? <CardRow cards={t.board} /> : <span className="muted">Карт на столе пока нет</span>}</div>
				{t.seats.map((s) => (
					<div key={s.seat} className={`pk-seat ${s.turn ? "turn" : ""} ${s.folded ? "folded" : ""}`}>
						<b>
							{s.dealer && <Crown size={13} />} {s.name}
							{s.me ? " (ты)" : ""}
						</b>
						<span>
							{s.round_bet ? `ставка ${fmt(s.round_bet)} · ` : ""}
							{fmt(s.stack)}
							{s.all_in ? " · олл-ин" : ""}
							{s.folded ? " · фолд" : ""}
							{s.leaving ? " · уходит" : ""}
						</span>
					</div>
				))}
			</Panel>
			<Panel title="Твои карты" tone="gold">
				<CardRow cards={t.hole} />
				{t.my_turn ? (
					<>
						<div className="pk-turn">
							<Timer size={15} /> Твой ход · {t.seconds_left} с
						</div>
						<div className="grid-3">
							<button className="btn red" type="button" disabled={busy} onClick={() => void act("fold")}>
								Фолд
							</button>
							{t.to_call > 0 ? (
								<button className="btn green" type="button" disabled={busy} onClick={() => void act("call")}>
									Колл {fmt(t.to_call)}
								</button>
							) : (
								<button className="btn green" type="button" disabled={busy} onClick={() => void act("check")}>
									Чек
								</button>
							)}
							<button className="btn violet" type="button" disabled={busy || !t.can_raise || Number(raise) < t.min_raise_to || Number(raise) > t.all_in_to} onClick={() => void act("raise", Number(raise))}>
								Рейз
							</button>
						</div>
						{t.can_raise && (
							<div className="cs-custom">
								<input inputMode="numeric" value={raise} aria-label="Рейз до" onChange={(e) => setRaise(e.target.value.replace(/\D/g, ""))} />
								<button type="button" className="btn ghost small" onClick={() => setRaise(String(t.all_in_to))}>
									Олл-ин
								</button>
							</div>
						)}
					</>
				) : (
					<div className="muted pk-turn">Ждём ход соперника…</div>
				)}
				<button className="btn ghost block" type="button" disabled={busy} onClick={() => void leave()}>
					<LogOut size={16} /> Встать после раздачи
				</button>
			</Panel>
		</>
	);
}
