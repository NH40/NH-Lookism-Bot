import { useEffect, useState } from "react";
import type { CasinoData } from "../../types";
import { Panel, fmt } from "../../components/ui";

export interface StakeValue {
	kind: "res";
	code: string;
	amount: number;
}

const PRESETS = [10, 50, 100, 500];

/** Выбор ставки: ресурс (сервер отдаёт только разрешённые — без донат-коинов, крови и статистов),
 *  пресеты + своё число. Наружу — готовая ставка или null, если невалидна. */
export function StakePicker({ data, onChange }: { data: CasinoData; onChange: (s: StakeValue | null) => void }) {
	const [code, setCode] = useState<string>(data.resources[0]?.code ?? "coins");
	const [amount, setAmount] = useState("100");

	const balance = data.resources.find((r) => r.code === code)?.balance ?? 0;
	const n = Math.floor(Number(amount)) || 0;
	const valid = n >= 1 && n <= balance;

	useEffect(() => {
		onChange(valid ? { kind: "res", code, amount: n } : null);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [valid, code, n]);

	return (
		<Panel title="Ставка">
			<div className="grid-3 cs-sources">
				{data.resources.map((r) => (
					<button key={r.code} type="button" className={`pill ${code === r.code ? "on" : ""}`} onClick={() => setCode(r.code)}>
						{r.label}
						<span className="cs-sub">{fmt(r.balance)}</span>
					</button>
				))}
			</div>
			<div className="grid-4 cs-presets">
				{PRESETS.map((p) => (
					<button key={p} type="button" className={`pill cs-pill ${n === p ? "on" : ""}`} onClick={() => setAmount(String(p))}>
						{fmt(p)}
					</button>
				))}
			</div>
			<div className="cs-custom">
				<input inputMode="numeric" value={amount} aria-label="Ставка" onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} />
				<button type="button" className="btn ghost small" onClick={() => setAmount(String(balance))}>
					Макс
				</button>
			</div>
		</Panel>
	);
}
