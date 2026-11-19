import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { imgUrl } from "../api";
import "./AbsoluteDrop.css";

export interface AbsoluteCard {
	name: string;
	image: string | null;
	rarity_label?: string;
}

const SPARKS = Array.from({ length: 18 }, (_, i) => i);

type Haptic = { HapticFeedback?: { notificationOccurred?: (kind: string) => void } };

/** Выпадение абсолюта (2026-11-19): полноэкранная вспышка, лучи, переворот карты, надпись. Тап — дальше. */
export function AbsoluteDrop({ cards, onDone }: { cards: AbsoluteCard[]; onDone: () => void }) {
	const [i, setI] = useState(0);
	const [ready, setReady] = useState(false);
	const card = cards[i];
	useEffect(() => {
		setReady(false);
		const id = setTimeout(() => setReady(true), 1600);
		try {
			const tg = (window as unknown as { Telegram?: { WebApp?: Haptic } }).Telegram?.WebApp;
			tg?.HapticFeedback?.notificationOccurred?.("success");
		} catch {
			/* вне Telegram */
		}
		return () => clearTimeout(id);
	}, [i]);
	if (!card) return null;
	const next = () => (i + 1 < cards.length ? setI(i + 1) : onDone());
	return createPortal(
		<div className="absd" key={i} onClick={next} role="dialog" aria-label={`Выпал абсолют: ${card.name}`}>
			<div className="absd-rays" />
			<div className="absd-flash" />
			<div className="absd-sparks">
				{SPARKS.map((s) => (
					<i key={s} style={{ ["--a" as string]: `${s * 20}deg`, ["--d" as string]: `${0.9 + (s % 5) * 0.12}s` }} />
				))}
			</div>
			<div className="absd-stage">
				<div className="absd-title">АБСОЛЮТ</div>
				<div className="absd-card">
					<div className="absd-card-inner">
						<div className="absd-back">♾</div>
						<div className="absd-front">{card.image ? <img src={imgUrl(card.image, 480)} alt={card.name} /> : <span>♾</span>}</div>
					</div>
				</div>
				<div className="absd-name">{card.name}</div>
				<div className={`absd-hint ${ready ? "on" : ""}`}>
					{cards.length > 1 ? `${i + 1} из ${cards.length} · ` : ""}нажми, чтобы продолжить
				</div>
			</div>
		</div>,
		document.body,
	);
}
