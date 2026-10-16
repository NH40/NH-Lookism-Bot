import { Gem, Hammer, Landmark, Trash2 } from "lucide-react";
import { useState } from "react";
import type { ClanCan, ClanLands } from "../../types";
import { Bar, Panel, Screen, StatRow, fmt } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";
import { AmountSheet, ConfirmSheet } from "./shared";

/** Вкладка «Земли»: земли и казна, здания, уровень клана. */
export function LandsTab({ can, onChanged }: { can: ClanCan; onChanged: () => Promise<void> }) {
	const { data, status, error, reload } = useApi<ClanLands>("/clan/lands");
	const { run, busy } = useAction(async () => {
		await reload();
		await onChanged();
	});
	const [donating, setDonating] = useState(false);
	const [demolish, setDemolish] = useState<string | null>(null);
	const [level, setLevel] = useState(false);

	return (
		<Screen status={data ? "ready" : status} error={error}>
			{data && (
				<>
					<Panel title="Земли" tone="gold">
						<StatRow icon={<Landmark size={16} color="var(--cyan)" />} label="Освоено" value={`${data.lands}/${data.max_lands}`} />
						<StatRow label="Свободно под здания" value={data.free} />
						<StatRow label="Казна" value={`${fmt(data.treasury)} NHCoin`} />
						<div className="grid-2" style={{ marginTop: 10 }}>
							<button className="btn gold small" type="button" onClick={() => setDonating(true)}>Внести в казну</button>
							{can.manage && (
								<button className="btn small" type="button" disabled={busy || data.next_land_price === null} onClick={() => run("/clan/buy-land")}>
									{data.next_land_price === null ? "Максимум земель" : `Освоить · ${fmt(data.next_land_price)}`}
								</button>
							)}
						</div>
					</Panel>

					<Panel title="Здания">
						{data.buildings.map((b) => (
							<div key={b.kind} className="clan-building">
								<div style={{ flex: 1, minWidth: 0 }}>
									<div className="clan-row-name">{b.name} <span className="muted">×{b.count}/{b.max}</span></div>
									<div className="muted clan-row-sub clan-wrap">{b.about}</div>
								</div>
								{can.manage && (
									<div className="clan-building-actions">
										<button className="btn small" type="button" disabled={busy || b.next_price === null || data.free <= 0} aria-label={`Построить ${b.name}`} onClick={() => run("/clan/build", { kind: b.kind })}>
											<Hammer size={14} />{b.next_price === null ? "Макс" : fmt(b.next_price)}
										</button>
										{b.count > 0 && (
											<button className="btn ghost small" type="button" disabled={busy} aria-label={`Снести ${b.name}`} onClick={() => setDemolish(b.kind)}><Trash2 size={14} /></button>
										)}
									</div>
								)}
							</div>
						))}
						{can.manage && data.free <= 0 && <div className="muted clan-hint">Нет свободной земли — освой новую.</div>}
					</Panel>

					<Panel title="Уровень клана" tone="violet">
						<div className="row" style={{ marginBottom: 8 }}>
							<span style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 700 }}><Gem size={16} color="var(--violet)" />Уровень</span>
							<b>{data.donate_level}/{data.max_donate_level}</b>
						</div>
						<Bar value={data.donate_level} max={data.max_donate_level} fill="violet" />
						{data.donate_buyers.length > 0 && <div className="muted clan-hint">Купили: {data.donate_buyers.join(", ")}</div>}
						<button className="btn violet block" style={{ marginTop: 10 }} type="button" disabled={busy || data.next_donate_price === null} onClick={() => setLevel(true)}>
							{data.next_donate_price === null ? "Максимальный уровень" : `Поднять уровень · ${fmt(data.next_donate_price)} донат-коинов`}
						</button>
					</Panel>

					{donating && (
						<AmountSheet title="Внести в казну" hint={`У тебя ${fmt(data.coins)} NHCoin`} max={data.coins} confirmLabel="Внести" busy={busy} onClose={() => setDonating(false)} onSubmit={async (n) => {
							if (await run("/clan/donate", { amount: n })) setDonating(false);
						}} />
					)}
					{demolish && (() => {
						const b = data.buildings.find((x) => x.kind === demolish);
						return b && (
							<ConfirmSheet title="Снести здание" text={`Снести «${b.name}»? В казну вернётся ${fmt(b.refund)} NHCoin.`} confirmLabel="Снести" busy={busy} onClose={() => setDemolish(null)} onConfirm={async () => {
								if (await run("/clan/demolish", { kind: b.kind })) setDemolish(null);
							}} />
						);
					})()}
					{level && data.next_donate_price !== null && (
						<ConfirmSheet title="Уровень клана" tone="" text={`Поднять уровень клана за ${fmt(data.next_donate_price)} донат-коинов? У тебя ${fmt(data.donate_coins)}. Если выйдешь из клана, уровень пропадёт, а коины вернутся.`} confirmLabel="Купить" busy={busy} onClose={() => setLevel(false)} onConfirm={async () => {
							if (await run("/clan/buy-donate-level")) setLevel(false);
						}} />
					)}
				</>
			)}
		</Screen>
	);
}
