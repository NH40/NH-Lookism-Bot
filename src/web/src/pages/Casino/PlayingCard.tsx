import type { PlayingCardData } from "../../types";

/** Игральная карта: ранг + масть стилизованным div, рубашка для скрытой. */
export function PlayingCard({ card, small }: { card: PlayingCardData; small?: boolean }) {
	if (card.hidden) return <div className={`pc pc-back ${small ? "pc-small" : ""}`} aria-label="Скрытая карта" />;
	const red = card.suit === "♥" || card.suit === "♦";
	return (
		<div className={`pc ${red ? "pc-red" : ""} ${small ? "pc-small" : ""}`} aria-label={`${card.rank}${card.suit}`}>
			<span className="pc-rank">{card.rank}</span>
			<span className="pc-suit">{card.suit}</span>
		</div>
	);
}

export function CardRow({ cards, small }: { cards: PlayingCardData[]; small?: boolean }) {
	return (
		<div className="pc-row">
			{cards.map((c, i) => (
				<PlayingCard key={i} card={c} small={small} />
			))}
		</div>
	);
}
