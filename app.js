const devicesEl = document.getElementById("devices");
const armToggle = document.getElementById("armToggle");
const regInput = document.getElementById("regInput");
const addRegBtn = document.getElementById("addRegBtn");

function fmtAddr(a) {
  return "0x" + Number(a).toString(16).toUpperCase();
}

async function api(url, method="GET", body=null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(url, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}

async function refresh() {
  const state = await api("/api/state");
  armToggle.checked = state.armed;

  devicesEl.innerHTML = "";
  for (const d of state.devices) {
    const key = `${d.name}__${d.unit_id}`;
    const values = state.latest[key] || {};

    const card = document.createElement("div");
    card.className = "card";

    const title = document.createElement("h2");
    title.textContent = `${d.name} (unit ${d.unit_id})`;
    card.appendChild(title);

    const table = document.createElement("table");
    table.className = "table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Register</th>
          <th>Value</th>
          <th>Status</th>
          <th>Write</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;
    const tbody = table.querySelector("tbody");

    for (const addr of state.registers) {
      const rv = values[addr];
      const ok = rv ? rv.ok : false;
      const val = rv && rv.value !== null ? rv.value : "—";
      const err = rv && rv.error ? rv.error : "";
      const ts = rv && rv.ts ? new Date(rv.ts * 1000).toLocaleTimeString() : "";

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${fmtAddr(addr)}</td>
        <td>${val}</td>
        <td class="${ok ? "good" : "bad"}">
          ${ok ? "OK" : "ERR"} ${err ? `<br><small>${err}</small>` : ""} ${ts ? `<br><small>${ts}</small>` : ""}
        </td>
        <td>
          <div class="write">
            <input data-addr="${addr}" placeholder="value" />
            <button data-addr="${addr}">Send</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);

      const btn = tr.querySelector("button");
      btn.addEventListener("click", async () => {
        const input = tr.querySelector("input");
        const value = Number(input.value);
        if (!Number.isFinite(value)) {
          alert("Enter a numeric value");
          return;
        }
        try {
          await api("/api/write", "POST", {
            device_name: d.name,
            unit_id: d.unit_id,
            address: addr,
            value: value
          });
          input.value = "";
          await refresh();
        } catch (e) {
          alert("Write failed: " + e.message);
        }
      });
    }

    card.appendChild(table);
    devicesEl.appendChild(card);
  }
}

armToggle.addEventListener("change", async () => {
  try {
    await api("/api/arm", "POST", { armed: armToggle.checked });
  } catch (e) {
    alert("Failed to set arm state: " + e.message);
    armToggle.checked = !armToggle.checked;
  }
});

addRegBtn.addEventListener("click", async () => {
  const raw = regInput.value.trim();
  if (!raw) return;
  try {
    await api("/api/registers", "POST", { address: raw });
    regInput.value = "";
    await refresh();
  } catch (e) {
    alert("Failed to add register: " + e.message);
  }
});

async function loop() {
  try { await refresh(); } catch (e) { console.error(e); }
  setTimeout(loop, 800);
}
loop();
