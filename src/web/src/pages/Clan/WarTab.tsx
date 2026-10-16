import { ChevronLeft, ChevronRight, Shield, Swords, Trophy } from "lucide-react";
import { useState } from "react";
import type { ClanAttackResult, ClanCan, ClanWar, ClanWarTarget } from "../../types";
import { Panel, Screen, StatRow, countdown, fmt } from "../../components/ui";
import { Sheet } from "../../components/Sheet";
import { useAction, useApi } from "../../hooks/useApi";
import { ConfirmSheet } from "./shared";

/** Вкладка «Война»: цели для нападения, кулдаун и щит, история войн. */
export function WarTab({ can, onChanged }: { can: ClanCan; onChanged: () => Promise<void> }) {
	const [page, setPage] = useState(0);
	const { data, status, error, reload } = useApi<ClanWar>(`/clan/war?page=${page}`);
	const { run, busy } = useAction(async () => {
		await reload();
		await onChanged();
	});
	const [target, setTarget] = useState<ClanWarTarget | null>(null);
	const [result, setResult] = useState<ClanAttackResult | null>(null);

	const attack = async () => {
		if (!target) return;
		const r = (await run("/clan/war/attack", { clan_id: target.clan_id })) as ClanAttackResult | null;
		setTarget(null);
		if (r) setResult(r);
	};

	return (
		<Screen status={data ? "ready" : status} error={error}>
			{data && (
				<>
					<Panel title="Готовность" tone="red">
						<StatRow icon={<Swords size={16} color="var(--red)" />} label="Мощь роты" value={fmt(data.power)} />
						<StatRow label="Следующее нападение" value={data.cooldown_seconds > 0 ? `через ${countdown(data.cooldown_seconds)}` : "можно"} />
						<StatRow icon={<Shield size={16} color="var(--green)" />} label="Щит клана" value={data.shield_seconds > 0 ? countdown(data.shield_seconds) : "нет"} />
						{!can.manage && <div className="muted clan-hint">Нападают владелец и заместитель.</div>}
					</Panel>

					<Panel title="Цели">
						{data.targets.length === 0 ? (
							<div className="muted clan-hint">Других кланов пока нет.</div>
						) : (
							<div className="clan-list">
								{data.targets.map((t) => (
									<div key={t.clan_id} className="clan-row">
										<div style={{ flex: 1, minWidth: 0 }}>
											<div className="clan-row-name">{t.name}</div>
											<div className="muted clan-row-sub">{t.members} участн. · {t.lands} земель{t.shielded ? " · под щитом" : ""}</div>
										</div>
										{can.manage && (
											<button className="btn red small" type="button" disabled={busy || t.shielded || data.cooldown_seconds > 0} onClick={() => setTarget(t)}>
												<Swords size={14} />Напасть
											</button>
										)}
									</div>
								))}
							</div>
						)}
						{data.pages > 1 && (
							<div className="clan-pager">
								<button className="btn ghost small" type="button" disabled={data.page <= 0} onClick={() => setPage(data.page - 1)}><ChevronLeft size={16} /></button>
								<span className="muted">{data.page + 1} / {data.pages}</span>
								<button className="btn ghost small" type="button" disabled={data.page >= data.pages - 1} onClick={() => setPage(data.page + 1)}><ChevronRight size={16} /></button>
							</div>
						)}
					</Panel>

					<Panel title="История войн">
						{data.history.length === 0 ? (
							<div className="muted clan-hint">Войн ещё не было.</div>
						) : (
							data.history.map((w, i) => (
								<div key={i} className="stat" style={{ alignItems: "flex-start" }}>
									<Trophy size={16} color={w.won_by_me ? "var(--gold)" : "var(--muted)"} />
									<div style={{ flex: 1, minWidth: 0 }}>
										<div className="clan-row-name">{w.i_attacked ? `Нападение на «${w.defender}»` : `«${w.attacker}» напал на нас`}</div>
										<div className="muted clan-row-sub">
											{w.won_by_me ? "Победа" : "Поражение"} · земель {w.i_attacked === w.won_by_me ? "+" : "−"}{w.lands_taken} · {new Date(w.created_at).toLocaleDateString("ru-RU")}
										</div>
									</div>
								</div>
							))
						)}
					</Panel>

					{target && (
						<ConfirmSheet
							title="Напасть на клан"
							text={`Напасть на «${target.name}» (${target.lands} земель)? Бой решается сразу, потери рот необратимы. Следующее нападение будет доступно через сутки.`}
							confirmLabel="В бой"
							busy={busy}
							onClose={() => setTarget(null)}
							onConfirm={attack}
						/>
					)}
					{result && (
						<Sheet title={result.won ? "Победа" : "Поражение"} onClose={() => setResult(null)}>
							<p className="clan-hint">{result.message}</p>
							<StatRow label="Мощь рот" value={`${fmt(result.attacker_power)} против ${fmt(result.defender_power)}`} />
							<StatRow label="Раундов" value={result.rounds} />
							<StatRow label="Наши потери" value={fmt(result.attacker_dead)} />
							<StatRow label="Потери врага" value={fmt(result.defender_dead)} />
							{result.won && <StatRow label="Земли" value={`+${result.lands_gained} (у врага −${result.lands_taken})`} />}
							{result.won && <StatRow label="Казна" value={`+${fmt(result.treasury_taken)}`} />}
							<button className="btn block" style={{ marginTop: 12 }} type="button" onClick={() => setResult(null)}>Закрыть</button>
						</Sheet>
					)}
				</>
			)}
		</Screen>
	);
}
