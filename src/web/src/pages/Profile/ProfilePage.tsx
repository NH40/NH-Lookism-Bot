import { Coins, Crosshair, Dna, Eye, FlaskConical, Gem, Home, Lightbulb, Move, Route, Shield, Sparkles, Swords, Ticket, Zap } from "lucide-react";
import type { ReactNode } from "react";
import { imgUrl } from "../../api";
import type { ProfileDevItem, ProfileData } from "../../types";
import { Bar, Chip, Panel, Screen, StatRow, countdown, fmt } from "../../components/ui";
import { Link } from "react-router-dom";
import { ROUTE_STATS } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import { getWebApp } from "../../telegram";
import "./Profile.css";

const STAT_ICONS: Record<string, ReactNode> = {
  strength: <Swords size={16} color="#ff7a8a" />,
  speed: <Zap size={16} color="#7fd4ff" />,
  endurance: <Shield size={16} color="#3ddc84" />,
  agility: <Eye size={16} color="#f5b942" />,
};

const DEV_ICONS: Record<ProfileDevItem["kind"], { icon: ReactNode; label: string }> = {
  bloodline: { icon: <Dna size={18} color="#ff7a8a" />, label: "родословная" },
  path: { icon: <Route size={18} color="#7fd4ff" />, label: "путь" },
  technique: { icon: <Move size={18} color="#f5b942" />, label: "техника" },
  genius: { icon: <Lightbulb size={18} color="#a78bfa" />, label: "гений" },
};

export function ProfilePage() {
  const { data, status, error, reload } = useApi<ProfileData>("/profile");
  const { run, busy } = useAction(reload);
  return (
    <Screen status={status} error={error}>
      {data && <ProfileView p={data} run={run} busy={busy} />}
    </Screen>
  );
}

function ProfileView({ p, run, busy }: { p: ProfileData; run: (path: string, body?: unknown) => Promise<unknown>; busy: boolean }) {
  const name = p.display_name ?? (p.username ? `@${p.username}` : "Игрок");
  const sub = [p.gang_name ? `Банда «${p.gang_name}»` : null, p.clan_name ? `Клан «${p.clan_name}»` : null, p.city?.name].filter(Boolean).join(" · ");
  // Аватар: карта на позиции «Лидер» → фото Telegram → эмблема с инициалами.
  const avatar = p.avatar ? imgUrl(p.avatar, 320) : (getWebApp()?.initDataUnsafe.user?.photo_url ?? null);
  const initials = name.replace("@", "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join("") || "?";
  const total = p.attack_power + p.defense_power;
  const attackShare = total > 0 ? p.attack_power : 0;
  const pp = p.phase_progress;

  return (
    <div className="page">
      <div className="pf-head">
        <div className="portrait">
          {avatar ? <img src={avatar} alt="Портрет" /> : <div className="pf-initial">{initials}</div>}
        </div>
        <div className="pf-info">
          <div className="disp pf-name">{name}</div>
          <div className="muted pf-sub">{sub || "—"}</div>
          <div className="pf-badges">
            <span className="pf-badge">{p.phase_label.toUpperCase()}</span>
            <span className="pf-badge gold">{p.potential_label}</span>
          </div>
        </div>
        <div className="pf-online">
          <b>
            <span className="pf-dot" />
            {fmt(p.online)}
          </b>
          <small>в сети</small>
        </div>
      </div>

      {p.potential_cost != null && p.potential_next && (
        <Panel title="ПОТЕНЦИАЛ" tone="gold" badgeMark="🧬">
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 700, marginBottom: 5 }}>
            <span className="muted">До «{p.potential_next}»</span>
            <span>{fmt(p.potential_points ?? 0)} / {fmt(p.potential_cost)}</span>
          </div>
          <Bar value={p.potential_points ?? 0} max={p.potential_cost} fill="gold" />
          <div className="muted" style={{ fontSize: 11, fontWeight: 700, margin: "6px 0" }}>
            Очки потенциала копятся за активность и сгорают при удалении банды и пробуждении.
          </div>
          <button className={`btn gold block ${(p.potential_points ?? 0) >= p.potential_cost ? "" : "off"}`} type="button"
            disabled={busy || (p.potential_points ?? 0) < p.potential_cost} onClick={() => run("/potential-up")}>
            Повысить потенциал
          </button>
        </Panel>
      )}

      <div className="grid-3">
        <Chip variant="gold" icon={<Coins size={18} color="#f5b942" />} value={fmt(p.nh_coins)} label="NHCoin" />
        <Chip icon={<Ticket size={18} color="#7fd4ff" />} value={`${p.tickets}/${p.tickets_cap}`} label="тикеты" />
        <Chip variant="violet" icon={<Gem size={18} color="#a78bfa" />} value={fmt(p.donate_balance)} label="донат" />
      </div>

      <Panel title="Статус">
        <div className="row pf-row">
          <span>Боевая мощь</span>
          <span className="disp pf-power">{p.army_power.toLocaleString("ru-RU")}</span>
        </div>
        <div className="pf-gap">
          <Bar value={attackShare} max={total} fill="red" />
          <div className="row muted" style={{ fontSize: 10, fontWeight: 700, marginTop: 4 }}>
            <span>атака {fmt(p.attack_power)}</span>
            <span>защита {fmt(p.defense_power)}</span>
          </div>
        </div>
        {pp ? (
          <>
            <div className="row pf-row">
              <span>Путь к фазе «{pp.target_label}»</span>
              <span className="muted">
                {pp.scope_label} {pp.current}/{pp.total}
              </span>
            </div>
            <Bar value={pp.current} max={pp.total} fill="violet" />
          </>
        ) : (
          <div className="muted pf-row">Высшая фаза достигнута</div>
        )}
        <div className="pf-stats">
          {p.stats.map((s) => (
            <StatRow key={s.code} icon={STAT_ICONS[s.code] ?? <Crosshair size={16} />} label={s.label} value={s.rank} />
          ))}
          <StatRow icon={<Sparkles size={16} color="#a78bfa" />} label="Очки развития" value={p.dev_points} />
          <StatRow icon={<Home size={16} color="#7fd4ff" />} label="Районы" value={p.districts} />
        </div>
        <Link to={ROUTE_STATS} className="btn small block" style={{ marginTop: 10 }}>Прокачать характеристики</Link>
        {p.nh_coins_pending > 0 && <div className="pf-pending">В бизнесе накоплено {fmt(p.nh_coins_pending)} NHCoin</div>}
      </Panel>

      <Panel title="Развитие">
        {p.development.length === 0 ? (
          <div className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
            Пока ничего не выбрано — родословная, путь, техника и гений открываются в разделе «Развитие».
          </div>
        ) : (
          <div className="grid-2">
            {p.development.map((d) => (
              <Chip key={`${d.kind}-${d.label}`} icon={DEV_ICONS[d.kind].icon} value={`${d.label} · ${d.level}`} label={DEV_ICONS[d.kind].label} />
            ))}
          </div>
        )}
        {p.second_body && <div className="pf-pending" style={{ color: "var(--violet-2)" }}>Второе тело открыто</div>}
      </Panel>

      {p.absolutes && p.absolutes.items.length > 0 && (
        <Panel title="♾ Абсолюты" tone="gold">
          {p.absolutes.blocked_seconds > 0 && (
            <div className="pf-abs-blocked">Заблокированы Арианом противника ещё {countdown(p.absolutes.blocked_seconds)}</div>
          )}
          {p.absolutes.items.map((a) => (
            <div key={a.code} className={`pf-abs ${p.absolutes && p.absolutes.blocked_seconds > 0 ? "off" : ""}`}>
              <b>{a.name}{a.via_stylist ? " · через Стилиста" : ""}</b>
              <div className="muted pf-potion-effect">{a.perk}</div>
            </div>
          ))}
        </Panel>
      )}

      {p.potions.length > 0 && (
        <Panel title="Зелья действуют">
          {p.potions.map((z) => (
            <div key={z.name} className="pf-potion">
              <StatRow icon={<FlaskConical size={16} color="#7fffb0" />} label={`${z.name} ${z.tier}`} value={countdown(z.left_seconds)} />
              <div className="muted pf-potion-effect">{z.effect}</div>
            </div>
          ))}
        </Panel>
      )}
    </div>
  );
}
