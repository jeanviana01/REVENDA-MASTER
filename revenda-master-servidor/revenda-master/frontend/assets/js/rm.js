/* Revenda Master — base comum: auxiliares de DOM, cliente da API e cartão de veículo.
 * Todo texto vindo da API é inserido com textContent (nunca innerHTML), o que impede XSS. */
(function (w) {
  "use strict";
  var RM = (w.RM = w.RM || {});
  RM.config = RM.config || { linkVeiculo: function (id) { return "/veiculo?id=" + encodeURIComponent(id); } };

  RM.el = function (tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  RM.opcoes = function (sel, rotulo, lista) {
    sel.textContent = "";
    var o = RM.el("option", null, rotulo);
    o.value = "";
    sel.appendChild(o);
    lista.forEach(function (v) { var op = RM.el("option", null, String(v)); op.value = String(v); sel.appendChild(op); });
  };

  RM.linkWhats = function (numero, msg) {
    return "https://wa.me/" + String(numero || "").replace(/\D/g, "") + "?text=" + encodeURIComponent(msg);
  };

  RM.nomeCarro = function (c) {
    return c.brand + " " + c.model + (c.version ? " " + c.version : "") + " (" + (c.year_label || c.year) + ")";
  };

  RM.limpar = function (node) { while (node.firstChild) node.removeChild(node.firstChild); };

  /* ---------- Cliente da API ---------- */
  RM.csrf = null;

  RM.request = function (path, opts) {
    opts = opts || {};
    var ctrl = new AbortController(), timer = setTimeout(function () { ctrl.abort(); }, 20000);
    var init = { method: opts.method || "GET", credentials: "same-origin", signal: ctrl.signal, headers: {} };
    if (opts.json !== undefined) { init.body = JSON.stringify(opts.json); init.headers["Content-Type"] = "application/json"; }
    if (opts.form) init.body = opts.form;
    if (init.method !== "GET" && RM.csrf) init.headers["X-CSRF-Token"] = RM.csrf;
    return fetch(path, init).then(function (r) {
      clearTimeout(timer);
      return r.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = null; }
        if (!r.ok) {
          var err = new Error((data && data.error && data.error.message) || ("Erro " + r.status));
          err.status = r.status; err.fields = data && data.error && data.error.fields;
          throw err;
        }
        return data;
      });
    }, function (e) {
      clearTimeout(timer);
      var err = new Error(e && e.name === "AbortError" ? "O servidor demorou para responder." : "Não foi possível conectar ao servidor.");
      err.network = true;
      throw err;
    });
  };

  RM.api = {
    meta: function () { return RM.request("/api/meta"); },
    vehicles: function (filtros) {
      var qs = new URLSearchParams();
      Object.keys(filtros || {}).forEach(function (k) { if (filtros[k] !== "" && filtros[k] != null) qs.set(k, filtros[k]); });
      var s = qs.toString();
      return RM.request("/api/vehicles" + (s ? "?" + s : ""));
    },
    vehicle: function (id) { return RM.request("/api/vehicles/" + encodeURIComponent(id)); }
  };

  /* ---------- Cartão de veículo (usado nas listas e nos resultados) ---------- */
  RM.cartao = function (c) {
    var a = RM.el("a", "carro link");
    a.href = RM.config.linkVeiculo(c.id);
    if (c.photo) {
      var th = RM.el("img", "thumb");
      th.src = c.photo; th.alt = ""; th.loading = "lazy";
      th.addEventListener("error", function () { th.hidden = true; });       // foto indisponível: some sem quebrar o card
      a.appendChild(th);
    }
    var info = RM.el("div", "corpo");
    info.appendChild(RM.el("strong", null, RM.nomeCarro(c)));
    info.appendChild(RM.el("span", "detalhe", " · " + [c.color, c.transmission].filter(Boolean).join(" · ")));
    if (c.description) info.appendChild(RM.el("span", "desc", c.description));
    a.appendChild(info);
    a.appendChild(RM.el("span", "selo" + (c.available ? "" : " indisp"), c.available ? "Disponível para venda" : "Indisponível"));
    a.appendChild(RM.el("span", "ver", "Ver detalhes ›"));
    return a;
  };
})(window);
