"""/start — вход в игру (константы).

Онбординг выбора страны/города — первая часть флоу из raw-notes, раздел «Карта»
(«Когда игрок начинает игру он выбирает страну... Далее он попадает на карту страны где
показаны все города данной страны»). Сам список стран/городов — не здесь (см.
`config/country`, `config/city`), тут только callback_data-префиксы, которые строит
клавиатура и матчит хендлер (см. CLAUDE.md, правило про `constant/` — один и тот же
префикс, не дублирование строки).
"""
from __future__ import annotations

CB_START_COUNTRY_PREFIX = "start:country:"
CB_START_CITY_PREFIX = "start:city:"
CB_START_CITY_PAGE_PREFIX = "start:citypage:"
CB_START_BACK_TO_COUNTRY = "start:back_country"
