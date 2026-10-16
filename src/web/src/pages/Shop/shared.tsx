import { useEffect, useState, type ReactNode } from "react";
import { Sheet } from "../../components/Sheet";
import { countdown, fmt } from "../../components/ui";
import type { useAction } from "../../hooks/useApi";

export type Runner = ReturnType<typeof useAction>;

export interface TabProps {
	coins: number;
	run: Runner["run"];
	busy: boolean;
}

/** Тикающий обратный отсчёт от `initial` секунд. */
export function useTick(initial: number): number {
	const [left, setLeft] = useState(initial);
	useEffect(() => {
		setLeft(initial);
		if (initial <= 0) return;
		const id = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
		return () => clearInterval(id);
	}, [initial]);
	return left;
}

export function Timer({ seconds }: { seconds: number }) {
	return <>{countdown(useTick(seconds))}</>;
}

export function parseAmount(raw: string): number {
	const n = Number(raw.replace(/\s/g, ""));
	return Number.isInteger(n) && n > 0 ? n : 0;
}

/** Шторка ввода количества: поле + «Максимум» + кнопка подтверждения. */
export function AmountSheet({ title, hint, max, confirm, busy, onConfirm, onClose, children }: {
	title: string;
	hint?: ReactNode;
	max: number;
	confirm: (amount: number) => string;
	busy: boolean;
	onConfirm: (amount: number) => void;
	onClose: () => void;
	children?: ReactNode;
}) {
	const [raw, setRaw] = useState("");
	const amount = parseAmount(raw);
	const valid = amount > 0 && amount <= max;
	return (
		<Sheet title={title} onClose={onClose}>
			<div className="shop-sheet-body">
				{hint && <div className="shop-note">{hint}</div>}
				{children}
				<input
					className="shop-input"
					inputMode="numeric"
					placeholder={`1 — ${fmt(max)}`}
					value={raw}
					onChange={(e) => setRaw(e.target.value.replace(/[^\d\s]/g, ""))}
				/>
				<div className="grid-2">
					<button className="btn ghost" type="button" onClick={() => setRaw(String(max))}>Максимум</button>
					<button className={`btn gold ${valid && !busy ? "" : "off"}`} type="button" disabled={!valid || busy} onClick={() => onConfirm(amount)}>
						{valid ? confirm(amount) : "Введи число"}
					</button>
				</div>
			</div>
		</Sheet>
	);
}
