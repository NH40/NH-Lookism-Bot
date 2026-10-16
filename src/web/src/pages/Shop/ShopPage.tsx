import { useSearchParams } from "react-router-dom";
import type { ShopData } from "../../types";
import { BackHeader, Screen, fmt } from "../../components/ui";
import { ROUTE_MORE } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import { ContractsTab } from "./ContractsTab";
import { DepositsTab } from "./DepositsTab";
import { PotionsTab } from "./PotionsTab";
import { StorageTab } from "./StorageTab";
import "../../styles/game-screens.css";
import "./Shop.css";

const TABS = [
	{ id: "contracts", label: "Контракты" },
	{ id: "potions", label: "Зелья" },
	{ id: "storage", label: "Ячейки" },
	{ id: "deposits", label: "Вклады" },
] as const;

export function ShopPage() {
	const { data, status, error, reload } = useApi<ShopData>("/shop");
	const { run, busy } = useAction(reload);
	const [params, setParams] = useSearchParams();
	const tab = TABS.find((t) => t.id === params.get("tab"))?.id ?? "contracts";

	const common = { coins: data?.nh_coins ?? 0, run, busy };

	return (
		<Screen status={status} error={error}>
			{data && (
				<div className="page">
					<BackHeader
						title="Магазин"
						backLabel="Ещё"
						to={ROUTE_MORE}
						subtitle={`NHCoin: ${fmt(data.nh_coins)} · к сбору ${fmt(data.pending)}`}
					/>
					<div className="grid-4">
						{TABS.map((t) => (
							<button
								key={t.id}
								type="button"
								className={`pill ${tab === t.id ? "on" : ""}`}
								onClick={() => setParams({ tab: t.id }, { replace: true })}
							>
								{t.label}
							</button>
						))}
					</div>
					<div className="page shop-tab-fade" key={tab} style={{ padding: 0 }}>
						{tab === "contracts" && <ContractsTab data={data.contracts} {...common} />}
						{tab === "potions" && <PotionsTab data={data.potions} {...common} />}
						{tab === "storage" && <StorageTab data={data.storage} {...common} />}
						{tab === "deposits" && <DepositsTab data={data.deposits} {...common} />}
					</div>
				</div>
			)}
		</Screen>
	);
}
