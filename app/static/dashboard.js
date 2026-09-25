"use strict";

(() => {
  const R = window.Radar;
  let rows = [],
    sortKey = "risk_score",
    descending = true,
    issueFilter = "";
  const statuses = new Set();
  const $ = selector => document.querySelector(selector);
  function reset() {
    for (const id of ["search", "owner-filter", "issuer-filter", "days-min", "days-max"]) $("#" + id).value = "";
    $("#issues-only").checked = false;
    statuses.clear();
    issueFilter = "";
    document.querySelectorAll("#status-filters input").forEach(input => input.checked = false);
  }
  function selectStatus(value) {
    reset();
    statuses.add(value);
    $(`#status-filters input[value="${value}"]`).checked = true;
    renderTable();
    $("#results-table").scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
  }
  function drawSummary(summary) {
    for (const key of ["health", "services", "certificates"]) $("#" + key).textContent = summary[key] ?? "—";
    $("#health").style.color = summary.health < 50 ? R.colors.EXPIRED : summary.health < 80 ? R.colors.WARNING :
      R.colors.OK;
    $("#chain-count").textContent = summary.issues.CHAIN;
    $("#name-count").textContent = summary.issues.HOSTNAME_MISMATCH;
    $("#owner-count").textContent = summary.issues.NO_OWNER;
    for (const [code, label] of Object.entries(R.labels)) {
      const button = R.el("button", null, "status-card");
      button.style.setProperty("--status-color", R.colors[code]);
      button.append(R.el("strong", summary.statuses[code]), R.el("span", label));
      button.addEventListener("click", () => selectStatus(code));
      $("#status-cards").append(button);
      const check = R.el("input");
      check.type = "checkbox";
      check.value = code;
      check.addEventListener("change", () => {
        check.checked ? statuses.add(code) : statuses.delete(code);
        renderTable();
      });
      const option = R.el("label", null, "check");
      option.append(check, R.el("span", label));
      $("#status-filters").append(option);
    }
    for (const row of summary.top_risks) {
      const link = R.el("a", null, "risk-row");
      link.href = `/endpoint/${row.endpoint_id}`;
      link.append(R.el("strong", row.service_name), R.risk(row), R.el("span",
        row.reasons.map(r => r.text).join(" · "), "muted"));
      $("#top-risks").append(link);
    }
    if (!summary.top_risks.length) $("#top-risks").append(R.el("p", "Повышенных рисков не обнаружено.", "muted"));
    new Chart($("#status-chart"), {
      type: "doughnut",
      data: {
        labels: Object.values(R.labels),
        datasets: [{
          data: Object.values(summary.statuses),
          backgroundColor: Object.values(R.colors),
          borderWidth: 3,
          borderColor: "#fff"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "72%",
        plugins: {
          legend: {
            position: "right",
            labels: {
              boxWidth: 10,
              padding: 15,
              font: {
                size: 11
              }
            }
          }
        }
      }
    });
    new Chart($("#expiry-chart"), {
      type: "bar",
      data: {
        labels: summary.expiry_buckets.map(b => b.label),
        datasets: [{
          label: "Сервисов",
          data: summary.expiry_buckets.map(b => b.count),
          backgroundColor: ["#c84c5e", "#e28a48", "#e7b34b", "#598cdd", "#36a277"],
          borderRadius: 5,
          maxBarThickness: 45
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              precision: 0
            },
            grid: {
              color: "#edf1f6"
            }
          },
          x: {
            grid: {
              display: false
            }
          }
        }
      }
    });
  }
  function filtered() {
    const query = $("#search").value.toLowerCase(),
      owner = $("#owner-filter").value,
      issuer = $("#issuer-filter").value;
    const min = $("#days-min").value,
      max = $("#days-max").value;
    return rows.filter(row => {
      const haystack = [row.host, row.service_name, row.subject_cn, ...row.san_dns,
        ...row.san_ip].join(" ").toLowerCase();
      const codes = row.issues.map(i => i.code);
      return (!query || haystack.includes(query)) && (!owner || (row.owner || "__none__") === owner) && (!issuer ||
        R.issuer(row) === issuer) && (!statuses.size || statuses.has(row.status)) && (min === "" ||
        row.days_left !== null && row.days_left >= Number(min)) && (max === "" || row.days_left !== null &&
        row.days_left <= Number(max)) && (!$("#issues-only").checked || codes.length > 0) && (!issueFilter ||
        (issueFilter === "NO_OWNER" ? !row.owner : issueFilter === "CHAIN" ? codes.some(c => ["CHAIN_UNTRUSTED",
        "SELF_SIGNED"].includes(c)) : codes.includes(issueFilter)));
    });
  }
  function value(row) {
    if (sortKey === "issuer") return R.issuer(row);
    if (sortKey === "issues") return row.issues.length;
    if (sortKey === "criticality") return ["low", "normal", "high", "critical"].indexOf(row.criticality);
    if (sortKey === "status") return Object.keys(R.labels).indexOf(row.status);
    return row[sortKey];
  }
  function compare(a, b) {
    const av = value(a),
      bv = value(b);
    if (av == null || bv == null) return av == null ? bv == null ? 0 : 1 : -1;
    const diff = typeof av === "number" ? av - bv : String(av).localeCompare(String(bv), "ru");
    return (descending ? -diff : diff) || (a.days_left ?? Infinity) - (b.days_left ?? Infinity);
  }
  function renderTable() {
    const selected = filtered().sort(compare),
      body = $("#result-rows");
    body.replaceChildren();
    $("#filtered-count").textContent = `${selected.length} / ${rows.length}`;
    $("#no-matches").hidden = !!selected.length;
    $("#active-issue").textContent = issueFilter ? "Фильтр по выбранной проблеме" : "";
    for (const row of selected) {
      const tr = R.el("tr");
      tr.dataset.endpoint = row.endpoint_id;
      const service = R.el("td", null, "service-cell"),
        link = R.el("a", row.service_name);
      link.href = `/endpoint/${row.endpoint_id}`;
      service.append(link, R.el("small", `${row.host}:${row.port}`));
      tr.append(service);
      const cells = [
        row.owner || "Не назначен",
        R.criticalities[row.criticality],
        R.issuer(row),
        row.subject_cn || "—",
        R.date(row.not_after),
        row.days_left ?? "—",
        R.status(row.status),
        R.chains[row.chain_status] || row.chain_status,
        {match: "Совпадает", mismatch: "Не совпадает", not_checked: "—"}[row.hostname_match],
        R.risk(row),
        row.issues.length
      ];
      cells.forEach((content, index) => {
        const td = R.el("td");
        content instanceof Node ? td.append(content) : td.textContent = content;
        if (index === 10) td.title = row.issues.map(i => i.title).join("; ");
        tr.append(td);
      });
      tr.addEventListener("click", event => {
        if (!event.target.closest("a")) location.href = link.href;
      });
      body.append(tr);
    }
    document.querySelectorAll("[data-sort]").forEach(button => {
      const active = button.dataset.sort === sortKey;
      button.querySelector("span").textContent = active ? descending ? "↓" : "↑" : "↕";
      button.closest("th").setAttribute("aria-sort", active ? descending ? "descending" : "ascending" : "none");
    });
  }
  async function init() {
    const [data, summary] = await Promise.all([R.api("/api/results"), R.api("/api/summary")]);
    rows = data;
    $("#empty").hidden = !!rows.length;
    $("#dashboard").hidden = !rows.length;
    if (!rows.length) return;
    drawSummary(summary);
    for (const [id, values] of [["owner-filter", rows.map(r => r.owner || "__none__")], ["issuer-filter",
      rows.map(R.issuer)]]) {
      [...new Set(values)].sort().forEach(value => {
        const option = R.el("option", value === "__none__" ? "Без владельца" : value);
        option.value = value;
        $("#" + id).append(option);
      });
    }
    for (const id of ["search", "owner-filter", "issuer-filter", "days-min", "days-max",
      "issues-only"]) $("#" + id).addEventListener("input", renderTable);
    document.querySelectorAll("[data-sort]").forEach(button => button.addEventListener("click", () => {
      descending = sortKey === button.dataset.sort ? !descending : false;
      sortKey = button.dataset.sort;
      renderTable();
    }));
    document.querySelectorAll("[data-issue]").forEach(button => button.addEventListener("click", () => {
      reset();
      issueFilter = button.dataset.issue;
      renderTable();
    }));
    $("#all-services").addEventListener("click", () => {
      reset();
      renderTable();
    });
    $("#reset-filters").addEventListener("click", () => {
      reset();
      renderTable();
    });
    R.action("#rescan", async () => {
      const result = await R.api("/api/scans", R.json({
        rescan_all: true
      }));
      location.href = `/scan?scan_id=${result.scan_id}`;
    });
    renderTable();
  }
  init().catch(error => R.message(error.message, true));
})();
