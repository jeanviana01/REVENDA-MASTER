/* Página de detalhes do veículo: lê ?id= da URL e monta a página com os dados da API. */
(function (w) {
  "use strict";
  var RM = w.RM;

  function ficha(rotulo, valor) {
    var d = RM.el("div", "vei-ficha");
    d.appendChild(RM.el("span", null, rotulo)); d.appendChild(RM.el("strong", null, valor || "—"));
    return d;
  }

  RM.veiculo = {
    render: function (raiz, id, urlVoltar) {
      urlVoltar = urlVoltar || "/";
      function voltar() { var a = RM.el("a", "vei-voltar", "‹ Voltar ao início"); a.href = urlVoltar; return a; }
      function mostrarErro(msg) {
        RM.limpar(raiz); raiz.appendChild(voltar());
        raiz.appendChild(RM.el("p", "estado erro", msg));
      }
      if (!/^\d+$/.test(String(id || ""))) { mostrarErro("Veículo não encontrado."); return Promise.resolve(); }
      return Promise.all([RM.api.vehicle(id), RM.api.meta().catch(function () { return { whatsapp: "" }; })]).then(function (r) {
        var c = r[0], meta = r[1];
        document.title = RM.nomeCarro(c) + " | Revenda Master";
        RM.limpar(raiz); raiz.appendChild(voltar());

        var topo = RM.el("header", "vei-topo");
        topo.appendChild(RM.el("p", "vei-cat", c.brand));
        var h = RM.el("h1", "vei-titulo", c.model + " ");
        if (c.version) h.appendChild(RM.el("span", null, c.version));
        topo.appendChild(h);
        topo.appendChild(RM.el("span", "selo" + (c.available ? "" : " indisp"), c.available ? "Disponível para venda" : "Indisponível"));
        if (c.description) topo.appendChild(RM.el("p", "vei-descricao", c.description));
        if (c.photos.length) {
          var vit = RM.el("div", "vei-vitrine"), img = RM.el("img");
          img.src = c.photos[0].url; img.alt = RM.nomeCarro(c);
          img.addEventListener("error", function () { vit.hidden = true; });
          vit.appendChild(img); topo.appendChild(vit);
        }
        raiz.appendChild(topo);

        var fichas = RM.el("section", "vei-fichas");
        fichas.setAttribute("aria-label", "Resumo");
        fichas.appendChild(ficha("Ano/modelo", c.year_label || String(c.year)));
        if (c.version) fichas.appendChild(ficha("Versão", c.version));
        fichas.appendChild(ficha("Cor", c.color)); fichas.appendChild(ficha("Câmbio", c.transmission));
        raiz.appendChild(fichas);

        if (c.sections.length) {
          var blocos = RM.el("section", "vei-blocos");
          c.sections.forEach(function (s) {
            var b = RM.el("article", "vei-bloco"); b.appendChild(RM.el("h2", null, s.title));
            var ul = RM.el("ul"); s.items.forEach(function (i) { ul.appendChild(RM.el("li", null, i)); });
            b.appendChild(ul); blocos.appendChild(b);
          });
          raiz.appendChild(blocos);
        }

        raiz.appendChild(RM.el("h2", "vei-secao", "Fotos do carro"));
        var extras = c.photos.slice(1);
        if (extras.length) {
          var gal = RM.el("section", "vei-galeria");
          extras.forEach(function (p) {
            var f = RM.el("figure"), im = RM.el("img"); im.src = p.url; im.alt = "Foto de " + RM.nomeCarro(c); im.loading = "lazy";
            im.addEventListener("error", function () { f.hidden = true; }); f.appendChild(im); gal.appendChild(f);
          });
          raiz.appendChild(gal);
        } else {
          raiz.appendChild(RM.el("p", "vei-vazio", "Mais fotos em breve."));
        }

        var ac = RM.el("div", "vei-acoes");
        if (meta.whatsapp) {
          var z = RM.el("a", "btn cheio", "Falar no WhatsApp");
          z.href = RM.linkWhats(meta.whatsapp, "Olá! Tenho interesse no " + c.brand + " " + c.model + (c.version ? " " + c.version : "") + " " + (c.year_label || c.year) + ".");
          z.target = "_blank"; z.rel = "noopener"; ac.appendChild(z);
        }
        var o = RM.el("a", "btn", "Ver outros carros"); o.href = urlVoltar; ac.appendChild(o);
        raiz.appendChild(ac);
      }).catch(function (e) { mostrarErro(e.status === 404 ? "Veículo não encontrado." : e.message); });
    }
  };

  var raiz = document.getElementById("vei-raiz");
  if (raiz && raiz.getAttribute("data-auto") !== "off") RM.veiculo.render(raiz, new URLSearchParams(location.search).get("id"));
})(window);
