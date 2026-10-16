import { useState, type ReactNode } from "react";
import { Sheet } from "../../components/Sheet";
import { Spinner, fmt } from "../../components/ui";

/** Ввод целого числа в шторке: «Все» ставит максимум, кнопка подтверждает. */
export function AmountSheet({ title, hint, max, confirmLabel, busy, onSubmit, onClose }: {
	title: string;
	hint?: ReactNode;
	max?: number;
	confirmLabel: string;
	busy: boolean;
	onSubmit: (amount: number) => void;
	onClose: () => void;
}) {
	const [text, setText] = useState("");
	const amount = Number(text) || 0;
	const bad = amount <= 0 || (max !== undefined && amount > max);
	return (
		<Sheet title={title} onClose={onClose}>
			{hint && <p className="muted clan-hint">{hint}</p>}
			<div className="row">
				<input
					className="clan-input"
					inputMode="numeric"
					autoFocus
					placeholder={max !== undefined ? `1 – ${fmt(max)}` : "Сумма"}
					value={text}
					onChange={(e) => setText(e.currentTarget.value.replace(/\D/g, "").slice(0, 12))}
				/>
				{max !== undefined && (
					<button className="btn ghost small" type="button" onClick={() => setText(String(max))}>Все</button>
				)}
			</div>
			<button className="btn block" style={{ marginTop: 12 }} type="button" disabled={busy || bad} onClick={() => onSubmit(amount)}>
				{busy ? <Spinner /> : confirmLabel}
			</button>
		</Sheet>
	);
}

/** Подтверждение необратимого действия. */
export function ConfirmSheet({ title, text, confirmLabel, tone = "red", busy, onConfirm, onClose }: {
	title: string;
	text: ReactNode;
	confirmLabel: string;
	tone?: "red" | "gold" | "";
	busy: boolean;
	onConfirm: () => void;
	onClose: () => void;
}) {
	return (
		<Sheet title={title} onClose={onClose}>
			<p className="clan-hint">{text}</p>
			<div className="grid-2" style={{ marginTop: 12 }}>
				<button className="btn ghost" type="button" onClick={onClose}>Отмена</button>
				<button className={`btn ${tone}`} type="button" disabled={busy} onClick={onConfirm}>
					{busy ? <Spinner /> : confirmLabel}
				</button>
			</div>
		</Sheet>
	);
}

export interface PickItem {
	id: string;
	title: string;
	sub: string;
	max: number;
	thumb?: string;
}

/** Выбор позиции из списка, затем количество (внести/забрать в роте). */
export function PickAmountSheet({ title, items, empty, confirmLabel, busy, onSubmit, onClose }: {
	title: string;
	items: PickItem[];
	empty: string;
	confirmLabel: string;
	busy: boolean;
	onSubmit: (id: string, amount: number) => void;
	onClose: () => void;
}) {
	const [picked, setPicked] = useState<PickItem | null>(null);
	if (picked) {
		return (
			<AmountSheet
				title={picked.title}
				hint={`Доступно: ${fmt(picked.max)}`}
				max={picked.max}
				confirmLabel={confirmLabel}
				busy={busy}
				onSubmit={(n) => onSubmit(picked.id, n)}
				onClose={onClose}
			/>
		);
	}
	return (
		<Sheet title={title} onClose={onClose}>
			{items.length === 0 ? (
				<div className="muted clan-hint">{empty}</div>
			) : (
				items.map((it) => (
					<button key={it.id} className="pick-row" type="button" onClick={() => setPicked(it)}>
						{it.thumb !== undefined && <div className="pick-thumb">{it.thumb && <img src={it.thumb} alt="" loading="lazy" />}</div>}
						<div style={{ flex: 1, minWidth: 0 }}>
							<div className="pick-name">{it.title}</div>
							<div className="pick-sub">{it.sub}</div>
						</div>
					</button>
				))
			)}
		</Sheet>
	);
}
