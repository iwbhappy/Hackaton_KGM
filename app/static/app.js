"use strict";
window.Radar = (() => {
  const labels = {OK:"OK",INFO:"Информация",WARNING:"Предупреждение",CRITICAL:"Критический",EXPIRED:"Истёк",ERROR:"Недоступно"};
  const colors = {OK:"#36a277",INFO:"#598cdd",WARNING:"#e7b34b",CRITICAL:"#e28a48",EXPIRED:"#c84c5e",ERROR:"#a2adbb"};
  const criticalities = {low:"Низкая",normal:"Обычная",high:"Высокая",critical:"Критичная"};
  const chains = {valid:"Доверена",valid_but_expired:"Истёк",self_signed:"Самоподписанный",untrusted_root:"Недоверенный CA",incomplete_or_untrusted:"Неполная / недоверенная",not_yet_valid:"Ещё не действует",error:"Ошибка",not_checked:"Не проверена"};
  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }
  function message(text, error = false) {
    const box = document.querySelector("#message");
    box.textContent = text; box.hidden = !text; box.classList.toggle("error", error);
  }
  async function api(path, options = {}) {
    let response;
    try { response = await fetch(path, options); }
    catch { throw new Error("Нет связи с сервером. Проверьте, что приложение запущено."); }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      throw new Error(typeof detail === "string" ? detail : detail?.message || "Не удалось выполнить запрос");
    }
    return data;
  }
  const json = data => ({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
  const date = value => value ? new Date(value).toLocaleDateString("ru-RU", {timeZone:"UTC"}) : "—";
  const datetime = value => value ? new Date(value).toLocaleString("ru-RU") : "—";
  const status = value => el("span",labels[value] || value,"badge status-" + value);
  const risk = row => el("span",row.risk_score === null ? "—" : `${row.risk_score} / ${row.risk_level}`,"badge risk-" + (row.risk_level || "none"));
  const issuer = row => row.issuer_o || row.issuer_cn || "—";
  function action(selector, callback) {
    document.querySelector(selector)?.addEventListener("click", async event => {
      const button = event.currentTarget; button.disabled = true; message("");
      try { await callback(event); } catch (error) { message(error.message, true); }
      finally { if (!button.dataset.busy) button.disabled = false; }
    });
  }
  document.querySelectorAll("nav a").forEach(link => {
    if (link.getAttribute("href") === location.pathname) link.setAttribute("aria-current", "page");
  });
  return {labels,colors,criticalities,chains,el,message,api,json,date,datetime,status,risk,issuer,action};
})();
