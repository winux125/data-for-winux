"use client"

import { useI18n } from "@/components/locale-provider"
import { productMessages } from "@/lib/messages/product"
import { CHECK_STATUS_LABELS, isRunningCheck, type CheckRecord } from "@/lib/checks"
export type { CheckRecord } from "@/lib/checks"

import type { Selection, SortDescriptor } from "@heroui/react"
import { Button, Checkbox, Chip, I18nProvider } from "@heroui/react"
import { ArrowLeftRight, Check, Copy, Eye, FileVideo, Inbox, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { Table } from "@/components/ui/heroui-table"
import "./table.css"

interface ChecksTableProps {
  records: CheckRecord[]
  onOpen: (id: string) => void
  onDelete: (id: string) => void
  selectedIds?: string[]
  onSelectionChange?: (ids: string[]) => void
}

const statusLabels = CHECK_STATUS_LABELS

const statusColors: Record<CheckRecord["status"], "success" | "danger" | "warning"> = {
  violation: "warning",
  no_violation: "success",
  failed: "danger",
  processing: "warning",
  uploading: "warning",
  reconnecting: "warning",
  paused: "warning",
}

function formatDate(value: string, localeTag: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(localeTag, {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date)
}

/** The supplied compound HeroUI table, adapted to the video review workflow. */
export function ChecksTable({ records, onOpen, onDelete, selectedIds, onSelectionChange }: ChecksTableProps) {
  const { t, localeTag } = useI18n(productMessages)
  const [internalSelectedIds, setInternalSelectedIds] = useState<string[]>([])
  const visibleIds = useMemo(() => new Set(records.map((record) => record.id)), [records])
  const selectedKeys = useMemo(() => new Set(
    (selectedIds ?? internalSelectedIds).filter((id) => visibleIds.has(id)),
  ), [selectedIds, internalSelectedIds, visibleIds])
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [copyError, setCopyError] = useState(false)
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: "createdAt",
    direction: "descending",
  })

  const sortedRecords = useMemo(() => {
    return [...records].sort((a, b) => {
      let comparison: number
      if (sortDescriptor.column === "events") comparison = a.events - b.events
      else if (sortDescriptor.column === "createdAt") {
        if (Boolean(a.demo) !== Boolean(b.demo)) return a.demo ? 1 : -1
        const first = new Date(a.createdAt).getTime()
        const second = new Date(b.createdAt).getTime()
        if (Number.isFinite(first) !== Number.isFinite(second)) return Number.isFinite(first) ? -1 : 1
        comparison = Number.isFinite(first) && Number.isFinite(second)
          ? first - second
          : 0
      } else comparison = a.name.localeCompare(b.name, localeTag, { numeric: true })
      return sortDescriptor.direction === "descending" ? -comparison : comparison
    })
  }, [records, sortDescriptor, localeTag])

  function updateSelection(keys: Selection) {
    const nextIds = keys === "all"
      ? Array.from(visibleIds)
      : Array.from(keys, String).filter((id) => visibleIds.has(id))
    setInternalSelectedIds(nextIds)
    onSelectionChange?.(nextIds)
  }

  async function copyId(id: string) {
    try {
      await navigator.clipboard.writeText(id)
      setCopyError(false)
      setCopiedId(id)
      window.setTimeout(() => setCopiedId((current) => current === id ? null : current), 2200)
    } catch {
      setCopyError(true)
      window.setTimeout(() => setCopyError(false), 3000)
    }
  }

  function toggleRecord(id: string, isSelected: boolean) {
    const nextKeys = new Set(selectedKeys)
    if (isSelected) nextKeys.add(id)
    else nextKeys.delete(id)
    updateSelection(nextKeys)
  }

  function renderStatus(record: CheckRecord) {
    return (
      <Chip color={statusColors[record.status]} size="sm" variant="soft" className={`check-status check-status--${record.status}`}>
        <span className="check-status-dot" aria-hidden="true" />{t(statusLabels[record.status])}
      </Chip>
    )
  }

  function renderActions(record: CheckRecord) {
    return (
      <div className="table-actions">
        <Button isIconOnly size="sm" variant="ghost" aria-label={`${t("Открыть проверку")} ${record.name}`} onPress={() => onOpen(record.id)} className="table-action"><Eye size={16} /></Button>
        <Button isIconOnly size="sm" variant="ghost" aria-label={copiedId === (record.jobId || record.id) ? t("Номер проверки скопирован") : `${t("Скопировать номер проверки")} ${record.name}`} onPress={() => void copyId(record.jobId || record.id)} className={`table-action ${copiedId === (record.jobId || record.id) ? "is-copied" : ""}`}>
          {copiedId === (record.jobId || record.id) ? <Check size={16} /> : <Copy size={15} />}
        </Button>
        <Button isIconOnly size="sm" variant="ghost" aria-label={`${t("Удалить проверку")} ${record.name}`} isDisabled={isRunningCheck(record)} onPress={() => onDelete(record.id)} className="table-action table-action-delete"><Trash2 size={15} /></Button>
      </div>
    )
  }

  function renderFile(record: CheckRecord) {
    return (
      <div className="record-file">
        <span className="record-file-icon" aria-hidden="true"><FileVideo size={18} strokeWidth={1.6} /></span>
        <div className="record-file-text">
          <button type="button" className="record-file-name" onClick={() => onOpen(record.id)} title={record.name}>{record.name}</button>
          <span className="record-file-id">{record.demo ? t("Демонстрационный пример") : `№ ${record.jobId || record.id}`}</span>
        </div>
      </div>
    )
  }

  function eventCount(record: CheckRecord) {
    return record.status !== "violation" && record.status !== "no_violation" ? "-" : record.events
  }

  if (records.length === 0) {
    return (
      <div className="checks-table-empty">
        <span className="checks-table-empty-icon"><Inbox size={24} strokeWidth={1.5} /></span>
        <strong>{t("Проверки не найдены")}</strong>
        <p>{t("Загрузите видео или измените параметры поиска.")}</p>
      </div>
    )
  }

  return (
    <I18nProvider locale={localeTag}><div className="checks-table">
      <div className="checks-table-announcement" aria-live="polite" role="status">
        {copiedId ? t("Номер проверки скопирован") : copyError ? t("Не удалось скопировать номер проверки") : ""}
      </div>
      <div className="checks-table-desktop">
        <Table variant="secondary">
          <Table.ScrollContainer tabIndex={0} aria-label={t("Таблица проверок: при необходимости прокрутите по горизонтали")}>
            <Table.Content
              aria-label={t("История проверок видео")}
              className="checks-table-content"
              selectionMode="multiple"
              selectedKeys={selectedKeys}
              sortDescriptor={sortDescriptor}
              onSelectionChange={updateSelection}
              onSortChange={setSortDescriptor}
            >
              <Table.Header>
                <Table.Column className="checks-table-select">
                  <Checkbox aria-label={t("Выбрать все видимые проверки")} slot="selection">
                    <Checkbox.Content><Checkbox.Control><Checkbox.Indicator /></Checkbox.Control></Checkbox.Content>
                  </Checkbox>
                </Table.Column>
                <Table.Column id="name" allowsSorting isRowHeader>
                  {({ sortDirection }) => <Table.SortableColumnHeader sortDirection={sortDirection}>{t("Видеозапись")}</Table.SortableColumnHeader>}
                </Table.Column>
                <Table.Column id="createdAt" allowsSorting>
                  {({ sortDirection }) => <Table.SortableColumnHeader sortDirection={sortDirection}>{t("Дата")}</Table.SortableColumnHeader>}
                </Table.Column>
                <Table.Column id="duration">{t("Длительность")}</Table.Column>
                <Table.Column id="status">{t("Результат")}</Table.Column>
                <Table.Column id="events" allowsSorting>
                  {({ sortDirection }) => <Table.SortableColumnHeader sortDirection={sortDirection}>{t("События")}</Table.SortableColumnHeader>}
                </Table.Column>
                <Table.Column id="actions" className="checks-table-actions-heading">{t("Действия")}</Table.Column>
              </Table.Header>
              <Table.Body>
                {sortedRecords.map((record) => (
                  <Table.Row key={record.id} id={record.id} textValue={record.name}>
                    <Table.Cell className="checks-table-select">
                      <Checkbox aria-label={`${t("Выбрать")} ${record.name}`} slot="selection" variant="secondary">
                        <Checkbox.Content><Checkbox.Control><Checkbox.Indicator /></Checkbox.Control></Checkbox.Content>
                      </Checkbox>
                    </Table.Cell>
                    <Table.Cell>{renderFile(record)}</Table.Cell>
                    <Table.Cell className="record-date">{formatDate(record.createdAt, localeTag)}</Table.Cell>
                    <Table.Cell className="record-duration">{record.duration}</Table.Cell>
                    <Table.Cell>{renderStatus(record)}</Table.Cell>
                    <Table.Cell><span className={`record-event-count ${record.events > 0 ? "has-events" : ""}`}>{eventCount(record)}</span></Table.Cell>
                    <Table.Cell>{renderActions(record)}</Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Content>
          </Table.ScrollContainer>
        </Table>
        <p className="checks-table-scroll-hint"><ArrowLeftRight size={14} aria-hidden="true" />{t("Таблицу можно прокрутить по горизонтали")}</p>
      </div>
      <div className="checks-table-mobile">
        <div className="checks-mobile-toolbar">
          <label className="checks-mobile-select-all">
            <input
              type="checkbox"
              checked={selectedKeys.size === records.length}
              ref={(element) => { if (element) element.indeterminate = selectedKeys.size > 0 && selectedKeys.size < records.length }}
              onChange={(event) => updateSelection(event.target.checked ? "all" : new Set())}
            />
            <span>{t("Выбрать все")}</span>
          </label>
          <label className="checks-mobile-sort">
            <span className="checks-table-announcement">{t("Порядок проверок")}</span>
            <select
              value={`${sortDescriptor.column}:${sortDescriptor.direction}`}
              onChange={(event) => {
                const [column, direction] = event.target.value.split(":")
                setSortDescriptor({ column, direction: direction as SortDescriptor["direction"] })
              }}
            >
              <option value="createdAt:descending">{t("Сначала новые")}</option>
              <option value="createdAt:ascending">{t("Сначала старые")}</option>
              <option value="name:ascending">{t("По названию: А–Я")}</option>
              <option value="name:descending">{t("По названию: Я–А")}</option>
              <option value="events:descending">{t("Больше событий")}</option>
              <option value="events:ascending">{t("Меньше событий")}</option>
            </select>
          </label>
        </div>
        <ul className="checks-mobile-list" aria-label={t("История проверок видео")}>
          {sortedRecords.map((record) => (
            <li key={record.id} className={`checks-mobile-card ${selectedKeys.has(record.id) ? "is-selected" : ""}`}>
              <div className="checks-mobile-card-heading">
                <label className="checks-mobile-checkbox">
                  <input type="checkbox" aria-label={`${t("Выбрать")} ${record.name}`} checked={selectedKeys.has(record.id)} onChange={(event) => toggleRecord(record.id, event.target.checked)} />
                </label>
                {renderFile(record)}
              </div>
              <dl className="checks-mobile-metadata">
                <div><dt>{t("Дата")}</dt><dd>{formatDate(record.createdAt, localeTag)}</dd></div>
                <div><dt>{t("Длительность")}</dt><dd>{record.duration}</dd></div>
                <div><dt>{t("События")}</dt><dd>{eventCount(record)}</dd></div>
              </dl>
              <div className="checks-mobile-card-footer">{renderStatus(record)}{renderActions(record)}</div>
            </li>
          ))}
        </ul>
      </div>
    </div></I18nProvider>
  )
}

export default ChecksTable
