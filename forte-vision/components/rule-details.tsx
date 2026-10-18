"use client";

import { ArrowUpRight } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { workspaceMessages } from "@/lib/messages/workspace";
import type { Violation } from "@/lib/analysis";

export default function RuleDetails({ violation }: { violation: Violation }) {
  const { t } = useI18n(workspaceMessages);
  const rule = violation.rule;
  const safeUrl = rule?.url && /^https?:\/\//i.test(rule.url) ? rule.url : null;
  return rule?.title ? <div className="fv-rule-details">
    <span className="fv-source-label">{t("НОРМАТИВНЫЙ ИСТОЧНИК")}</span><strong>{rule.title}</strong>
    {rule.section && <p>{rule.section}</p>}
    {rule.path?.length ? <p>{rule.path.join(" → ")}</p> : null}
    {rule.source_relation === "context_only" && <p>{t("Общий контекст: конкретный пункт не выбран.")}</p>}
    {rule.quote ? <div className="fv-rule-quotation"><span className="fv-source-label">{t("Цитата из источника")}</span><blockquote>{rule.quote}</blockquote></div>
      : <p>{t("Цитата не передана в этом результате.")}</p>}
    {rule.context?.length ? <details className="fv-rule-context"><summary>{t("Связанные положения и исключения")}</summary>
      {rule.context.map((item, index) => <div className="fv-rule-quotation" key={`${item.title}-${item.section || index}`}>
        <strong>{item.title}</strong>{item.section && <p>{item.section}</p>}
        {item.path?.length ? <p>{item.path.join(" → ")}</p> : null}
        {item.quote && <blockquote>{item.quote}</blockquote>}
        {item.url && /^https?:\/\//i.test(item.url) && <a href={item.url} target="_blank" rel="noopener noreferrer">{t("Открыть источник")} <ArrowUpRight size={15}/></a>}
      </div>)}
    </details> : null}
    {safeUrl && <a href={safeUrl} target="_blank" rel="noopener noreferrer">{t("Открыть источник")} <ArrowUpRight size={15}/></a>}
  </div> : <div className="fv-rule-details"><span className="fv-source-label">{t("ИСТОЧНИК НЕ УКАЗАН")}</span><strong>{t("Источник не передан")}</strong><p>{t("В результате нет документа и раздела правила. Проверьте основание перед подтверждением события.")}</p></div>;
}
