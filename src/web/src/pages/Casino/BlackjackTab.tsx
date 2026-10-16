import { Hand, Plus, RotateCcw, X as Double } from "lucide-react";
import { useState } from "react";
import { apiPost } from "../../api";
import type { BlackjackHand, CasinoData } from "../../types";
import { Panel, useToast } from "../../components/ui";
import { CardRow } from "./PlayingCard";
import { StakePicker, type StakeValue } from "./StakePicker";

interface HandResponse {
	message: string;
	hand: BlackjackHand;
}

/** Блэкджек: раздача, ещё / хватит / удвоить. Раздача живёт на сервере (Redis) — после
 *  перезахода продолжается с того же места. */
export function BlackjackTab({ data, reload }: { data: CasinoData; reload: () => void | Promise<void> }) {
	const toast = useToast();
	const [hand, setHand] = useState<BlackjackHand | null>(data.blackjack);
	const [stake, setStake] = useState<StakeValue | null>(null);
	const [busy, setBusy] = useState(false);

	const call = async (path: string, body?: unknown) => {
		if (busy) return;
		setBusy(true);
		try {
			const res = await apiPost<HandResponse>(path, body ?? {});
			setHand(res.hand);
			if (res.hand.finished) void reload();
		} catch (err) {
			toast(err instanceof Error ? err.message : String(err), "err");
			void reload();
		} finally {
			setBusy(false);
		}
	};

	const playing = hand !== null && !hand.finished;
	const tone = hand?.finished ? (hand.outcome === "win" || hand.outcome === "natural" ? "green" : hand.outcome === "push" ? "blue" : "red") : "gold";

	return (
		<>
			{hand && (
				<Panel title="Блэкджек" tone={tone}>
					<div className="bj-side">
						<span className="muted">Дилер</span>
						<b>{hand.dealer_total ?? "?"}</b>
					</div>
					<CardRow cards={hand.dealer} />
					<div className="bj-side bj-mine">
						<span className="muted">Ты</span>
						<b>{hand.player_total}</b>
					</div>
					<CardRow cards={hand.player} />
					<div className="bj-info muted">
						Ставка: {hand.stake_label}
						{hand.doubled ? " ×2" : ""}
					</div>
					{hand.finished && (
						<div className={`cs-note ${hand.outcome === "win" || hand.outcome === "natural" ? "win" : ""}`} role="status">
							{hand.message}
						</div>
					)}
					{playing && (
						<div className="grid-3 bj-actions">
							<button className="btn" type="button" disabled={busy} onClick={() => void call("/casino/blackjack/hit")}>
								<Plus size={16} /> Ещё
							</button>
							<button className="btn green" type="button" disabled={busy} onClick={() => void call("/casino/blackjack/stand")}>
								<Hand size={16} /> Хватит
							</button>
							<button className="btn violet" type="button" disabled={busy || !hand.can_double} onClick={() => void call("/casino/blackjack/double")}>
								<Double size={16} /> Удвоить
							</button>
						</div>
					)}
				</Panel>
			)}
			{!playing && (
				<>
					<StakePicker data={data} allowStatists onChange={setStake} />
					<button className="btn gold block" type="button" disabled={!stake || busy} onClick={() => stake && void call("/casino/blackjack/deal", stake)}>
						{hand ? <RotateCcw size={18} /> : null} {hand ? "Новая раздача" : "Раздать"}
					</button>
				</>
			)}
		</>
	);
}
