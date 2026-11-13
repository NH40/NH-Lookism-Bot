import { useState } from "react";
import type { GuideData } from "../../types";
import { BackHeader, Panel, Screen } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useApi } from "../../hooks/useApi";
import { imgUrl } from "../../api/api";
import "./Guide.css";

// Гайд — те же разделы и тексты, что /help в боте (HTML бота: <b>, <i>, переносы строк).
export function GuidePage() {
  const { data, status, error } = useApi<GuideData>("/guide");
  const [code, setCode] = useState<string | null>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const current = data?.sections.find((s) => s.code === code) ?? data?.sections[0];
  return (
    <Screen status={status} error={error}>
      {data && current && (
        <div className="page">
          <BackHeader title="Гайд по игре" subtitle="тот же текст, что /help" backLabel="Ещё" to={ROUTE_MORE} />
          <div className="guide-tabs">
            {data.sections.map((s) => (
              <button key={s.code} type="button" className={`pill ${s.code === current.code ? "on" : ""}`} onClick={() => setCode(s.code)}>
                {s.title}
              </button>
            ))}
          </div>
          <Panel title={current.title.toUpperCase()}>
            <div className="guide-body" dangerouslySetInnerHTML={{ __html: current.body.replace(/\n/g, "<br>") }} />
            {!!current.images?.length && (
              <div className="guide-sheets">
                {current.images.map((p) => (
                  <img key={p} src={imgUrl(p, 1280)} loading="lazy" alt="" onClick={() => setZoom(p)} />
                ))}
                <small className="muted">Нажми на картинку, чтобы открыть крупно.</small>
              </div>
            )}
          </Panel>
          {zoom && (
            <div className="guide-zoom" onClick={() => setZoom(null)}>
              <img src={imgUrl(zoom, 1280)} alt="" />
            </div>
          )}
        </div>
      )}
    </Screen>
  );
}
