// Империя (API `/api/empire`) — налоги, персональные ставки, война императоров, саботаж.

export interface EmpireOverride {
  username: string | null;
  name: string;
  percent: number;
}

export interface EmpireIncomingWar {
  war_id: number;
  attacker: string;
  expires_in_seconds: number;
}

export interface EmpireWarHistory {
  war_id: number;
  as_attacker: boolean;
  other: string;
  won: boolean | null;
  forfeit: boolean;
  cities: number;
  treasury: number;
}

export interface EmpireRuler {
  cities: number;
  players: number;
  tax_percent: number;
  collected: number;
  treasury: number;
  holdings: number;
  overrides: EmpireOverride[];
  overrides_total: number;
  sabotage_total: number;
  sabotage_success: number;
  sabotage_hours: number;
  incoming: EmpireIncomingWar | null;
  war_cooldown_seconds: number;
  history: EmpireWarHistory[];
}

export interface SabotageAction {
  code: string;
  label: string;
  chance: number;
  cooldown_seconds: number;
}

export interface EmpireSubject {
  emperor: string;
  emperor_username: string | null;
  emperor_cities: number;
  emperor_country: string | null;
  tax_percent: number;
  actions: SabotageAction[];
}

export interface EmpireData {
  ruler: EmpireRuler | null;
  subject: EmpireSubject | null;
  tax_min: number;
  tax_max: number;
  subtitle: string;
}

export interface EmpireSubjectRate {
  user_id: number;
  name: string;
  percent: number;
  own: boolean;
}

export interface EmpireWarTarget {
  user_id: number;
  name: string;
  country: string | null;
  cities: number;
  treasury: number;
  shield_seconds: number;
}

export interface EmpireWarTargets {
  items: EmpireWarTarget[];
  page: number;
  has_more: boolean;
}
