"use strict";
(() => {
  const R = window.Radar, $ = selector=>document.querySelector(selector);
  function payload() {
    const file = $("#target-file").files[0];
    if (file) { const body = new FormData(); body.append("file",file); return {method:"POST",body}; }
    return R.json({text:$("#targets").value});
  }
  async function preview() {
    const data = await R.api("/api/targets/parse",payload());
    $("#preview-panel").hidden=false; $("#preview-count").textContent=`Распознано целей: ${data.targets.length}`;
    $("#parse-errors").replaceChildren(...data.errors.map(e=>R.el("li",`Строка ${e.line}: ${e.error}`)));
    $("#preview-rows").replaceChildren(...data.targets.map(target=>{const tr=R.el("tr"); for(const value of [target.host,target.port,target.sni || "—",target.owner || "—",R.criticalities[target.criticality] || "Обычная"]) tr.append(R.el("td",value)); return tr;}));
    return data.errors.length === 0 && data.targets.length > 0;
  }
  async function poll(id) {
    $("#progress-panel").hidden=false; $("#start-scan").disabled=true; $("#start-scan").dataset.busy="true";
    try {
      const data = await R.api(`/api/scans/${id}`);
      $("#scan-progress").max=data.total; $("#scan-progress").value=data.done;
      $("#progress-text").textContent=`Обработано ${data.done} из ${data.total}`;
      if(data.status === "done") { location.href="/"; return; }
      if(data.status === "failed") throw new Error("Сканирование завершилось с ошибкой. Подробности в журнале.");
      setTimeout(()=>poll(id),1000);
    } catch(error) { R.message(error.message,true); delete $("#start-scan").dataset.busy; $("#start-scan").disabled=false; }
  }
  R.action("#demo",async()=>{const data=await R.api("/api/demo-targets"); $("#targets").value=data.text; $("#target-file").value=""; await preview();});
  R.action("#preview",preview);
  R.action("#start-scan",async()=>{if(!await preview()) {R.message("Исправьте ошибки или добавьте цели.",true);return;} const result=await R.api("/api/scans",payload()); history.replaceState(null,"",`/scan?scan_id=${result.scan_id}`); await poll(result.scan_id);});
  $("#targets").addEventListener("input",()=>$("#target-file").value="");
  const scanId=new URLSearchParams(location.search).get("scan_id"); if(scanId) poll(Number(scanId));
})();
