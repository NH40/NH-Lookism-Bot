import { Lock, Package, PackageOpen } from "lucide-react";
import { useState } from "react";
import { Sheet } from "../../components/Sheet";
import { Panel, fmt } from "../../components/ui";
import type { ShopCell, ShopStorage } from "../../types";
import { AmountSheet, type TabProps } from "./shared";

type Mode = { kind: "put"; cell: ShopCell } | { kind: "take"; cell: ShopCell };

export function StorageTab({ data, coins, run, busy }: TabProps & { data: ShopStorage }) {
	const [mode, setMode] = useState<Mode | null>(null);
	const [item, setItem] = useState<{ kind: "res" | "statist"; code: string; label: string; have: number } | null>(null);
	const [picking, setPicking] = useState<ShopCell | null>(null);

	const options = [
		...data.resources.filter((r) => r.have > 0).map((r) => ({ kind: "res" as const, code: r.code, label: r.name, have: r.have })),
		...data.squads.map((s) => ({ kind: "statist" as const, code: s.code, label: s.label, have: s.have })),
	];

	const startPut = (cell: ShopCell) => {
		if (cell.kind) {
			// Доложить: тот же предмет, что лежит в ячейке.
			const same = options.find((o) => o.kind === cell.kind && o.code === cell.code);
			if (same) {
				setItem(same);
				setMode({ kind: "put", cell });
			}
			return;
		}
		setPicking(cell);
	};

	const close = () => { setMode(null); setItem(null); setPicking(null); };

	return (
		<>
			<Panel title="Ячейки хранения">
				<div className="shop-note muted" style={{ marginBottom: 6 }}>
					Положенное в ячейку <b>не теряется</b> при атаках, саботаже и войнах. Хранение — {fmt(data.fee_per_hour)} в час за непустую
					ячейку, плата копится и платится, когда достаёшь. Сгорает только при пробуждении и удалении банды.
				</div>
				{data.cells.map((c) => (
					<div className="shop-cell" key={c.slot}>
						<div className="shop-cell-head">
							<div className="ico-box">{c.opened ? (c.kind ? <Package size={16} /> : <PackageOpen size={16} />) : <Lock size={16} color="var(--muted)" />}</div>
							<div className="grow">
								Ячейка {c.slot}
								{c.opened && c.kind && <div className="sub">{c.label} · {c.amount.toLocaleString("ru-RU")}{c.debt > 0 && ` · долг ${fmt(c.debt)}`}</div>}
								{c.opened && !c.kind && <div className="sub">пусто</div>}
							</div>
							{!c.opened && (
								<button
									className={`btn small ${c.next_to_open ? (coins >= c.open_cost ? "gold" : "ghost") : "ghost"}`}
									type="button"
									disabled={!c.next_to_open || busy}
									onClick={() => run("/shop/storage/open", { slot: c.slot })}
								>
									Открыть · {fmt(c.open_cost)}
								</button>
							)}
						</div>
						{c.opened && (
							<div className="shop-cell-actions">
								<button className="btn small ghost" type="button" disabled={busy} onClick={() => startPut(c)}>
									{c.kind ? "Доложить" : "Положить"}
								</button>
								<button className="btn small ghost" type="button" disabled={busy || !c.kind} onClick={() => setMode({ kind: "take", cell: c })}>
									Часть
								</button>
								<button className="btn small green" type="button" disabled={busy || !c.kind} onClick={() => run("/shop/storage/retrieve", { slot: c.slot })}>
									Всё
								</button>
							</div>
						)}
					</div>
				))}
			</Panel>

			{picking && !item && (
				<AmountPicker
					options={options}
					onClose={close}
					onPick={(o) => { setItem(o); setMode({ kind: "put", cell: picking }); setPicking(null); }}
				/>
			)}

			{mode?.kind === "put" && item && (
				<AmountSheet
					title={`Ячейка ${mode.cell.slot}: ${item.label}`}
					hint={<>У тебя: <b>{item.have.toLocaleString("ru-RU")}</b></>}
					max={item.have}
					busy={busy}
					confirm={(n) => `Положить ${fmt(n)}`}
					onConfirm={async (n) => {
						const r = await run("/shop/storage/store", { slot: mode.cell.slot, kind: item.kind, code: item.code, amount: n });
						if (r) close();
					}}
					onClose={close}
				/>
			)}

			{mode?.kind === "take" && (
				<AmountSheet
					title={`Ячейка ${mode.cell.slot}: достать`}
					hint={<>В ячейке: <b>{mode.cell.amount.toLocaleString("ru-RU")}</b> · долг за хранение {fmt(mode.cell.debt)} спишется сразу.</>}
					max={mode.cell.amount}
					busy={busy}
					confirm={(n) => `Достать ${fmt(n)}`}
					onConfirm={async (n) => {
						const r = await run("/shop/storage/retrieve", { slot: mode.cell.slot, amount: n });
						if (r) close();
					}}
					onClose={close}
				/>
			)}
		</>
	);
}

function AmountPicker({ options, onPick, onClose }: {
	options: { kind: "res" | "statist"; code: string; label: string; have: number }[];
	onPick: (o: { kind: "res" | "statist"; code: string; label: string; have: number }) => void;
	onClose: () => void;
}) {
	return (
		<Sheet title="Что положить?" onClose={onClose}>
			{options.length === 0 ? (
				<div className="shop-empty">Положить нечего.</div>
			) : (
				<div className="shop-pick">
					{options.map((o) => (
						<button key={`${o.kind}:${o.code}`} type="button" onClick={() => onPick(o)}>
							<span>{o.label}</span>
							<span className="muted">{o.have.toLocaleString("ru-RU")}</span>
						</button>
					))}
				</div>
			)}
		</Sheet>
	);
}
