import { Bell, Castle, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useEffect, useState } from "react";
import type { ClanBrowse, ClanNone } from "../../types";
import { BackHeader, Panel, Spinner, fmt } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import { ConfirmSheet } from "./shared";
import { Sheet } from "../../components/Sheet";

/** Клан не выбран: поиск и топ кланов, свой клан, приглашения. */
export function ClanFind({ data, reload }: { data: ClanNone; reload: () => Promise<void> }) {
	const [query, setQuery] = useState("");
	const [debounced, setDebounced] = useState("");
	const [page, setPage] = useState(0);
	const [tick, setTick] = useState(0);
	const [creating, setCreating] = useState(false);
	const [name, setName] = useState("");
	const [leaveApp, setLeaveApp] = useState(false);

	useEffect(() => {
		const t = setTimeout(() => {
			setDebounced(query.trim());
			setPage(0);
		}, 350);
		return () => clearTimeout(t);
	}, [query]);

	const initial = debounced === "" && page === 0 && tick === 0;
	const browse = useApi<ClanBrowse>(initial ? null : `/clan/browse?page=${page}&q=${encodeURIComponent(debounced)}&_=${tick}`);
	const list = initial ? data.browse : (browse.data ?? data.browse);

	const refresh = async () => {
		setTick((t) => t + 1);
		await reload();
	};
	const { run, busy } = useAction(refresh);
	const canCreate = data.coins >= data.create_cost;
	const nameOk = name.trim().length >= data.name_min && name.trim().length <= data.name_max;

	return (
		<div className="page">
			<BackHeader title="Кланы" subtitle="ты пока не в клане" to={ROUTE_MORE} />
			<label className="clan-search">
				<Search size={16} />
				<input placeholder="Название клана" value={query} onChange={(e) => setQuery(e.currentTarget.value)} maxLength={data.name_max} />
			</label>

			<Panel title={debounced ? "Результаты" : "Топ кланов"}>
				{list.items.length === 0 ? (
					<div className="clan-empty"><Castle size={24} />Кланов не найдено.</div>
				) : (
					<div className="clan-list">
						{list.items.map((c) => (
							<div key={c.clan_id} className={`clan-row ${c.top10 ? "top" : ""}`}>
								<div className="clan-row-ico"><Castle size={20} /></div>
								<div style={{ flex: 1, minWidth: 0 }}>
									<div className="clan-row-name">
										{c.name}
										{c.top10 && <span className="clan-top">ТОП-10</span>}
									</div>
									<div className="muted clan-row-sub">{c.members}/{c.max_members} участников · {c.lands} земель · ур. {c.donate_level}/5</div>
								</div>
								{c.applied ? (
									<button className="btn ghost small" type="button" disabled={busy} onClick={() => setLeaveApp(true)}>Отозвать</button>
								) : (
									<button className="btn small" type="button" disabled={busy || c.members >= c.max_members || data.application !== null} onClick={() => run("/clan/apply", { clan_id: c.clan_id })}>Заявка</button>
								)}
							</div>
						))}
					</div>
				)}
				{list.pages > 1 && (
					<div className="clan-pager">
						<button className="btn ghost small" type="button" disabled={list.page <= 0} onClick={() => setPage(list.page - 1)}><ChevronLeft size={16} /></button>
						<span className="muted">{list.page + 1} / {list.pages}</span>
						<button className="btn ghost small" type="button" disabled={list.page >= list.pages - 1} onClick={() => setPage(list.page + 1)}><ChevronRight size={16} /></button>
					</div>
				)}
				<div className="note muted" style={{ textAlign: "center", marginTop: 10 }}>
					Всего кланов: {list.total} · заявку можно подать только в один клан
				</div>
			</Panel>

			<Panel title="Свой клан" tone="gold">
				<div className="note" style={{ marginBottom: 10 }}>
					До 15 участников, 8 земель на старте, здания с бафами, клановая рота и войны за земли.
				</div>
				<div className="row">
					<div>
						<div className="disp clan-cost">{fmt(data.create_cost)}</div>
						<div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>у тебя {fmt(data.coins)} NHCoin</div>
					</div>
					<button className={`btn ${canCreate ? "gold" : "ghost"}`} type="button" disabled={!canCreate} onClick={() => setCreating(true)}>Создать</button>
				</div>
			</Panel>

			<Panel title="Приглашения">
				{data.invites.length === 0 ? (
					<div className="clan-empty"><Bell size={24} />Приглашений пока нет — кланы могут позвать тебя по нику.</div>
				) : (
					<div className="clan-list">
						{data.invites.map((i) => (
							<div key={i.clan_id} className="clan-row">
								<div className="clan-row-ico"><Castle size={20} /></div>
								<div className="clan-row-name" style={{ flex: 1, minWidth: 0 }}>{i.name}</div>
								<button className="btn green small" type="button" disabled={busy} onClick={() => run("/clan/invite/accept", { clan_id: i.clan_id })}>Принять</button>
								<button className="btn ghost small" type="button" disabled={busy} onClick={() => run("/clan/invite/decline", { clan_id: i.clan_id })}>Нет</button>
							</div>
						))}
					</div>
				)}
			</Panel>

			{creating && (
				<Sheet title="Новый клан" onClose={() => setCreating(false)}>
					<p className="muted clan-hint">Название от {data.name_min} до {data.name_max} символов. Спишется {fmt(data.create_cost)} NHCoin.</p>
					<input className="clan-input" style={{ width: "100%" }} autoFocus maxLength={data.name_max} placeholder="Название клана" value={name} onChange={(e) => setName(e.currentTarget.value)} />
					<button className="btn gold block" style={{ marginTop: 12 }} type="button" disabled={busy || !nameOk} onClick={async () => {
						const r = await run("/clan/create", { name: name.trim() });
						if (r) setCreating(false);
					}}>
						{busy ? <Spinner /> : "Создать клан"}
					</button>
				</Sheet>
			)}
			{leaveApp && data.application && (
				<ConfirmSheet title="Отозвать заявку" text={`Отозвать заявку в клан «${data.application.name}»?`} confirmLabel="Отозвать" busy={busy} onClose={() => setLeaveApp(false)} onConfirm={async () => {
					await run("/clan/cancel-application", { clan_id: data.application!.clan_id });
					setLeaveApp(false);
				}} />
			)}
		</div>
	);
}
