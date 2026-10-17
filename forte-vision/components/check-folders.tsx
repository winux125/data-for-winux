"use client"

import { useI18n } from "@/components/locale-provider"
import { productMessages } from "@/lib/messages/product"
import { VERDICT_LABELS } from "@/lib/analysis"
import { CHECK_STATUS_LABELS } from "@/lib/checks"

import { useMemo, useState } from "react"
import type { CheckRecord } from "@/components/ui/demo"
import GlassFolder, { type GlassFolderFile } from "@/components/ui/glass-folder"
import "./check-folders.css"

interface CheckFoldersProps {
  records: CheckRecord[]
  onOpen: (id: string) => void
}

type GroupId = "attention" | "clear" | "demo"

const GROUPS: {
  id: GroupId
  title: string
  description: string
  emptyMessage: string
  variant: "burgundy" | "rose" | "ivory"
}[] = [
  { id: "attention", title: VERDICT_LABELS.violation, description: "Реальные записи с событиями, которые стоит изучить.", emptyMessage: "Среди показанных записей нет реальных проверок с найденными событиями.", variant: "burgundy" },
  { id: "clear", title: VERDICT_LABELS.no_violation, description: "Реальные записи, в которых сервис не обнаружил событий.", emptyMessage: "Среди показанных записей пока нет реальных проверок без замечаний.", variant: "ivory" },
  { id: "demo", title: "Демонстрация", description: "Условные примеры интерфейса. Модель на них не запускалась.", emptyMessage: "Демонстрационных примеров среди показанных записей нет.", variant: "rose" },
]

const STATUS_LABELS = CHECK_STATUS_LABELS

/** A second view of the same records, never a separate editable data store. */
export default function CheckFolders({ records, onOpen }: CheckFoldersProps) {
  const { t } = useI18n(productMessages)
  const [expanded, setExpanded] = useState<GroupId | null>(null)
  const grouped = useMemo(() => {
    const groups: Record<GroupId, GlassFolderFile[]> = { attention: [], clear: [], demo: [] }
    const other: CheckRecord[] = []
    for (const record of records) {
      const group: GroupId | null = record.demo ? "demo" : record.status === "violation" ? "attention" : record.status === "no_violation" ? "clear" : null
      if (group) groups[group].push({ id: record.id, name: record.name, meta: `${t(STATUS_LABELS[record.status])} · ${record.duration}` })
      else other.push(record)
    }
    return { groups, other }
  }, [records, t])

  return <div className="cf-root">
    <div className="cf-folder-grid" aria-label={t("Проверки по папкам")}>
      {GROUPS.map(group => <GlassFolder
        key={group.id}
        title={t(group.title)}
        description={t(group.description)}
        emptyMessage={t(group.emptyMessage)}
        variant={group.variant}
        files={grouped.groups[group.id]}
        open={expanded === group.id}
        onOpenChange={open => setExpanded(open ? group.id : null)}
        onFileSelect={file => onOpen(file.id)}
      />)}
    </div>
    {grouped.other.length > 0 && <section className="cf-other-checks" aria-label={t("Незавершённые проверки")}>
      <h3>{t("Другие состояния")}</h3>
      <p>{t("Эти записи ещё не имеют итогового результата.")}</p>
      <ul>{grouped.other.map(record => <li key={record.id}><button type="button" onClick={() => onOpen(record.id)}><span>{record.name}</span><small>{t(STATUS_LABELS[record.status])}</small></button></li>)}</ul>
    </section>}
    <p className="cf-view-note">{t("Откройте папку, чтобы увидеть все её записи. Список меняется вместе с поиском и фильтром.")}</p>
  </div>
}
