import { Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { apiPost } from "../../api";
import type { CasinoData, SlotsResult } from "../../types";
import { Panel, useToast } from "../../components/ui";
import { StakePicker, type StakeValue } from "./StakePicker";

const SPIN_MS = 1200;

/** Слоты: барабаны крутятся CSS-анимацией, пока идёт запрос и минимум ~1,2 с, затем итог. */
export function SlotsTab({ data, reload }: { data: CasinoData; reload: () => void | Promise<void> }) {
	const toast = useToast();
	const symbols = data.symbols.map((s) => s.symbol);
	const [reel, setReel] = useState<string[]>([symbols[3] ?? "", symbols[4] ?? "", symbols[5] ?? ""]);
	const [spinning, setSpinning] = useState(false);
	const [shown, setShown] = useState<string[]>(reel);
	const [result, setResult] = useState<SlotsResult | null>(null);
	const [stake, setStake] = useState<StakeValue | null>(null);
	const timer = useRef<number | null>(null);

	useEffect(() => () => void (timer.current && window.clearInterval(timer.current)), []);

	const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

	const spin = async () => {
		if (!stake || spinning) return;
		setSpinning(true);
		setResult(null);
		if (!reduced) {
			timer.current = window.setInterval(() => setShown(Array.from({ length: 3 }, () => symbols[Math.floor(Math.random() * symbols.length)])), 90);
		}
		const started = Date.now();
		try {
			const res = await apiPost<SlotsResult>("/casino/slots/spin", stake);
			const wait = reduced ? 0 : Math.max(0, SPIN_MS - (Date.now() - started));
			await new Promise((r) => window.setTimeout(r, wait));
			setReel(res.reel);
			setShown(res.reel);
			setResult(res);
			void reload();
		} catch (err) {
			toast(err instanceof Error ? err.message : String(err), "err");
		} finally {
			if (timer.current) window.clearInterval(timer.current);
			setSpinning(false);
		}
	};

	const label = stake ? `${stake.amount.toLocaleString("ru-RU")}` : "";
	const note = result ? result.message : `Пара — ставка возвращается`;

	return (
		<>
			<Panel title="Слоты" tone="gold">
				<div className="grid-3">
					{(spinning ? shown : reel).map((s, i) => (
						<div key={i} className={`cs-reel ${spinning ? "spin" : ""} ${!spinning && result?.outcome === "triple" ? "win" : ""}`}>
							{s}
						</div>
					))}
				</div>
				<div className={`cs-note ${result?.outcome === "triple" ? "win" : ""}`} role="status">
					{note}
				</div>
				<div className="grid-3 cs-table">
					{data.symbols.map((s) => (
						<div key={s.symbol} className="cs-sym">
							{s.symbol} ×{s.multiplier}
						</div>
					))}
				</div>
			</Panel>
			<StakePicker data={data} allowStatists={false} onChange={setStake} />
			<button className="btn gold block" type="button" disabled={!stake || spinning} onClick={() => void spin()}>
				<Play size={18} /> Крутить{label ? ` · ${label}` : ""}
			</button>
		</>
	);
}
