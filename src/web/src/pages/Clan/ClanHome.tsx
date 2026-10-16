import { Landmark, Shield, Swords, Users } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import type { ClanCan, ClanData, ClanInfo } from "../../types";
import { BackHeader, fmt } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { GarrisonTab } from "./GarrisonTab";
import { LandsTab } from "./LandsTab";
import { MembersTab } from "./MembersTab";
import { WarTab } from "./WarTab";

const TABS = [
	{ code: "members", label: "Состав", icon: <Users size={15} /> },
	{ code: "lands", label: "Земли", icon: <Landmark size={15} /> },
	{ code: "garrison", label: "Рота", icon: <Shield size={15} /> },
	{ code: "war", label: "Война", icon: <Swords size={15} /> },
] as const;
type Tab = (typeof TABS)[number]["code"];

function isTab(v: string | null): v is Tab {
	return TABS.some((t) => t.code === v);
}

/** Клан игрока: статистика сверху, вкладки Состав / Земли / Рота / Война (?tab=). */
export function ClanHome({ data, clan, can, reload }: { data: ClanData; clan: ClanInfo; can: ClanCan; reload: () => Promise<void> }) {
	const [params, setParams] = useSearchParams();
	const raw = params.get("tab");
	const tab: Tab = isTab(raw) ? raw : "members";

	return (
		<div className="page">
			<BackHeader title={clan.name} subtitle={data.my_rank_label ?? undefined} to={ROUTE_MORE} />
			<div className="grid-3">
				<div className="chip clan-chip"><span className="muted">Земли</span><span className="disp" style={{ color: "var(--cyan-2)" }}>{clan.lands}/{clan.max_lands}</span></div>
				<div className="chip clan-chip"><span className="muted">Казна</span><span className="disp" style={{ color: "var(--gold-2)" }}>{fmt(clan.treasury)}</span></div>
				<div className="chip clan-chip"><span className="muted">Уровень</span><span className="disp" style={{ color: "var(--violet-2)" }}>{clan.donate_level}/{clan.max_donate_level}</span></div>
			</div>
			<div className="seg" role="tablist" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
				{TABS.map((t) => (
					<button key={t.code} type="button" role="tab" aria-selected={t.code === tab} className={`pill ${t.code === tab ? "on" : ""}`} style={{ minHeight: 44 }} onClick={() => setParams({ tab: t.code }, { replace: true })}>
						{t.icon}
						{t.label}
					</button>
				))}
			</div>
			{tab === "members" && <MembersTab clan={clan} can={can} onChanged={reload} />}
			{tab === "lands" && <LandsTab can={can} onChanged={reload} />}
			{tab === "garrison" && <GarrisonTab clan={clan} onChanged={reload} />}
			{tab === "war" && <WarTab can={can} onChanged={reload} />}
		</div>
	);
}
