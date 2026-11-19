"""Render one self-contained HTML file (inline CSS/JS/data, no network)."""

from __future__ import annotations

import json
from dataclasses import asdict

from .inventory import Inventory

MAX_JSON_CHARS_FOR_SCRIPT = 8 * 1024 * 1024


def _payload(inventory: Inventory, product: str, generated: str, or_source: str) -> dict:
    rows = []
    for row in inventory.rows:
        data = asdict(row)
        data["in_combos"] = list(row.in_combos)
        data["in_use"] = row.in_use
        data["context"] = row.context
        data["max_completion"] = row.max_completion
        rows.append(data)
    return {
        "product": product,
        "generated": generated,
        "openrouter_source": or_source,
        "summary": inventory.summary(),
        "providers": inventory.providers,
        "combos": inventory.combos,
        "models": rows,
        "warnings": inventory.warnings,
    }


def _json_for_script(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Never let embedded data close the <script> element or start a comment.
    return (
        text.replace("</", "<\\/")
        .replace("<!--", "<\\!--")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def build_html(
    inventory: Inventory,
    *,
    product: str = "9router-follow-up",
    generated: str = "",
    or_source: str = "none",
) -> str:
    payload = _payload(inventory, product, generated, or_source)
    data = _json_for_script(payload)
    if len(data) > MAX_JSON_CHARS_FOR_SCRIPT:
        raise ValueError("inventory payload too large to embed")
    return _TEMPLATE.replace("__DATA__", data).replace("__PRODUCT__", _escape(product))


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>9router model inventory — __PRODUCT__</title>
<style>
:root{--bg:#fafaf8;--fg:#1c1c1a;--mut:#6b6b66;--card:#fff;--line:#dcdcd6;--acc:#2b6cb0;--ok:#2f855a;--bad:#c53030;--warn:#b7791f}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ededE8;--mut:#9a9a92;--card:#201f1d;--line:#3a3935;--acc:#63b3ed;--ok:#68d391;--bad:#fc8181;--warn:#ecc94b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:16px 20px 8px;display:flex;flex-wrap:wrap;gap:10px;align-items:baseline}
h1{font-size:18px;margin:0}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin:0 0 10px}
.mut{color:var(--mut)}
.grow{flex:1}
.btn{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:6px 14px;font:inherit;font-weight:600;cursor:pointer}
.btn:hover{filter:brightness(1.08)}
.btn:disabled{opacity:.55;cursor:default;filter:none}
.hint{color:var(--mut);font-size:12px;margin:0;padding:0 20px 8px}
main{padding:0 20px 40px;display:grid;gap:14px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.card .k{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.card .v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums;margin-top:2px}
.card .s{font-size:11px;color:var(--mut)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:10px}
input[type=search],select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font:inherit}
input[type=search]{min-width:260px}
label.chk{display:flex;gap:6px;align-items:center;color:var(--mut);font-size:12px}
.tablewrap{overflow:auto;max-height:62vh;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;text-align:left;white-space:nowrap;border-bottom:1px solid var(--line)}
thead th{position:sticky;top:0;background:var(--card);cursor:pointer;user-select:none;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);z-index:1}
thead th:hover{color:var(--fg)}
tbody tr:hover{background:color-mix(in srgb,var(--acc) 8%,transparent)}
td.num,th.num{text-align:right}
.tag{display:inline-block;padding:1px 6px;border-radius:999px;font-size:10.5px;border:1px solid var(--line);color:var(--mut)}
.tag.on{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 45%,transparent)}
.tag.off{color:var(--bad);border-color:color-mix(in srgb,var(--bad) 40%,transparent)}
.tag.warn{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 45%,transparent)}
.tag.combo{color:var(--acc);border-color:color-mix(in srgb,var(--acc) 45%,transparent)}
.tags{display:inline-flex;gap:4px;flex-wrap:wrap}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.grid2{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}
.box{border:1px solid var(--line);border-radius:8px;padding:10px}
.box h3{margin:0 0 6px;font-size:13px;display:flex;gap:8px;align-items:center}
ul.plain{list-style:none;margin:0;padding:0;display:grid;gap:4px}
ul.plain li{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.empty{color:var(--mut);font-size:12.5px}
footer{padding:0 20px 24px;color:var(--mut);font-size:11.5px}
</style>
</head>
<body>
<header>
  <h1>9router model inventory</h1>
  <span class="mut" id="subtitle">__PRODUCT__</span>
  <span class="grow"></span>
  <button class="btn" id="refresh" type="button">Refresh</button>
</header>
<p class="hint" id="refresh-hint"></p>
<main>
  <section class="cards" id="cards"></section>

  <section class="panel">
    <h2>Models</h2>
    <div class="toolbar">
      <input type="search" id="q" placeholder="Filter by model, provider, combo or OpenRouter name…" autocomplete="off">
      <select id="provider"><option value="">all providers</option></select>
      <label class="chk"><input type="checkbox" id="inuse"> only models in use</label>
      <span class="mut" id="count"></span>
    </div>
    <div class="tablewrap">
      <table>
        <thead><tr id="head"></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <h2>Providers &amp; connections</h2>
    <div class="grid2" id="providers"></div>
  </section>

  <section class="panel">
    <h2>Combos</h2>
    <div class="grid2" id="combos"></div>
  </section>

  <section class="panel" id="unmatched-panel">
    <h2>Not matched in OpenRouter</h2>
    <div id="unmatched"></div>
  </section>

  <section class="panel" id="warn-panel">
    <h2>Warnings</h2>
    <ul class="plain" id="warnings"></ul>
  </section>
</main>
<footer id="footer"></footer>

<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("data").textContent);
  var S = D.summary;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function fmt(n) {
    if (n === null || n === undefined || n === "") return "—";
    if (typeof n !== "number") return String(n);
    return n.toLocaleString("en-US");
  }
  function compact(n) {
    if (!n) return "0";
    if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
    if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
    return String(n);
  }
  function money(n) {
    if (n === null || n === undefined) return "—";
    if (n === 0) return "$0";
    if (n < 0.01) return "$" + n.toFixed(5);
    return "$" + n.toFixed(2);
  }
  function price(n) {
    if (n === null || n === undefined) return "—";
    if (n === 0) return "free";
    return "$" + (n >= 1 ? n.toFixed(2) : n.toFixed(3));
  }
  function when(ts) {
    if (!ts) return "—";
    var d = new Date(ts);
    if (isNaN(d.getTime())) return ts;
    return d.toISOString().slice(0, 16).replace("T", " ") + "Z";
  }

  // ---- cards
  var cards = [
    ["Models", fmt(S.models), S.models_enabled + " enabled"],
    ["In use", fmt(S.models_in_use), S.requests + " requests"],
    ["Tokens", compact(S.prompt_tokens + S.completion_tokens), compact(S.prompt_tokens) + " in / " + compact(S.completion_tokens) + " out"],
    ["Cost", money(S.cost), S.errors ? S.errors + " errors" : "no errors"],
    ["Providers", fmt(S.providers), S.connected + " with a connection"],
    ["Combos", fmt(S.combos), "configured combos"],
    ["OpenRouter", fmt(S.matched) + " / " + fmt(S.models), S.unmatched + " unmatched"],
    ["Window", S.first_seen ? when(S.first_seen).slice(0, 10) : "—", S.last_seen ? "to " + when(S.last_seen).slice(0, 10) : "no usage"]
  ];
  var cardBox = document.getElementById("cards");
  cards.forEach(function (c) {
    var box = el("div", "card");
    box.appendChild(el("div", "k", c[0]));
    box.appendChild(el("div", "v", c[1]));
    box.appendChild(el("div", "s", c[2]));
    cardBox.appendChild(box);
  });

  // ---- models table
  var COLS = [
    { key: "provider", label: "Provider" },
    { key: "model", label: "Model" },
    { key: "combo", label: "Combo" },
    { key: "requests", label: "Req", num: true },
    { key: "prompt_tokens", label: "In tok", num: true },
    { key: "completion_tokens", label: "Out tok", num: true },
    { key: "cost", label: "Cost", num: true },
    { key: "errors", label: "Err", num: true },
    { key: "last_seen", label: "Last used" },
    { key: "context", label: "Context", num: true },
    { key: "max_completion", label: "Max out", num: true },
    { key: "prompt_price", label: "$/1M in", num: true },
    { key: "completion_price", label: "$/1M out", num: true },
    { key: "or_match", label: "OR match" },
    { key: "enabled", label: "State" }
  ];
  var sortKey = "requests", sortDir = -1;
  var head = document.getElementById("head");
  COLS.forEach(function (c) {
    var th = el("th", c.num ? "num" : "", c.label);
    th.addEventListener("click", function () {
      if (sortKey === c.key) sortDir = -sortDir;
      else { sortKey = c.key; sortDir = c.num ? -1 : 1; }
      renderTable();
    });
    head.appendChild(th);
  });

  var providerSel = document.getElementById("provider");
  D.providers.map(function (p) { return p.provider; }).forEach(function (p) {
    var opt = el("option", "", p);
    opt.value = p;
    providerSel.appendChild(opt);
  });

  var CELL = {
    provider: function (r) { return r.provider; },
    model: function (r) {
      var wrap = el("span", "mono", r.model);
      var bits = [];
      if (r.or_name) bits.push(r.or_name);
      if (r.or_id) bits.push(r.or_id);
      if (r.modalities) bits.push(r.modalities);
      if (bits.length) wrap.title = bits.join(" · ");
      return wrap;
    },
    combo: function (r) {
      var names = r.in_combos || [];
      if (!names.length) return "—";
      var wrap = el("span", "tags");
      names.forEach(function (name) { wrap.appendChild(el("span", "tag combo", name)); });
      return wrap;
    },
    requests: function (r) { return r.requests ? fmt(r.requests) : "—"; },
    prompt_tokens: function (r) { return r.prompt_tokens ? compact(r.prompt_tokens) : "—"; },
    completion_tokens: function (r) { return r.completion_tokens ? compact(r.completion_tokens) : "—"; },
    cost: function (r) { return r.cost ? money(r.cost) : "—"; },
    errors: function (r) { return r.errors ? fmt(r.errors) : "—"; },
    last_seen: function (r) { return r.last_seen ? when(r.last_seen) : "—"; },
    context: function (r) { return r.context ? compact(r.context) : "—"; },
    max_completion: function (r) { return r.max_completion ? compact(r.max_completion) : "—"; },
    prompt_price: function (r) { return price(r.prompt_price); },
    completion_price: function (r) { return price(r.completion_price); },
    modalities: function (r) { return r.modalities || "—"; },
    or_match: function (r) {
      if (!r.or_match) return "—";
      var kind = r.or_match;
      var cls = kind === "exact" || kind === "provider" ? "on" : kind === "ambiguous" ? "off" : "warn";
      var t = el("span", "tag " + cls, kind);
      if (r.or_id) t.title = r.or_id;
      return t;
    },
    enabled: function (r) {
      return el("span", "tag " + (r.enabled ? "on" : "off"), r.enabled ? "enabled" : "disabled");
    }
  };

  function filtered() {
    var q = document.getElementById("q").value.trim().toLowerCase();
    var provider = providerSel.value;
    var onlyUsed = document.getElementById("inuse").checked;
    return D.models.filter(function (r) {
      if (provider && r.provider !== provider) return false;
      if (onlyUsed && !r.in_use) return false;
      if (!q) return true;
      return (r.provider + " " + r.model + " " + (r.or_name || "") + " " + (r.or_id || "") +
        " " + (r.in_combos || []).join(" "))
        .toLowerCase().indexOf(q) !== -1;
    });
  }

  function value(r, key) {
    var v = r[key];
    if (v === null || v === undefined) return "";
    if (Array.isArray(v)) return v.join(", ");
    return v;
  }

  function renderTable() {
    var rows = filtered();
    rows.sort(function (a, b) {
      var x = value(a, sortKey), y = value(b, sortKey);
      if (typeof x === "number" || typeof y === "number") {
        x = typeof x === "number" ? x : -1;
        y = typeof y === "number" ? y : -1;
      } else {
        x = String(x).toLowerCase(); y = String(y).toLowerCase();
      }
      return x < y ? -sortDir : x > y ? sortDir : 0;
    });
    var body = document.getElementById("rows");
    body.replaceChildren();
    rows.forEach(function (r) {
      var tr = el("tr");
      COLS.forEach(function (c) {
        var td = el("td", c.num ? "num" : "");
        var out = CELL[c.key](r);
        if (out instanceof Node) td.appendChild(out); else td.textContent = out;
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    document.getElementById("count").textContent =
      rows.length + " of " + D.models.length + " models";
    if (!rows.length) {
      var tr = el("tr");
      var td = el("td", "empty", "No models match this filter.");
      td.colSpan = COLS.length;
      tr.appendChild(td);
      body.appendChild(tr);
    }
  }

  ["q", "provider", "inuse"].forEach(function (id) {
    document.getElementById(id).addEventListener("input", renderTable);
    document.getElementById(id).addEventListener("change", renderTable);
  });

  // ---- providers
  var pbox = document.getElementById("providers");
  if (!D.providers.length) pbox.appendChild(el("div", "empty", "No providers found."));
  D.providers.forEach(function (p) {
    var box = el("div", "box");
    var h = el("h3", "", p.provider);
    h.appendChild(el("span", "tag " + (p.active_connections ? "on" : "warn"),
      p.active_connections ? "connected" : "no connection"));
    box.appendChild(h);
    box.appendChild(el("div", "mut",
      p.models + " models · " + p.in_use + " in use · " + fmt(p.requests) + " requests · " + money(p.cost)));
    var ul = el("ul", "plain");
    p.connections.forEach(function (c) {
      var li = el("li");
      li.appendChild(el("span", "tag " + (c.active ? "on" : "off"), c.active ? "active" : "off"));
      li.appendChild(el("span", "", c.name || "(unnamed)"));
      li.appendChild(el("span", "mut", c.auth_type + (c.priority !== null ? " · p" + c.priority : "")));
      ul.appendChild(li);
    });
    if (!p.connections.length) {
      var li = el("li", "empty", "no connection row (models may come from custom entries)");
      ul.appendChild(li);
    }
    box.appendChild(ul);
    pbox.appendChild(box);
  });

  // ---- combos
  var cbox = document.getElementById("combos");
  if (!D.combos.length) cbox.appendChild(el("div", "empty", "No combos configured."));
  D.combos.forEach(function (c) {
    var box = el("div", "box");
    box.appendChild(el("h3", "", c.name + (c.kind ? " · " + c.kind : "")));
    var ul = el("ul", "plain");
    c.members.forEach(function (m) {
      var li = el("li");
      li.appendChild(el("span", "tag " + (m.available ? "on" : "off"), m.available ? "available" : "missing"));
      li.appendChild(el("span", "mono", m.raw));
      if (m.in_use) li.appendChild(el("span", "tag on", "in use"));
      ul.appendChild(li);
    });
    box.appendChild(ul);
    cbox.appendChild(box);
  });

  // ---- unmatched
  var unmatched = D.models.filter(function (r) { return !r.or_id; });
  var panel = document.getElementById("unmatched-panel");
  var ubox = document.getElementById("unmatched");
  if (!unmatched.length) {
    panel.style.display = "none";
  } else {
    ubox.appendChild(el("div", "mut",
      unmatched.length + " model(s) have no OpenRouter counterpart: they are listed without pricing or context."));
    var ul = el("ul", "plain");
    unmatched.slice(0, 80).forEach(function (r) {
      var li = el("li");
      li.appendChild(el("span", "tag", r.provider));
      li.appendChild(el("span", "mono", r.model));
      if (r.in_use) li.appendChild(el("span", "mut", fmt(r.requests) + " req"));
      ul.appendChild(li);
    });
    ubox.appendChild(ul);
    if (unmatched.length > 80) ubox.appendChild(el("div", "mut", "+" + (unmatched.length - 80) + " more"));
  }

  // ---- warnings
  var wpanel = document.getElementById("warn-panel");
  var wlist = document.getElementById("warnings");
  if (!D.warnings.length) { wpanel.style.display = "none"; }
  D.warnings.forEach(function (w) { wlist.appendChild(el("li", "", w)); });

  document.getElementById("subtitle").textContent =
    D.product + " · generated " + D.generated + " · OpenRouter: " + D.openrouter_source;
  document.getElementById("footer").textContent =
    "Read-only: generated from ~/.9router (catalog + sqlite, no apiKeys) and the public OpenRouter models table.";
  renderTable();

  // ---- refresh
  var refreshBtn = document.getElementById("refresh");
  var hint = document.getElementById("refresh-hint");
  var CLI = "python3 -m nine_router_followup dashboard";
  var served = location.protocol === "http:" || location.protocol === "https:";
  if (!served) {
    refreshBtn.disabled = true;
    refreshBtn.title = "This file is a snapshot. Run: " + CLI;
    hint.textContent = "Static snapshot. Refresh with `" + CLI +
      "`, or run `python3 -m nine_router_followup serve` and use this button there.";
  } else {
    hint.textContent = "Served locally: the button regenerates the page from 9router and OpenRouter.";
    refreshBtn.addEventListener("click", function () {
      refreshBtn.disabled = true;
      refreshBtn.textContent = "Refreshing…";
      fetch("/refresh", { method: "POST" })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function () { location.reload(); })
        .catch(function (error) {
          refreshBtn.disabled = false;
          refreshBtn.textContent = "Refresh";
          hint.textContent = "Refresh failed: " + error.message;
        });
    });
  }
})();
</script>
</body>
</html>
"""
