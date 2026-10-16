"""Разведка — отчёт о игроке и метки (константы)."""
from __future__ import annotations

CB_INTEL_OPEN = "intel:open"
CB_INTEL_MARKS = "intel:marks"
CB_INTEL_MARK_PREFIX = "intel:mark:"
"""f"{CB_INTEL_MARK_PREFIX}{user_id}" — поставить/снять метку."""

CB_INTEL_REPORTS = "intel:reports"  # список сохранённых отчётов разведки
