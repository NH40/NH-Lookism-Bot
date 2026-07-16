"""Чистые функции для вероятностных операций над агрегированными группами статистов.

Раньше тренировка/кража статистов работали построчно (ORDER BY random() LIMIT N,
затем UPDATE/DELETE по каждой выбранной строке) — O(N) на число бойцов. После
перехода на агрегированное хранение (squad_members: одна строка на группу
(rank, stars, base_power) со счётчиком count) те же эффекты нужно получать через
статистическую выборку на уровне группы — O(1) на группу, независимо от того,
сколько миллионов бойцов в ней лежит.
"""
import random

# Ниже этого n биномиальная выборка считается честным перебором испытаний —
# дешевле и без риска накопленной ошибки нормального приближения.
_EXACT_TRIAL_THRESHOLD = 5000


def sample_binomial(n: int, p: float) -> int:
    """Число успехов из n испытаний с вероятностью p, без построчной симуляции
    для больших n (нормальное приближение с округлением и отсечением в [0, n])."""
    if n <= 0:
        return 0
    p = min(1.0, max(0.0, p))
    if p <= 0:
        return 0
    if p >= 1:
        return n
    if n <= _EXACT_TRIAL_THRESHOLD:
        return sum(1 for _ in range(n) if random.random() < p)
    mean = n * p
    std = (n * p * (1 - p)) ** 0.5
    if std <= 0:
        return round(mean)
    return int(min(n, max(0, round(random.gauss(mean, std)))))


def split_three_way(n: int) -> tuple[int, int, int]:
    """Делит n на три случайные части с равной вероятностью каждого исхода —
    аналог floor(random()*3+1) для каждой из n единиц, но одной операцией."""
    if n <= 0:
        return 0, 0, 0
    d1 = sample_binomial(n, 1 / 3)
    d2 = sample_binomial(n - d1, 1 / 2)
    d3 = n - d1 - d2
    return d1, d2, d3


def largest_remainder_alloc(items: list[tuple], total_take: int) -> dict:
    """Пропорционально распределяет total_take между items=[(key, weight), ...],
    не превышая weight на элемент (метод наибольшего остатка). Возвращает
    {key: allocated}, сумма значений == min(total_take, сумма весов)."""
    total_weight = sum(w for _, w in items if w > 0)
    if total_weight <= 0 or total_take <= 0:
        return {}
    total_take = min(total_take, total_weight)
    raw = [(key, w, (w * total_take) / total_weight) for key, w in items if w > 0]
    alloc = {key: int(frac) for key, w, frac in raw}
    remaining = total_take - sum(alloc.values())
    order = sorted(raw, key=lambda t: (t[2] - int(t[2])), reverse=True)
    idx = 0
    guard = 0
    while remaining > 0 and order and guard < len(order) * 2:
        key, w, _frac = order[idx % len(order)]
        if alloc[key] < w:
            alloc[key] += 1
            remaining -= 1
        idx += 1
        guard += 1
    return {k: v for k, v in alloc.items() if v > 0}
