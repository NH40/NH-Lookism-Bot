import { KeyRound, PackageMinus, PackagePlus } from "lucide-react";
import { useState } from "react";
import type { ClanGarrison, ClanInfo } from "../../types";
import { imgUrl } from "../../api";
import { Panel, Screen, countdown, fmt } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";
import { ConfirmSheet, PickAmountSheet, type PickItem } from "./shared";

type Mode = "put-statists" | "put-cards" | "take-statists" | "take-cards";

/** Вкладка «Рота»: состав роты, внести / забрать бойцов и уников, доступ к роте. */
export function GarrisonTab({ clan, onChanged }: { clan: ClanInfo; onChanged: () => Promise<void> }) {
	const { data, status, error, reload } = useApi<ClanGarrison>("/clan/garrison");
	const { run, busy } = useAction(async () => {
		await reload();
		await onChanged();
	});
	const [mode, setMode] = useState<Mode | null>(null);
	const [putAll, setPutAll] = useState<"statists" | "cards" | null>(null);

	const items = (g: ClanGarrison, m: Mode): PickItem[] => {
		const statists = (m === "put-statists" ? g.my_statists : g.statists).map((s) => ({ id: s.key, title: s.title, sub: `мощь ${fmt(s.power)} · ${fmt(s.quantity)} шт.`, max: s.quantity }));
		const cards = (m === "put-cards" ? g.my_cards : g.cards).map((c) => ({ id: c.code, title: c.name, sub: `мощь ${fmt(c.power)} · ${fmt(c.quantity)} шт.`, max: c.quantity, thumb: imgUrl(c.image, 160) ?? "" }));
		return m.endsWith("statists") ? statists : cards;
	};

	const locked = (g: ClanGarrison) => !g.can_take || g.needs_approval;

	return (
		<Screen status={data ? "ready" : status} error={error}>
			{data && (
				<>
					<Panel title="Рота клана" tone="red">
						<div className="row" style={{ marginBottom: 8 }}>
							<span className="muted" style={{ fontWeight: 700 }}>Мощь роты</span>
							<span className="disp" style={{ color: "var(--red-2)", fontSize: 18, fontWeight: 800 }}>{fmt(data.power)}</span>
						</div>
						{data.statists.length === 0 && data.cards.length === 0 && data.contracts.length === 0 ? (
							<div className="muted clan-hint">Рота пуста — внесите бойцов и уников.</div>
						) : (
							<>
								{data.statists.map((s) => (
									<div key={s.key} className="stat"><span>{s.title}</span><b>×{fmt(s.quantity)}</b></div>
								))}
								{data.cards.map((c) => (
									<div key={c.code} className="stat"><span>{c.name}</span><b>×{fmt(c.quantity)}</b></div>
								))}
								{data.contracts.map((k, i) => (
									<div key={`c${i}`} className="stat"><span>📜 {k.rank} · контракт, ещё {countdown(k.left_seconds)}</span><b>×{fmt(k.quantity)}</b></div>
								))}
							</>
						)}
						<div className="grid-2" style={{ marginTop: 10 }}>
							<button className="btn small" type="button" onClick={() => setMode("put-statists")}><PackagePlus size={15} />Бойцов</button>
							<button className="btn small" type="button" onClick={() => setMode("put-cards")}><PackagePlus size={15} />Уников</button>
						</div>
						<div className="grid-2" style={{ marginTop: 6 }}>
							<button className="btn ghost small" type="button" disabled={busy} onClick={() => setPutAll("statists")}>Всю армию</button>
							<button className="btn ghost small" type="button" disabled={busy} onClick={() => setPutAll("cards")}>Всех уников</button>
						</div>
						{!locked(data) && (
							<div className="grid-2" style={{ marginTop: 8 }}>
								<button className="btn ghost small" type="button" disabled={data.statists.length === 0} onClick={() => setMode("take-statists")}><PackageMinus size={15} />Забрать бойцов</button>
								<button className="btn ghost small" type="button" disabled={data.cards.length === 0} onClick={() => setMode("take-cards")}><PackageMinus size={15} />Забрать уников</button>
							</div>
						)}
						{!data.can_take && <div className="muted clan-hint">Забирать из роты можно через {countdown(data.take_in_seconds)} после вступления.</div>}
						{data.can_take && data.needs_approval && (
							<div style={{ marginTop: 10 }}>
								<div className="muted clan-hint">Забирать бойцов из роты можно только с правом, которое выдаёт владелец клана. Контрактников роты не забирает никто.</div>
								<button className="btn violet block" type="button" disabled={busy || data.pending} onClick={() => run("/clan/garrison/request-access")}>
									<KeyRound size={16} />{data.pending ? "Запрос ждёт ответа" : "Запросить доступ"}
								</button>
							</div>
						)}
					</Panel>

					{clan.access_requests.length > 0 && (
						<Panel title={`Запросы доступа ${clan.access_requests.length}`} tone="violet">
							{clan.access_requests.length === 0 ? (
								<div className="muted clan-hint">Запросов нет.</div>
							) : (
								<div className="clan-list">
									{clan.access_requests.map((r) => (
										<div key={r.user_id} className="clan-row">
											<div className="clan-row-name" style={{ flex: 1, minWidth: 0 }}>{r.name}</div>
											<button className="btn green small" type="button" disabled={busy} onClick={() => run("/clan/garrison/resolve-access", { user_id: r.user_id, approved: true })}>Одобрить</button>
											<button className="btn red small" type="button" disabled={busy} onClick={() => run("/clan/garrison/resolve-access", { user_id: r.user_id, approved: false })}>Нет</button>
										</div>
									))}
								</div>
							)}
						</Panel>
					)}

					{putAll && (
						<ConfirmSheet
							title={putAll === "statists" ? "Вся армия в роту" : "Все уники в роту"}
							text={putAll === "statists"
								? "Внести в роту ВСЕХ своих статистов из обоих лагерей? Забрать обратно — только по правилам роты."
								: "Внести в роту ВСЕ копии уников из армии (стоящие на позициях не трогаем)? Забрать обратно — только по правилам роты."}
							confirmLabel="Внести всё"
							tone="gold"
							busy={busy}
							onConfirm={async () => { await run(`/clan/garrison/put-all-${putAll}`, {}); setPutAll(null); }}
							onClose={() => setPutAll(null)}
						/>
					)}
					{mode && (
						<PickAmountSheet
							title={{ "put-statists": "Внести бойцов", "put-cards": "Внести уников", "take-statists": "Забрать бойцов", "take-cards": "Забрать уников" }[mode]}
							items={items(data, mode)}
							empty={mode.startsWith("put") ? "У тебя нечего вносить." : "В роте нечего забирать."}
							confirmLabel={mode.startsWith("put") ? "Внести" : "Забрать"}
							busy={busy}
							onClose={() => setMode(null)}
							onSubmit={async (id, amount) => {
								const body = mode.endsWith("statists") ? { key: id, amount } : { code: id, amount };
								if (await run(`/clan/garrison/${mode}`, body)) setMode(null);
							}}
						/>
					)}
				</>
			)}
		</Screen>
	);
}
