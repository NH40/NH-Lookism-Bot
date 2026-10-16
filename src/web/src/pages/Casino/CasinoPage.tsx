import { useEffect, useState } from "react";
import type { CasinoData } from "../../types";
import { BackHeader, Screen } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useApi } from "../../hooks/useApi";
import { BlackjackTab } from "./BlackjackTab";
import { PokerTab } from "./PokerTab";
import { SlotsTab } from "./SlotsTab";
import "./Casino.css";

type Tab = "slots" | "blackjack" | "poker";
const TABS: { id: Tab; label: string }[] = [
	{ id: "slots", label: "Слоты" },
	{ id: "blackjack", label: "Блэкджек" },
	{ id: "poker", label: "Покер" },
];

export function CasinoPage() {
	const [tab, setTab] = useState<Tab>("slots");
	const { data, status, error, reload } = useApi<CasinoData>("/casino");

	// Лобби покера живое: обновляем раз в 5 с, пока открыта вкладка.
	useEffect(() => {
		if (tab !== "poker") return;
		const id = window.setInterval(() => void reload(), 5000);
		return () => window.clearInterval(id);
	}, [tab, reload]);

	return (
		<Screen status={status} error={error}>
			{data && (
				<div className="page">
					<BackHeader title="Казино" to={ROUTE_MORE} />
					<div className="seg" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
						{TABS.map((t) => (
							<button key={t.id} type="button" className={`pill ${tab === t.id ? "on" : ""}`} onClick={() => setTab(t.id)}>
								{t.label}
							</button>
						))}
					</div>
					{tab === "slots" && <SlotsTab data={data} reload={reload} />}
					{tab === "blackjack" && <BlackjackTab data={data} reload={reload} />}
					{tab === "poker" && <PokerTab data={data} reload={reload} />}
				</div>
			)}
		</Screen>
	);
}
