import { useState } from "react";
import { Panel, Screen, fmt } from "../../components/ui";
import { useApi } from "../../hooks/useApi";

interface StatRowData {
	user_id: number;
	name: string;
	rank: string;
	is_me: boolean;
	joined_at: string | null;
	last_active: string | null;
	treasury: number;
	garrison_units: number;
	garrison_power: number;
	garrison_taken: number;
	shop_spent: number;
	build_spent: number;
	wars: number;
	wars_won: number;
	lands_won: number;
	exchanges: number;
}

const SORTS: [string, string][] = [
	["treasury", "💰 Казна"],
	["garrison", "⚔️ Рота"],
	["spent", "🛒 Траты"],
	["wars", "🗡 Войны"],
	["activity", "🕒 Актив"],
];
const RANK_EMOJI: Record<string, string> = { owner: "👑", deputy: "🥈", captain: "🎖", member: "👤" };

function ago(iso: string | null): string {
	if (!iso) return "давно";
	const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
	if (minutes < 10) return "в сети";
	if (minutes < 60) return `${minutes} мин назад`;
	if (minutes < 48 * 60) return `${Math.floor(minutes / 60)} ч назад`;
	return `${Math.floor(minutes / 1440)} дн назад`;
}

/** Вкладка «Вклад» — эффективность участников для клана (те же счётчики, что в боте). */
export function StatsTab() {
	const [sort, setSort] = useState("treasury");
	const { data, status, error } = useApi<{ sort: string; rows: StatRowData[] }>(`/clan/stats?sort=${sort}`);
	return (
		<Screen status={data ? "ready" : status} error={error}>
			<div className="chips-row" style={{ marginTop: 8 }}>
				{SORTS.map(([code, label]) => (
					<button key={code} type="button" className={`pill ${sort === code ? "on" : ""}`} onClick={() => setSort(code)}>
						{label}
					</button>
				))}
			</div>
			{data && (
				<Panel title="Вклад участников">
					{data.rows.map((r, i) => (
						<div key={r.user_id} className="clan-stat" style={{
							padding: "10px 0", borderBottom: "1px solid rgba(120,160,255,.15)",
							...(r.is_me ? { background: "rgba(245,185,66,.08)", borderRadius: 8 } : {}),
						}}>
							<div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontWeight: 800, fontSize: 14 }}>
								<span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
									{i + 1}. {RANK_EMOJI[r.rank] ?? "👤"} {r.name}
								</span>
								<span className="muted" style={{ fontSize: 11, flex: "none" }}>{ago(r.last_active)}</span>
							</div>
							<div className="muted" style={{ fontSize: 12, fontWeight: 700, marginTop: 4, lineHeight: 1.5 }}>
								💰 {fmt(r.treasury)} · ⚔️ {fmt(r.garrison_units)} бойц. ({fmt(r.garrison_power)} мощи)
								{r.garrison_taken > 0 && ` · забрал ${fmt(r.garrison_taken)}`}
								<br />
								🛒 {fmt(r.shop_spent)} · 🏗 {fmt(r.build_spent)} · 🗡 {r.wars_won}/{r.wars} (+{r.lands_won} зем.) · 🔄 {r.exchanges}
							</div>
						</div>
					))}
					<div className="muted clan-hint" style={{ marginTop: 8 }}>
						💰 внесено в казну · ⚔️ отдано в роту · 🛒 потрачено из казны на магазин · 🏗 на земли и здания ·
						🗡 атак выиграно/всего · 🔄 передач через обменник. Считается с 21.10.2026.
					</div>
				</Panel>
			)}
		</Screen>
	);
}
