// Разведка (API `/api/intel`) и гайд (API `/api/guide`).

export interface IntelLog {
  at: string;
  text: string;
}

export interface ScoutField {
  field: string;
  label: string;
  value: string;
  seen: "exact" | "range" | "hidden";
}

export interface ScoutReport {
  target_id: number;
  name: string;
  ago: string;
  fields: ScoutField[];
  trap_lost: number;
  marked: boolean;
  can_mark: boolean;
  can_sabotage: boolean;
  sabotage_actions: [string, string, number][];
}

export interface ScoutRow {
  target_id: number;
  name: string;
  ago: string;
}

export interface IntelData {
  scout: number;
  logs: number;
  fields: number;
  marks_limit: number;
  marks: { target_id: number; name: string; hidden: boolean; entries: IntelLog[] }[];
}

export interface GuideData {
  sections: { code: string; title: string; body: string }[];
}
