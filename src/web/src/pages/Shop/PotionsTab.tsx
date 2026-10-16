import { Clover, Coins, Dumbbell, Gem, Lock, Repeat, Shield, Swords, UserPlus, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { Sheet } from "../../components/Sheet";
import { fmt } from "../../components/ui";
import type { ShopPotion, ShopPotions } from "../../types";
import { Timer, type TabProps } from "./shared";

const ICONS: Record<string, [LucideIcon, string]> = {
	power: [Swords, "#ff7a8a"],
	guard: [Shield, "#3ddc84"],
	wealth: [Coins, "#f5b942"],
	training: [Dumbbell, "#8ff0b8"],
	recruit: [UserPlus, "#7fd4ff"],
	luck: [Clover, "#8ff0b8"],
	hunter: [Gem, "#c4a6ff"],
};

export function PotionsTab({ data, coins, run, busy }: TabProps & { data: ShopPotions }) {
	const [pick, setPick] = useState<{ kind: string; tier: number } | null>(null);
	const potion = pick ? data.potions.find((p) => p.kind === pick.kind) : undefined;
	const tier = potion?.tiers.find((t) => t.tier === pick?.tier);
	const active = data.potions.filter((p) => p.active_tier > 0).length;

	const act = async (path: string, body: object) => {
		const r = await run(path, body);
		if (r) setPick(null);
	};

	return (
		<>
			<div className="shop-note muted" style={{ padding: "0 2px" }}>
				Доступны тиры 1–{data.max_tier} · выше открывает гений медицины.{" "}
				{active ? `Действует зелий: ${active}.` : "Сейчас ничего не действует."}
				{data.auto_slots > 0 && ` Слотов авто-зелий: ${data.auto_slots}.`}
			</div>
			<div className="shop-list">
				{data.potions.map((p: ShopPotion) => {
					const [Icon, color] = ICONS[p.kind] ?? [Coins, "#7fd4ff"];
					return (
						<div key={p.kind} className={`shop-item ${p.active_tier ? "live" : ""}`}>
							<div className="shop-item-head">
								<span className="name"><Icon size={16} color={color} />{p.name}</span>
								<span className="muted" style={{ fontSize: 11, fontWeight: 700, display: "flex", gap: 6, alignItems: "center" }}>
									{p.auto_tier > 0 && <Repeat size={12} color="var(--cyan)" />}
									{p.active_tier ? <span style={{ color: "var(--gold-2)" }}>T{p.active_tier} · <Timer seconds={p.left_seconds} /></span> : `${p.minutes} мин`}
								</span>
							</div>
							<div className="shop-tiers">
								{p.tiers.map((t) => (
									<button
										key={t.tier}
										type="button"
										className={`btn small ${t.unlocked ? (t.tier === p.active_tier ? "gold" : "ghost") : "ghost locked"}`}
										disabled={!t.unlocked}
										onClick={() => setPick({ kind: p.kind, tier: t.tier })}
									>
										{!t.unlocked && <Lock size={12} color="var(--muted)" />}T{t.tier} · {fmt(t.price)}
									</button>
								))}
							</div>
						</div>
					);
				})}
			</div>

			{potion && tier && (
				<Sheet title={`${potion.name} · T${tier.tier}`} onClose={() => setPick(null)}>
					<div className="shop-sheet-body">
						<div className="shop-note">{potion.about}</div>
						<div className="shop-quote">
							<div className="line"><span className="muted">Эффект</span><span style={{ textAlign: "right" }}>{tier.effect || "—"}</span></div>
							<div className="line" style={{ marginTop: 6 }}><span className="muted">Срок</span><span>{potion.minutes} мин</span></div>
							<div className="line" style={{ marginTop: 6 }}><span className="muted">Цена</span><span className="total">{fmt(tier.price)}</span></div>
						</div>
						<div className="shop-note muted">Новое зелье этого вида заменяет действующее и запускает срок заново.</div>
						<button
							className={`btn gold ${coins >= tier.price && !busy ? "" : "off"}`}
							type="button"
							disabled={coins < tier.price || busy}
							onClick={() => act("/shop/potion/buy", { kind: potion.kind, tier: tier.tier })}
						>
							{coins >= tier.price ? `Выпить за ${fmt(tier.price)}` : "Не хватает NHCoin"}
						</button>
						{data.auto_slots > 0 &&
							(potion.auto_tier === tier.tier ? (
								<button className="btn ghost" type="button" disabled={busy} onClick={() => act("/shop/potion/auto", { kind: potion.kind, tier: 0 })}>
									<Repeat size={16} />Выключить авто
								</button>
							) : (
								<button className="btn violet" type="button" disabled={busy} onClick={() => act("/shop/potion/auto", { kind: potion.kind, tier: tier.tier })}>
									<Repeat size={16} />Авто-продление T{tier.tier}
								</button>
							))}
					</div>
				</Sheet>
			)}
		</>
	);
}
