/* Página inicial: Fabricantes, Buscar e contato. Os dados vêm da API (/api/meta e /api/vehicles). */
(function () {
  "use strict";
  if (!document.getElementById("form-busca")) return;
  var $ = function (id) { return document.getElementById(id); };
  var meta = null;
  var LOGOS = { Chevrolet: "chevrolet", Volkswagen: "volkswagen", Fiat: "fiat", Jeep: "jeep", Hyundai: "hyundai", Toyota: "toyota", Honda: "honda", Renault: "renault" };
  var selMarca = $("sel-marca"), selModelo = $("sel-modelo"), selAno = $("sel-ano"), selCor = $("sel-cor"), selCambio = $("sel-cambio");
  var boxMarcas = $("marcas"), listaMarca = $("lista-marca"), resultado = $("resultado");

  function whats(msg) { return RM.linkWhats(meta && meta.whatsapp, msg); }
  function temWhats() { return !!(meta && meta.whatsapp); }

  function estadoErro(box, texto, tentar) {
    RM.limpar(box);
    var d = RM.el("div", "estado erro", texto);
    if (tentar) { var b = RM.el("button", "btn", "Tentar de novo"); b.type = "button"; b.addEventListener("click", tentar); d.appendChild(document.createElement("br")); d.appendChild(b); }
    box.appendChild(d);
  }

  function botaoEncomendar(msg) {
    if (!temWhats()) return RM.el("p", "estado", "Fale com a loja para encomendar este carro.");
    var l = RM.el("a", "btn cheio", "Gostaria de encomendar?");
    l.href = whats(msg); l.target = "_blank"; l.rel = "noopener";
    return l;
  }

  function modelosDe(marca) {
    var m = meta.models_by_brand || {};
    if (marca) return m[marca] || [];
    var todos = [];
    Object.keys(m).forEach(function (k) { todos = todos.concat(m[k]); });
    return todos.sort();
  }

  function montarFiltros() {
    RM.opcoes(selMarca, "Qualquer fabricante", meta.brands);
    RM.opcoes(selModelo, "Qualquer modelo", modelosDe(""));
    RM.opcoes(selAno, "Qualquer ano", meta.years);
    RM.opcoes(selCor, "Qualquer cor", meta.colors);
    RM.opcoes(selCambio, "Qualquer transmissão", meta.transmissions);
  }
  selMarca.addEventListener("change", function () {
    var atual = selModelo.value, lista = modelosDe(selMarca.value);
    RM.opcoes(selModelo, "Qualquer modelo", lista);
    if (lista.indexOf(atual) >= 0) selModelo.value = atual;
  });

  // Abrir e fechar painéis
  var paineis = [{ btn: $("btn-fabricantes"), box: $("painel-fabricantes") }, { btn: $("btn-buscar"), box: $("painel-buscar") }];
  paineis.forEach(function (p) {
    p.btn.addEventListener("click", function () {
      var abrir = p.box.hidden;
      paineis.forEach(function (q) { q.box.hidden = true; q.btn.setAttribute("aria-expanded", "false"); });
      if (abrir) {
        p.box.hidden = false; p.btn.setAttribute("aria-expanded", "true");
        p.box.scrollIntoView({ behavior: "smooth", block: "nearest" });
        if (p.box.id === "painel-buscar") selMarca.focus({ preventScroll: true });
      }
    });
  });

  // Fabricantes: um clique abre a lista de carros da marca, o segundo clique fecha
  function montarMarcas() {
    RM.limpar(boxMarcas);
    meta.brands.forEach(function (m) {
      var b = RM.el("button"); b.type = "button"; b.setAttribute("aria-pressed", "false");
      if (LOGOS[m]) { var im = RM.el("img"); im.src = RM.config.logo ? RM.config.logo(LOGOS[m]) : "/assets/img/" + LOGOS[m] + ".png"; im.alt = ""; im.loading = "lazy"; im.addEventListener("error", function () { im.hidden = true; }); b.appendChild(im); }
      b.appendChild(RM.el("span", null, m));
      b.addEventListener("click", function () { abrirMarca(b, m); });
      boxMarcas.appendChild(b);
    });
  }
  function abrirMarca(b, marca) {
    var estavaAberta = b.getAttribute("aria-pressed") === "true";
    Array.prototype.forEach.call(boxMarcas.children, function (x) { x.setAttribute("aria-pressed", "false"); });
    RM.limpar(listaMarca);
    if (estavaAberta) return;
    b.setAttribute("aria-pressed", "true");
    listaMarca.appendChild(RM.el("div", "estado", "Carregando…"));
    RM.api.vehicles({ brand: marca }).then(function (r) {
      if (b.getAttribute("aria-pressed") !== "true") return;           // o usuário já fechou ou trocou de marca
      RM.limpar(listaMarca);
      if (!r.items.length) {
        listaMarca.appendChild(RM.el("p", null, "Nenhum " + marca + " disponível no momento. "));
        listaMarca.appendChild(botaoEncomendar("Olá! Gostaria de encomendar um carro da marca " + marca + "."));
        return;
      }
      r.items.forEach(function (c) { listaMarca.appendChild(RM.cartao(c)); });
    }).catch(function (e) {
      if (b.getAttribute("aria-pressed") === "true") estadoErro(listaMarca, e.message, function () { b.setAttribute("aria-pressed", "false"); abrirMarca(b, marca); });
    });
  }

  // Busca: usa só os filtros escolhidos e mostra todos os carros que combinam
  $("form-busca").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var f = { brand: selMarca.value, model: selModelo.value, year: selAno.value, color: selCor.value, transmission: selCambio.value };
    resultado.className = "resultado"; RM.limpar(resultado);
    if (!f.brand && !f.model && !f.year && !f.color && !f.transmission) {
      resultado.className = "resultado nao-achou";
      resultado.textContent = "Escolha pelo menos uma opção (fabricante, modelo, ano, cor ou transmissão) para buscar.";
      return;
    }
    resultado.className = "resultado"; resultado.textContent = "Buscando…";
    RM.api.vehicles(f).then(function (r) {
      RM.limpar(resultado);
      if (r.items.length) {
        resultado.className = "resultado achou";
        resultado.appendChild(RM.el("p", "aviso", r.count === 1 ? "Encontramos 1 carro para você" : "Encontramos " + r.count + " carros para você"));
        r.items.forEach(function (c) { resultado.appendChild(RM.cartao(c)); });
      } else {
        resultado.className = "resultado nao-achou";
        resultado.appendChild(RM.el("p", "aviso", "Que pena que não temos disponível no momento."));
        var pedido = [f.brand, f.model, f.year].filter(Boolean).join(" "), extras = [];
        if (f.color) extras.push("cor " + f.color.toLowerCase());
        if (f.transmission) extras.push("câmbio " + f.transmission.toLowerCase());
        resultado.appendChild(botaoEncomendar("Olá! Gostaria de encomendar um " + (pedido || "carro") + (extras.length ? ", " + extras.join(", ") : "") + "."));
      }
    }).catch(function (e) { resultado.className = "resultado nao-achou"; estadoErro(resultado, e.message, function () { $("form-busca").requestSubmit(); }); });
  });

  function contato() {
    var msg = "Olá! Vim pelo site da Revenda Master e gostaria de falar com a loja.";
    ["btn-zap", "zap-flutuante"].forEach(function (id) { var a = $(id); if (temWhats()) { a.href = whats(msg); a.hidden = false; } });
    $("btn-maps").href = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(meta.address || "");
  }

  function iniciar() {
    RM.api.meta().then(function (m) { meta = m; montarFiltros(); montarMarcas(); contato(); })
      .catch(function (e) {
        [listaMarca, resultado].forEach(function (box) { estadoErro(box, "Não foi possível carregar o catálogo. " + e.message, iniciar); });
        $("btn-maps").href = "https://www.google.com/maps";
      });
  }
  iniciar();
})();
