import type { ClanData } from "../../types";
import { Screen } from "../../components/ui";
import { useApi } from "../../hooks/useApi";
import { ClanFind } from "./ClanFind";
import { ClanHome } from "./ClanHome";
import "./Clan.css";

/** Клан: без клана — поиск/создание/приглашения (ClanFind), в клане — обзор и вкладки (ClanHome). */
export function ClanPage() {
	const { data, status, error, reload } = useApi<ClanData>("/clan");
	return (
		<Screen status={status} error={error}>
			{data && (data.clan && data.can ? <ClanHome data={data} clan={data.clan} can={data.can} reload={reload} /> : data.no_clan && <ClanFind data={data.no_clan} reload={reload} />)}
		</Screen>
	);
}
