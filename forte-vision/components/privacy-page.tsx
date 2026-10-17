"use client";

/* eslint-disable @next/next/no-html-link-for-pages -- Keep product navigation as native document links. */
import { ArrowLeft, ArrowRight, ArrowUpRight, DoorOpen, Cookie, FileVideo, FlaskConical, Server } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { accountMessages } from "@/lib/messages/account";
import { AppearanceControls } from "@/components/theme-provider";
import "./privacy-page.css";

const sections = [
  { id: "access", number: "01", Icon: DoorOpen, title: "Доступ без регистрации", paragraphs: ["Forte Vision открывается по ссылке без аккаунта и пароля. Приложение не запрашивает имя или электронную почту.", "Проверки остаются в текущей вкладке. Другие посетители сайта не видят выбранные вами файлы или результаты."] },
  { id: "cookies", number: "02", Icon: Cookie, title: "Cookie и настройки браузера", paragraphs: ["В приложении нет сессии входа. Данные аккаунта не запрашиваются.", "Выбранная тема сохраняется в localStorage браузера. Язык интерфейса сохраняется в cookie forte-locale на этом сайте."] },
  { id: "video", number: "03", Icon: FileVideo, title: "Видео и результаты", paragraphs: ["Выбор файла открывает локальный предпросмотр в текущей вкладке. Проверки и результаты хранятся в памяти страницы до перезагрузки.", "Для продолжения проверки после перезагрузки sessionStorage сохраняет временный токен этой вкладки, номер задания и сведения о файле. Видео, кадры и ключ жюри туда не записываются.", "Удаление проверки убирает её из текущего интерфейса. Это действие не отправляет запрос на удаление видео или результата с сервера анализа.", "Отменить удаление можно в течение 10 секунд. До окончания этого срока результат и исходное видео остаются в памяти вкладки."] },
  { id: "api", number: "04", Icon: Server, title: "Подключённый сервер анализа", paragraphs: ["После запуска проверки видео отправляется напрямую на сервер команды. Подключение выполняется автоматически; ключ жюри в браузер не передаётся.", "Исходное видео удаляется после обработки или ошибки. Результат, кадры и закрытый технический журнал анализа хранятся до 24 часов. Отмена ожидания не останавливает задание."] },
  { id: "demo", number: "05", Icon: FlaskConical, title: "Демонстрация и аналитика", paragraphs: ["Готовые примеры проверок, этапы, события и таймкоды в демоверсии - условные данные. Они показывают интерфейс и не являются результатом анализа вашей записи.", "В приложении нет рекламных трекеров и маркетинговой аналитики. При техническом сбое отправляется ограниченный отчёт об ошибке: без содержимого форм, видео, cookie и параметров адреса. Хостинг и подключённый сервер анализа обрабатывают запросы по своим правилам."] },
];

export default function PrivacyPage() {
  const { t } = useI18n(accountMessages);
  return <div className="fp-page">
    <a className="fp-skip" href="#fp-content">{t("Перейти к содержимому")}</a>
    <header className="fp-header fp-container">
      <a className="fp-brand" href="/" aria-label={t("Forte Vision - на главную")}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="fp-wordmark-light" src="/brand/forte-wordmark-burgundy.svg" width="91" height="27" alt="Forte" />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="fp-wordmark-dark" src="/brand/forte-wordmark-white.svg" width="91" height="27" alt="Forte" />
        <span>Vision</span>
      </a>
      <a className="fp-header-link" href="/app" target="_top">{t("Открыть сервис")}<ArrowUpRight size={15} aria-hidden="true" /></a>
    </header>

    <main className="fp-main fp-container" id="fp-content">
      <a className="fp-back" href="/"><ArrowLeft size={15} aria-hidden="true" />{t("На главную")}</a>
      <div className="fp-intro"><p className="fp-eyebrow"><span /> {t("О ПРОТОТИПЕ")}</p><h1>{t("Данные и cookie")}</h1><p>{t("Как сохраняются настройки, работает предпросмотр видео и когда запись передаётся на сервер анализа.")}</p></div>
      <div className="fp-content-layout">
        <nav className="fp-nav" aria-label={t("Разделы страницы")}>{sections.map((section) => <a href={`#${section.id}`} key={section.id}><span>{section.number}</span>{t(section.title)}</a>)}</nav>
        <div className="fp-sections">{sections.map(({ id, number, Icon, title, paragraphs }) => <section className="fp-section" key={id} id={id} aria-labelledby={`fp-${id}-title`}><div className="fp-section-top"><span className="fp-section-icon"><Icon size={19} strokeWidth={1.5} aria-hidden="true" /></span><span className="fp-section-number">{number}</span></div><h2 id={`fp-${id}-title`}>{t(title)}</h2>{paragraphs.map((text) => <p key={text}>{t(text)}</p>)}</section>)}</div>
      </div>
      <div className="fp-bottom-actions"><a className="fp-primary" href="/">{t("Вернуться к продукту")}<ArrowRight size={16} aria-hidden="true" /></a><a className="fp-demo-link" href="/demo" target="_top">{t("Открыть демоверсию")}<ArrowUpRight size={14} aria-hidden="true" /></a></div>
    </main>

    <footer className="fp-footer fp-container"><AppearanceControls /><span>Forte Vision · Datathon 2026</span><span>{t("Демонстрационный проект по кейсу ForteBank")}</span></footer>
  </div>;
}
