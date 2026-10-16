import { ArrowLeftRight, Check, Crown, KeyRound, LogOut, MoreHorizontal, Swords, Trash2, UserPlus, Users, X } from "lucide-react";
import { useState } from "react";
import { apiGet } from "../../api";
import type { ClanCan, ClanInfo, ClanMember } from "../../types";
import { Panel, Spinner, fmt } from "../../components/ui";
import { Sheet } from "../../components/Sheet";
import { useAction } from "../../hooks/useApi";
import { ConfirmSheet } from "./shared";

type Confirm = { kind: "kick" | "transfer" | "leave"; member?: ClanMember };

const CONFIRM_PATH = { kick: "/clan/kick", transfer: "/clan/transfer", leave: "/clan/leave" } as const;
const CONFIRM_TITLE = { kick: "Исключить игрока", transfer: "Передать клан", leave: "Покинуть клан" } as const;

/** Вкладка «Состав»: участники и ранги, заявки, приглашение по нику, выход из клана. */
export function MembersTab({ clan, can, onChanged }: { clan: ClanInfo; can: ClanCan; onChanged: () => Promise<void> }) {
	const { run, busy } = useAction(onChanged);
	const [picked, setPicked] = useState<ClanMember | null>(null);
	const [confirm, setConfirm] = useState<Confirm | null>(null);
	const [inviting, setInviting] = useState(false);
	const [username, setUsername] = useState("");
	const [giving, setGiving] = useState<ClanMember | null>(null);
	const [resources, setResources] = useState<{ code: string; name: string; balance: number }[]>([]);
	const [resource, setResource] = useState<string>("");
	const [amount, setAmount] = useState("");
	const [deleting, setDeleting] = useState(false);
	const [deleteName, setDeleteName] = useState("");

	const openGive = async (m: ClanMember) => {
		setPicked(null);
		setGiving(m);
		setAmount("");
		try {
			const list = await apiGet<{ code: string; name: string; balance: number }[]>("/clan/exchange");
			setResources(list);
			setResource((cur) => cur || list[0]?.code || "");
		} catch {
			setResources([]);
		}
	};
	const picked_res = resources.find((r) => r.code === resource);

	const doConfirm = async () => {
		if (!confirm) return;
		const r = await run(CONFIRM_PATH[confirm.kind], confirm.member ? { user_id: confirm.member.user_id } : {});
		if (r) {
			setConfirm(null);
			setPicked(null);
		}
	};

	const confirmText = (c: Confirm): string => {
		if (c.kind === "kick") return `Исключить ${c.member?.name} из клана?`;
		if (c.kind === "transfer") return `Передать клан игроку ${c.member?.name}? Ты станешь рядовым участником.`;
		return "Выйти из клана? Купленные тобой уровни клана пропадут, уплаченное вернётся.";
	};

	return (
		<>
			<Panel title={`Состав ${clan.members.length}/${clan.max_members}`}>
				{clan.description && <div className="note" style={{ marginBottom: 10 }}>{clan.description}</div>}
				<div className="clan-members">
					{clan.members.map((m) => {
						const actionable = !m.is_me || m.can_kick || m.can_rank || m.can_access;
						return (
							<div key={m.user_id} className={`clan-member ${m.is_me ? "me" : ""}`}>
								<div className={`clan-rank rank-${m.rank}`}>{m.rank === "owner" ? <Crown size={15} /> : m.rank === "deputy" ? <Swords size={15} /> : <Users size={14} />}</div>
								<div style={{ flex: 1, minWidth: 0 }}>
									<div className="clan-member-name">{m.name}{m.is_me ? " · ты" : ""}</div>
									<div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>{m.rank_label}{m.username ? ` · @${m.username}` : ""}{m.garrison_access && m.rank !== "owner" ? " · 🔑 рота" : ""}</div>
								</div>
								{actionable && (
									<button className="clan-more" type="button" aria-label="Действия" onClick={() => setPicked(m)}><MoreHorizontal size={18} /></button>
								)}
							</div>
						);
					})}
				</div>
				<div className="muted" style={{ fontSize: 11, fontWeight: 700, marginTop: 10 }}>Мощь роты: {fmt(clan.power)}</div>
			</Panel>

			{can.manage && (
				<Panel title={`Заявки ${clan.requests.length}`} tone="green">
					{clan.requests.length === 0 ? (
						<div className="muted clan-hint">Новых заявок нет.</div>
					) : (
						<div className="clan-list">
							{clan.requests.map((r) => (
								<div key={r.user_id} className="clan-row">
									<div style={{ flex: 1, minWidth: 0 }}>
										<div className="clan-row-name">{r.name}</div>
										{r.username && <div className="muted clan-row-sub">@{r.username}</div>}
									</div>
									<button className="btn green small" type="button" disabled={busy} aria-label="Принять" onClick={() => run("/clan/requests/accept", { user_id: r.user_id })}><Check size={16} /></button>
									<button className="btn red small" type="button" disabled={busy} aria-label="Отклонить" onClick={() => run("/clan/requests/reject", { user_id: r.user_id })}><X size={16} /></button>
								</div>
							))}
						</div>
					)}
					<button className="btn block" style={{ marginTop: 10 }} type="button" onClick={() => setInviting(true)}><UserPlus size={17} />Пригласить по нику</button>
				</Panel>
			)}

			{can.leave ? (
				<button className="btn ghost block" type="button" onClick={() => setConfirm({ kind: "leave" })}><LogOut size={17} />Покинуть клан</button>
			) : (
				<>
					<div className="muted clan-hint" style={{ textAlign: "center" }}>Чтобы выйти, сначала передай клан другому участнику.</div>
					<button className="btn red block" type="button" onClick={() => setDeleting(true)}><Trash2 size={17} />Распустить клан</button>
				</>
			)}

			{picked && !confirm && (
				<Sheet title={picked.name} onClose={() => setPicked(null)}>
					<div className="muted clan-hint">{picked.rank_label}</div>
					{picked.can_rank && (
						<>
							<div className="section-title">Назначить ранг</div>
							<div className="clan-list">
								{clan.set_ranks.map((r) => (
									<button key={r.rank} type="button" className={`pill ${picked.rank === r.rank ? "on" : ""}`} style={{ flexDirection: "row" }} disabled={busy || picked.rank === r.rank} onClick={async () => {
										if (await run("/clan/rank", { user_id: picked.user_id, rank: r.rank })) setPicked(null);
									}}>{r.label}</button>
								))}
							</div>
						</>
					)}
					<div className="clan-list" style={{ marginTop: 12 }}>
						{!picked.is_me && (
							<button className="btn block" type="button" onClick={() => openGive(picked)}><ArrowLeftRight size={17} />Передать ресурс</button>
						)}
						{picked.can_access && (
							<button
								className={`btn ${picked.garrison_access ? "ghost" : "violet"} block`}
								type="button"
								disabled={busy}
								onClick={async () => {
									if (await run("/clan/garrison/access", { user_id: picked.user_id, allowed: !picked.garrison_access })) setPicked(null);
								}}
							>
								<KeyRound size={17} />{picked.garrison_access ? "Отнять доступ к роте" : "Выдать доступ к роте"}
							</button>
						)}
						{can.transfer && !picked.is_me && picked.rank !== "owner" && (
							<button className="btn gold block" type="button" onClick={() => setConfirm({ kind: "transfer", member: picked })}><Crown size={17} />Передать клан</button>
						)}
						{picked.can_kick && (
							<button className="btn red block" type="button" onClick={() => setConfirm({ kind: "kick", member: picked })}>Исключить</button>
						)}
					</div>
				</Sheet>
			)}

			{confirm && (
				<ConfirmSheet
					title={CONFIRM_TITLE[confirm.kind]}
					text={confirmText(confirm)}
					confirmLabel="Подтвердить"
					busy={busy}
					onClose={() => setConfirm(null)}
					onConfirm={doConfirm}
				/>
			)}

			{giving && (
				<Sheet title={`Обменник → ${giving.name}`} onClose={() => setGiving(null)}>
					<p className="muted clan-hint">Ресурс уходит с твоего счёта участнику клана сразу, без комиссии.</p>
					<div className="clan-res-grid">
						{resources.map((r) => (
							<button key={r.code} type="button" className={`pill ${resource === r.code ? "on" : ""}`} onClick={() => setResource(r.code)}>
								<b>{r.name}</b>
								<small>{fmt(r.balance)}</small>
							</button>
						))}
					</div>
					<div className="row" style={{ gap: 8, marginTop: 12 }}>
						<input className="clan-input" inputMode="numeric" placeholder="Сколько" value={amount} onChange={(e) => setAmount(e.currentTarget.value.replace(/\D/g, ""))} />
						{picked_res && (
							<button className="btn ghost small" type="button" onClick={() => setAmount(String(picked_res.balance))}>Всё</button>
						)}
					</div>
					<button className="btn block" style={{ marginTop: 12 }} type="button" disabled={busy || !resource || !Number(amount)} onClick={async () => {
						if (await run("/clan/exchange", { user_id: giving.user_id, resource, amount: Number(amount) })) setGiving(null);
					}}>{busy ? <Spinner /> : "Передать"}</button>
				</Sheet>
			)}

			{deleting && (
				<Sheet title="Распустить клан" onClose={() => setDeleting(false)}>
					<p className="muted clan-hint">
						Клан, его земли, здания, казна и рота пропадут навсегда. Всем, кто покупал уровни клана за донат, уплаченное вернётся.
						Чтобы подтвердить, впиши название клана: <b>{clan.name}</b>
					</p>
					<input className="clan-input" style={{ width: "100%" }} placeholder={clan.name} value={deleteName} onChange={(e) => setDeleteName(e.currentTarget.value)} />
					<button className="btn red block" style={{ marginTop: 12 }} type="button" disabled={busy || deleteName.trim().toLowerCase() !== clan.name.toLowerCase()} onClick={async () => {
						if (await run("/clan/delete", { confirm_name: deleteName })) setDeleting(false);
					}}>{busy ? <Spinner /> : "Распустить навсегда"}</button>
				</Sheet>
			)}

			{inviting && (
				<Sheet title="Приглашение" onClose={() => setInviting(false)}>
					<p className="muted clan-hint">Ник игрока в Telegram. Приглашение придёт ему в разделе «Кланы».</p>
					<input className="clan-input" style={{ width: "100%" }} autoFocus placeholder="@username" value={username} onChange={(e) => setUsername(e.currentTarget.value.replace(/\s/g, ""))} />
					<button className="btn block" style={{ marginTop: 12 }} type="button" disabled={busy || !username.replace("@", "")} onClick={async () => {
						if (await run("/clan/invite", { username })) {
							setInviting(false);
							setUsername("");
						}
					}}>{busy ? <Spinner /> : "Пригласить"}</button>
				</Sheet>
			)}
		</>
	);
}
