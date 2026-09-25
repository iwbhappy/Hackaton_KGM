"use strict";

(() => {
  const R = window.Radar,
    form = document.querySelector("#settings-form");
  function render(config) {
    for (const input of form.querySelectorAll("input")) input.value = Array.isArray(config[input.name]) ?
      config[input.name].join(",") : config[input.name];
  }
  async function loadCA() {
    const rows = await R.api("/api/trusted-ca"),
      body = document.querySelector("#ca-rows");
    body.replaceChildren();
    document.querySelector("#no-ca").hidden = !!rows.length;
    for (const row of rows) {
      const tr = R.el("tr"),
        action = R.el("td"),
        button = R.el("button", "Удалить");
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await R.api(`/api/trusted-ca/${encodeURIComponent(row.name)}`, {
            method: "DELETE"
          });
          await loadCA();
          R.message("CA удалён. Пересканируйте сервисы для проверки доверия.");
        } catch (error) {
          R.message(error.message, true);
          button.disabled = false;
        }
      });
      action.append(button);
      tr.append(R.el("td", row.cn), R.el("td", R.date(row.not_after)), R.el("td", row.name), action);
      body.append(tr);
    }
  }
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    try {
      const values = {};
      for (const input of form.querySelectorAll("input"))
        values[input.name] = input.name === 'notification_thresholds'
          ? input.value.split(",").map(v => Number(v.trim()))
          : Number(input.value);
      const options = R.json(values);
      options.method = "PUT";
      render(await R.api("/api/settings", options));
      R.message("Настройки сохранены. Статусы и риск пересчитаны.");
    } catch (error) {
      R.message(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  document.querySelector("#ca-form").addEventListener("submit", async event => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    try {
      const body = new FormData();
      body.append("file", document.querySelector("#ca-file").files[0]);
      await R.api("/api/trusted-ca", {
        method: "POST",
        body
      });
      await loadCA();
      R.message("CA загружен. Пересканируйте сервисы для проверки доверия.");
    } catch (error) {
      R.message(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  Promise.all([R.api("/api/settings").then(render), loadCA()]).catch(error => R.message(error.message, true));
})();
