"use strict";

(() => {
  const R = window.Radar,
    select = document.querySelector("#action-filter");
  const labels = {
    app_started: "Запуск приложения",
    scan_started: "Сканирование начато",
    scan_finished: "Сканирование завершено",
    targets_uploaded: "Загружены цели",
    endpoint_updated: "Обновлён сервис",
    endpoint_deleted: "Удалён сервис",
    settings_changed: "Изменены настройки",
    export_downloaded: "Выгружен отчёт",
    notification_sent: "Уведомление отправлено",
    notification_failed: "Ошибка уведомления",
    trusted_ca_uploaded: "Добавлен доверенный CA",
    trusted_ca_deleted: "Удалён доверенный CA"
  };
  for (const [value, label] of Object.entries(labels)) {
    const option = R.el("option", label);
    option.value = value;
    select.append(option);
  }
  async function load() {
    const rows = await R.api("/api/audit" + (select.value ? `?action=${encodeURIComponent(select.value)}` : ""));
    document.querySelector("#audit-rows").replaceChildren(...rows.map(row => {
      const tr = R.el("tr");
      [R.datetime(row.ts), row.actor, labels[row.action] || row.action,
        JSON.stringify(row.details)].forEach(value => tr.append(R.el("td", value)));
      return tr;
    }));
  }
  select.addEventListener("change", () => load().catch(error => R.message(error.message, true)));
  R.action("#refresh-audit", load);
  load().catch(error => R.message(error.message, true));
})();
