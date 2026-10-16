import { LogOut, Plus, Users } from "lucide-react";
import { useState } from "react";
import type { CasinoData } from "../../types";
import { Panel, countdown, fmt } from "../../components/ui";
import { useAction } from "../../hooks/useApi";
import { PokerTableView } from "./PokerTableView";

/** Покер: лобби столов, создание, вход; сидя за столом — живой стол с опросом раз в 3 с. */
export function PokerTab({ data, reload }: { data: CasinoData; reload: () => void | Promise<void> }) {
	const { run, busy } = useAction(reload);
	const cfg = data.poker;
	const [buyIn, setBuyIn] = useState(cfg.buy_ins[0] ?? 0);
	const [maxPlayers, setMaxPlayers] = useState(cfg.max_players_max);
	const [wait, setWait] = useState(cfg.wait_options[0] ?? 60);

	if (data.seat_table_id !== null) {
		return <PokerTableView tableId={data.seat_table_id} onLeft={reload} />;
	}

	const players = Array.from({ length: cfg.max_players_max - cfg.max_players_min + 1 }, (_, i) => cfg.max_players_min + i);
	return (
		<>
			<Panel title="Столы" tone="green">
				{data.lobby.length === 0 ? (
					<div className="muted cs-empty">Столов сейчас нет — создай свой.</div>
				) : (
					data.lobby.map((t) => (
						<div key={t.id} className="cs-lobby-row">
							<div className="cs-lobby-main">
								<b>Стол #{t.id}</b>
								<span className="muted">
									вход {fmt(t.buy_in)} NHCoin · старт через {countdown(t.starts_in)}
								</span>
							</div>
							<span className="chip cs-time">
								<Users size={14} /> {t.players}/{t.max_players}
							</span>
							<button className="btn green small" type="button" disabled={busy || data.coins < t.buy_in} onClick={() => void run("/casino/poker/join", { table_id: t.id })}>
								Сесть
							</button>
						</div>
					))
				)}
			</Panel>
			<Panel title="Создать стол" tone="gold">
				<div className="muted cs-label">Бай-ин (NHCoin, у тебя {fmt(data.coins)})</div>
				<div className="grid-3">
					{cfg.buy_ins.map((b) => (
						<button key={b} type="button" className={`pill ${buyIn === b ? "on" : ""}`} onClick={() => setBuyIn(b)}>
							{fmt(b)}
						</button>
					))}
				</div>
				<div className="muted cs-label">Игроков за столом</div>
				<div className="seg" style={{ gridTemplateColumns: `repeat(${players.length}, minmax(0, 1fr))` }}>
					{players.map((p) => (
						<button key={p} type="button" className={`pill ${maxPlayers === p ? "on" : ""}`} onClick={() => setMaxPlayers(p)}>
							{p}
						</button>
					))}
				</div>
				<div className="muted cs-label">Ожидание старта</div>
				<div className="seg" style={{ gridTemplateColumns: `repeat(${cfg.wait_options.length}, minmax(0, 1fr))` }}>
					{cfg.wait_options.map((w) => (
						<button key={w} type="button" className={`pill ${wait === w ? "on" : ""}`} onClick={() => setWait(w)}>
							{w >= 60 ? `${w / 60} мин` : `${w} с`}
						</button>
					))}
				</div>
				<div className="muted cs-hint">
					Рейк {Math.round(cfg.rake_percent * 100)}% с банка, на ход — {cfg.action_timeout} с (потом авто-чек/фолд).
				</div>
				<button className="btn gold block" type="button" disabled={busy || data.coins < buyIn} onClick={() => void run("/casino/poker/create", { buy_in: buyIn, max_players: maxPlayers, wait })}>
					<Plus size={18} /> Создать · {fmt(buyIn)} NHCoin
				</button>
			</Panel>
			<LeaveHint />
		</>
	);
}

function LeaveHint() {
	return (
		<div className="muted cs-hint" style={{ textAlign: "center" }}>
			<LogOut size={13} style={{ verticalAlign: "-2px" }} /> Выйти из-за стола можно в любой момент — стек вернётся после раздачи.
		</div>
	);
}
