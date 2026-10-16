import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

/** Нижняя шторка (bottom sheet): затемнение + панель; закрывается тапом по фону, крестиком и Esc. */
export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="sheet-back" onClick={onClose} role="presentation">
      <div className="sheet" role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-head">
          <div className="sheet-title">{title}</div>
          <button className="sheet-x" type="button" onClick={onClose} aria-label="Закрыть">
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
