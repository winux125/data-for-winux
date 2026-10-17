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
    {safeUrl && <a href={safeUrl} target="_blank" rel="noopener noreferrer">{t("Открыть источник")} <ArrowUpRight size={15}/></a>}
  </div> : <div className="fv-rule-details"><span className="fv-source-label">{t("ИСТОЧНИК НЕ УКАЗАН")}</span><strong>{t("Источник не передан")}</strong><p>{t("В результате нет документа и раздела правила. Проверьте основание перед подтверждением события.")}</p></div>;
}
