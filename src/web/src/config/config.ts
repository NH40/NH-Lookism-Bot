// Русские подписи фазы игрока — зеркало src/bot/texts/profile/profile.py: PHASE_LABELS
// (единственный источник правды на стороне бота). Живёт в config/, а не в constants/ — это
// визуальный текстовый баланс (отображаемая подпись), не строка-идентификатор для
// сравнения ===/startswith, тот же принцип, что TIER_INFO в Universe Anime Planet
// (config/config.ts) — зеркало игровых чисел/подписей бота, не сравниваемый ключ.
export const PHASE_LABELS: Record<string, string> = {
  gang: "Банда",
  circle: "Круг",
  fist: "Кулак",
};
