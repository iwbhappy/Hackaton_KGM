"use strict";
(() => {
  const R=window.Radar, $=selector=>document.querySelector(selector), id=$("#details").dataset.endpointId;
  let latest;
  function render(data) {
    const ep=data.endpoint; latest=data.latest;
    $("#service-title").textContent=ep.service_name || ep.host;
    $("#service-address").textContent=`${ep.host}:${ep.port}`;
    $("#service-name").value=ep.service_name || ""; $("#owner").value=ep.owner || ""; $("#criticality").value=ep.criticality;
    if(!latest) { R.message("Сервис ещё не сканировался."); return; }
    $("#detail-status").replaceChildren(R.status(latest.status)); $("#risk-value").replaceChildren(R.risk(latest));
    $("#risk-reasons").replaceChildren(...latest.reasons.map(reason=>R.el("li",reason.text)));
    $("#ip-hint").hidden=!(ep.host.includes(":") || /^\d+(\.\d+){3}$/.test(ep.host));
    $("#copy-thumbprint").disabled=!latest.thumbprint_sha1;
    const attrs=[["Сервис / порт",`${ep.host}:${ep.port}`],["IP-адрес",latest.resolved_ip],["CN",latest.subject_cn],
      ["SAN DNS",latest.san_dns.join("\n")],["SAN IP",latest.san_ip.join("\n")],["Издатель CN",latest.issuer_cn],["Организация издателя",latest.issuer_o],
      ["Серийный номер",latest.serial],["Thumbprint SHA-1",latest.thumbprint_sha1],["Fingerprint SHA-256",latest.fingerprint_sha256],
      ["Действует с (UTC)",latest.not_before],["Действует до (UTC)",latest.not_after],["Осталось дней",latest.days_left],["Версия TLS",latest.tls_version],
      ["Ключ",[latest.key_type,latest.key_size].filter(Boolean).join(" ")],["Подпись",latest.signature_algorithm],
      ["Цепочка",R.chains[latest.chain_status]],["Проверка доверия / OpenSSL",latest.chain_message],
      ["Проверка имени",{match:"Совпадает",mismatch:"Не совпадает",not_checked:"Не проверено"}[latest.hostname_match]],["Ошибка подключения",latest.error]];
    $("#attributes").replaceChildren(...attrs.flatMap(([label,value])=>[R.el("dt",label),R.el("dd",value ?? "—")]));
    $("#issues-rows").replaceChildren(...latest.issues.map(issue=>{const tr=R.el("tr"); [issue.title,issue.detail,issue.recommendation,issue.points ? `+${issue.points}` : "—"].forEach(value=>tr.append(R.el("td",value)));return tr;}));
    $("#no-issues").hidden=!!latest.issues.length;
    $("#history-rows").replaceChildren(...data.history.map(row=>{const tr=R.el("tr");tr.append(R.el("td",R.datetime(row.scanned_at)),R.el("td",row.thumbprint_sha1 || "—"),R.el("td",row.days_left ?? "—"));const status=R.el("td"),risk=R.el("td");status.append(R.status(row.status));risk.append(R.risk(row));tr.append(status,risk);return tr;}));
  }
  $("#owner-form").addEventListener("submit",async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;
    try { const options=R.json({service_name:$("#service-name").value,owner:$("#owner").value,criticality:$("#criticality").value});options.method="PATCH";render(await R.api(`/api/endpoints/${id}`,options));R.message("Изменения сохранены. Риск пересчитан без сканирования."); }
    catch(error){R.message(error.message,true);}finally{button.disabled=false;}
  });
  R.action("#copy-thumbprint",async()=>{await navigator.clipboard.writeText(latest.thumbprint_sha1);R.message("Thumbprint скопирован.");});
  R.api(`/api/endpoints/${id}`).then(render).catch(error=>R.message(error.message,true));
})();
