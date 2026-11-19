import { Megaphone } from "lucide-react";
import { useState } from "react";
import type { ClanCan, ClanInfo } from "../../types";
import { Panel, Spinner, countdown } from "../../components/ui";
import { Sheet } from "../../components/Sheet";
import { useAction } from "../../hooks/useApi";

/** Объявление клана (2026-11-19): последнее висит у всех участников, владелец и зам пишут новое — участникам уходит пуш. */
export function AnnouncePanel({ clan, can, onChanged }: { clan: ClanInfo; can: ClanCan; onChanged: () => Promise<void> }) {
	const { run, busy } = useAction(onChanged);
	const [writing, setWriting] = useState(false);
	const [text, setText] = useState("");
	if (!clan.announcement && !can.manage) return null;
	const cd = clan.announce_cooldown ?? 0;
	const when = clan.announcement_at ? new Date(clan.announcement_at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "";
	return (
		<>
			<Panel title="Объявление" tone="gold">
				{clan.announcement ? (
					<>
						<div className="muted" style={{ fontSize: 11, fontWeight: 700, marginBottom: 6 }}>{when}</div>
						<div className="note" style={{ whiteSpace: "pre-line" }}>{clan.announcement}</div>
					</>
				) : (
					<div className="muted" style={{ fontSize: 12, fontWeight: 600 }}>Пока объявлений нет.</div>
				)}
				{can.manage && (
					<button className="btn gold block" style={{ marginTop: 10 }} type="button" disabled={cd > 0} onClick={() => setWriting(true)}>
						<Megaphone size={16} />{cd > 0 ? `Новое через ${countdown(cd)}` : "Написать объявление"}
					</button>
				)}
			</Panel>
			{writing && (
				<Sheet title="Объявление клану" onClose={() => setWriting(false)}>
					<p className="muted clan-hint">Участникам придёт пуш, текст повиснет на экране клана. Одно объявление в час.</p>
					<textarea className="clan-input" style={{ width: "100%", minHeight: 120, padding: 10, resize: "vertical" }} autoFocus
						maxLength={clan.announce_max || 1000} value={text} onChange={(e) => setText(e.currentTarget.value)} />
					<div className="muted" style={{ fontSize: 11, fontWeight: 700, textAlign: "right" }}>{text.length}/{clan.announce_max || 1000}</div>
					<button className="btn gold block" style={{ marginTop: 10 }} type="button" disabled={busy || !text.trim()} onClick={async () => {
						if (await run("/clan/announce", { text: text.trim() })) {
							setWriting(false);
							setText("");
						}
					}}>
						{busy ? <Spinner /> : "Опубликовать"}
					</button>
				</Sheet>
			)}
		</>
	);
}
