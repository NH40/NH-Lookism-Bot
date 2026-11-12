import { Check, ShoppingBag } from "lucide-react";
import { Panel, countdown } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";

type SaleData = {
  active: {
    kind: string;
    title: string;
    about: string;
    left_seconds: number;
    chosen: boolean;
    choices: string[];
    special: boolean;
    price: number | null;
    bought: boolean;
  } | null;
  categories: { code: string; name: string }[];
};

/** Текущая «пятница» на странице доната: что даёт, выбор «избранных», разовая покупка. */
export function SalePanel({ onChanged }: { onChanged?: () => void }) {
  const { data, reload } = useApi<SaleData>("/sale");
  const { run, busy } = useAction(async () => {
    await reload();
    onChanged?.();
  });
  const s = data?.active;
  if (!s) return null;
  return (
    <Panel title={s.title.toUpperCase()} tone="gold" badgeMark="%">
      <p className="emp-note" style={{ margin: "0 0 8px" }}>{s.about} Осталось: {countdown(s.left_seconds)}.</p>
      {s.chosen && (
        <div className="grid-2" style={{ gap: 6 }}>
          {data!.categories.map((c) => (
            <button key={c.code} type="button" className={`btn small ${s.choices.includes(c.code) ? "gold" : "ghost"}`} disabled={busy}
              onClick={() => run("/sale/pick", { category: c.code })}>
              {s.choices.includes(c.code) && <Check size={12} />}{c.name}
            </button>
          ))}
        </div>
      )}
      {s.special && (s.bought ? (
        <p className="emp-note" style={{ margin: 0 }}>Ты уже воспользовался этой пятницей.</p>
      ) : (
        <button type="button" className="btn block gold" disabled={busy} onClick={() => run("/sale/buy", {})}>
          <ShoppingBag size={16} />Купить — {s.price} 💎
        </button>
      ))}
    </Panel>
  );
}

type AdminSale = { active: { kind: string; title: string; left_seconds: number } | null; kinds: { code: string; title: string; about: string }[] };

/** Админка: запустить одну пятницу на 24 ч или выключить текущую. */
export function SaleAdminSection() {
  const { data, reload } = useApi<AdminSale>("/admin/sale");
  const { run, busy } = useAction(reload);
  if (!data) return null;
  return (
    <Panel title="Пятницы">
      {data.active ? (
        <>
          <p className="adm-hint">Идёт: <b>{data.active.title}</b>, ещё {countdown(data.active.left_seconds)}.</p>
          <button type="button" className="btn block red" disabled={busy} onClick={() => run("/admin/sale/stop", {})}>Выключить</button>
        </>
      ) : (
        <>
          <p className="adm-hint">Одна за раз, сама заканчивается через 24 ч. Игрокам приходит уведомление.</p>
          <div className="adm-list">
            {data.kinds.map((k) => (
              <button key={k.code} type="button" className="adm-item" disabled={busy} onClick={() => run("/admin/sale/start", { kind: k.code })}>
                <div><b>{k.title}</b><small>{k.about}</small></div>
              </button>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
