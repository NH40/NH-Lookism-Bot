import { useEffect, useState } from "react";
import type { CasinoData } from "../../types";
import { Panel, fmt } from "../../components/ui";

export interface StakeValue {
	kind: "res" | "statist";
	code: string;
	amount: number;
}

const PRESETS = [10, 50, 100, 500];

/** Выбор ставки: ресурс (кроме донат-коинов — их сервер не принимает) или отряд статистов,
 *  пресеты + своё число. Наружу — готовая ставка или null, если невалидна. */
export function StakePicker({ data, allowStatists, onChange }: { data: CasinoData; allowStatists: boolean; onChange: (s: StakeValue | null) => void }) {
	const [source, setSource] = useState<string>("res:" + (data.resources[0]?.code ?? "coins"));
	const [amount, setAmount] = useState("100");

	const isStatist = source === "statist";
	const squad = isStatist ? source : "";
	const [squadCode, setSquadCode] = useState(data.squads[0]?.code ?? "");
	const balance = isStatist ? (data.squads.find((s) => s.code === squadCode)?.total ?? 0) : (data.resources.find((r) => "res:" + r.code === source)?.balance ?? 0);
	const n = Math.floor(Number(amount)) || 0;
	const minAmount = isStatist ? data.statists_min : 1;
	const valid = n >= minAmount && n <= balance;

	useEffect(() => {
		if (!valid) onChange(null);
		else onChange(isStatist ? { kind: "statist", code: squadCode, amount: n } : { kind: "res", code: source.slice(4), amount: n });
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [valid, isStatist, squadCode, source, n]);

	const presets = isStatist ? [5, 10, 25, 50] : PRESETS;

	return (
		<Panel title="Ставка">
			<div className="grid-3 cs-sources">
				{data.resources.map((r) => (
					<button key={r.code} type="button" className={`pill ${source === "res:" + r.code ? "on" : ""}`} onClick={() => setSource("res:" + r.code)}>
						{r.label}
						<span className="cs-sub">{fmt(r.balance)}</span>
					</button>
				))}
				{allowStatists && data.squads.length > 0 && (
					<button type="button" className={`pill ${squad ? "on" : ""}`} onClick={() => setSource("statist")}>
						Статисты
						<span className="cs-sub">{fmt(data.squads.reduce((a, s) => a + s.total, 0))} бойцов</span>
					</button>
				)}
			</div>
			{isStatist && (
				<label className="cs-field">
					<span className="muted">Отряд (минимум {data.statists_min} бойцов)</span>
					<select value={squadCode} onChange={(e) => setSquadCode(e.target.value)}>
						{data.squads.map((s) => (
							<option key={s.code} value={s.code}>
								{s.label} · {fmt(s.total)}
							</option>
						))}
					</select>
				</label>
			)}
			<div className="grid-4 cs-presets">
				{presets.map((p) => (
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
