"use strict";
(() => {
  const R=window.Radar;
  function outcome(data) {
    if(!data.configured) return "Каналы уведомлений не настроены. Укажите параметры в .env и перезапустите приложение.";
    return Object.entries(data.channels).map(([name,value])=>`${name}: ${value.error || (value.status === 'sent' ? 'сводка отправлена' : 'новых уведомлений нет')}`).join(" · ");
  }
  R.api("/api/notifications").then(data=>{
    const button=document.querySelector("#send-now");
    if(button && Object.values(data.channels).some(channel=>channel.configured)) {button.disabled=false;button.textContent="Отправить уведомления";button.title="Отправить сводку повторно";}
    if(data.failures.length) R.message("Последняя ошибка уведомлений: " + data.failures[0].details.error,true);
    const container=document.querySelector("#channels");
    if(container) for(const [name,channel] of Object.entries(data.channels)) {
      const card=R.el("div",null,"panel"),title=R.el("h3",{telegram:"Telegram",email:"Email",teams:"Teams"}[name]);
      const test=R.el("button","Тест");test.disabled=!channel.configured;
      test.addEventListener("click",async()=>{test.disabled=true;try{const result=await R.api(`/api/notifications/test/${name}`,R.json({}));R.message(result.error || "Тестовое уведомление отправлено.",!!result.error);}catch(error){R.message(error.message,true);}finally{test.disabled=false;}});
      card.append(title,R.el("p",channel.configured ? "Настроен" : "Не настроено"),R.el("p",channel.masked,"muted"),test);container.append(card);
    }
  }).catch(error=>R.message(error.message,true));
  R.action("#send-now",async()=>{const data=await R.api("/api/notifications/send-now",R.json({}));R.message(outcome(data),Object.values(data.channels).some(value=>value.status==='failed'));});
})();
