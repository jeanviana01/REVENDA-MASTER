/* Área do administrador. Toda a segurança está no servidor: login, sessão, CSRF e permissões.
 * Este arquivo só monta a tela e chama a API; nenhuma senha ou segredo existe aqui. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var meta = null, veiculos = [], editando = null;      // editando = veículo (objeto detalhado) ou null

  function msg(id, texto, ok) { var e = $(id); e.textContent = texto || ""; e.className = "adm-msg" + (ok ? " ok" : ""); }
  function erroTexto(e) {
    if (e.fields) return Object.keys(e.fields).map(function (k) { return e.fields[k]; }).join(" ");
    return e.message;
  }
  function mostrar(logado, nome) {
    $("adm-login").hidden = logado; $("adm-painel").hidden = !logado;
    if (logado) $("adm-nome").textContent = nome;
  }

  // ---------- sessão ----------
  function carregarPainel() {
    return Promise.all([RM.api.meta(), RM.api.vehicles({})]).then(function (r) {
      meta = r[0]; veiculos = r[1].items;
      RM.opcoes($("f-marca"), "Selecione", meta.brands);
      RM.opcoes($("f-cambio"), "Selecione", meta.transmissions);
      var dm = $("dl-modelos"), dc = $("dl-cores"); RM.limpar(dm); RM.limpar(dc);
      Object.keys(meta.models_by_brand).forEach(function (b) { meta.models_by_brand[b].forEach(function (m) { var o = RM.el("option"); o.value = m; dm.appendChild(o); }); });
      meta.colors.forEach(function (c) { var o = RM.el("option"); o.value = c; dc.appendChild(o); });
      desenharLista();
    });
  }
  function iniciar() {
    RM.request("/api/auth/me").then(function (s) {
      if (s.authenticated) { RM.csrf = s.csrf_token; mostrar(true, s.username); return carregarPainel(); }
      mostrar(false);
    }).catch(function (e) { mostrar(false); msg("msg-geral", e.message); });
  }

  $("form-login").addEventListener("submit", function (ev) {
    ev.preventDefault();
    msg("msg-login", "");
    var user = $("adm-user").value.trim(), pass = $("adm-pass").value;
    if (!user || !pass) { msg("msg-login", "Informe usuário e senha."); return; }
    RM.request("/api/auth/login", { method: "POST", json: { username: user, password: pass } }).then(function (s) {
      RM.csrf = s.csrf_token; $("adm-pass").value = ""; mostrar(true, s.username); return carregarPainel();
    }).catch(function (e) { msg("msg-login", e.status === 401 ? "Usuário ou senha incorretos." : e.message); });
  });

  $("btn-sair").addEventListener("click", function () {
    RM.request("/api/auth/logout", { method: "POST" }).catch(function () {}).then(function () { RM.csrf = null; limparForm(); mostrar(false); });
  });

  // ---------- lista ----------
  function desenharLista() {
    var box = $("adm-lista"); RM.limpar(box); $("adm-qtd").textContent = veiculos.length;
    if (!veiculos.length) { box.appendChild(RM.el("p", "estado", "Nenhum veículo cadastrado.")); return; }
    veiculos.forEach(function (c) {
      var d = RM.el("div", "carro");
      if (c.photo) { var th = RM.el("img", "thumb"); th.src = c.photo; th.alt = ""; th.addEventListener("error", function () { th.hidden = true; }); d.appendChild(th); }
      var info = RM.el("div", "corpo");
      info.appendChild(RM.el("strong", null, RM.nomeCarro(c)));
      info.appendChild(RM.el("span", "detalhe", " · " + [c.color, c.transmission].filter(Boolean).join(" · ") + (c.photo ? "" : " · sem foto") + (c.available ? "" : " · indisponível")));
      if (c.description) info.appendChild(RM.el("span", "desc", c.description));
      d.appendChild(info);
      var ac = RM.el("div", "adm-acoes");
      var be = RM.el("button", "btn peq", "Editar"); be.type = "button"; be.addEventListener("click", function () { abrirEdicao(c.id); });
      var br = RM.el("button", "btn peq perigo", "Remover"); br.type = "button"; br.addEventListener("click", function () { remover(c); });
      ac.appendChild(be); ac.appendChild(br); d.appendChild(ac); box.appendChild(d);
    });
  }
  function recarregarLista() {
    return RM.api.vehicles({}).then(function (r) { veiculos = r.items; desenharLista(); });
  }
  function tratarSessao(e) {
    if (e.status === 401) { RM.csrf = null; mostrar(false); msg("msg-login", "Sua sessão expirou. Entre novamente."); return true; }
    return false;
  }

  function remover(c) {
    if (!w_confirm("Remover " + RM.nomeCarro(c) + "? As fotos também serão apagadas.")) return;
    RM.request("/api/admin/vehicles/" + c.id, { method: "DELETE" }).then(function () {
      if (editando && editando.id === c.id) limparForm();
      return recarregarLista();
    }).then(function () { msg("msg-form", "Veículo removido.", true); }).catch(function (e) { if (!tratarSessao(e)) msg("msg-form", erroTexto(e)); });
  }
  function w_confirm(t) { return window.confirm(t); }

  // ---------- formulário ----------
  function secoesParaTexto(secs) {
    return (secs || []).map(function (s) { return "# " + s.title + "\n" + s.items.join("\n"); }).join("\n");
  }
  function textoParaSecoes(txt) {
    var secs = [], atual = null;
    txt.split(/\r?\n/).forEach(function (linha) {
      var l = linha.trim();
      if (!l) return;
      if (l.charAt(0) === "#") { atual = { title: l.replace(/^#+\s*/, ""), items: [] }; secs.push(atual); }
      else { if (!atual) { atual = { title: "Detalhes", items: [] }; secs.push(atual); } atual.items.push(l); }
    });
    return secs;
  }

  function limparForm() {
    editando = null;
    ["f-modelo", "f-versao", "f-ano", "f-rotulo-ano", "f-cor", "f-desc", "f-detalhes"].forEach(function (i) { $(i).value = ""; });
    $("f-marca").value = ""; $("f-cambio").value = ""; $("f-disp").value = "1"; $("f-fotos").value = "";
    $("h-form").textContent = "Adicionar veículo"; $("btn-salvar").textContent = "Salvar veículo";
    $("btn-cancelar").hidden = true; $("bloco-fotos-atuais").hidden = true; RM.limpar($("fotos-atuais")); msg("msg-form", "");
  }
  $("btn-cancelar").addEventListener("click", limparForm);

  function desenharFotos(c) {
    var box = $("fotos-atuais"); RM.limpar(box);
    $("bloco-fotos-atuais").hidden = !c.photos.length;
    c.photos.forEach(function (p, i) {
      var f = RM.el("div", "adm-foto"), im = RM.el("img"); im.src = p.url; im.alt = "Foto " + (i + 1); f.appendChild(im);
      if (i === 0) f.appendChild(RM.el("small", null, "Principal"));
      var ac = RM.el("div", "adm-acoes");
      if (i > 0) { var bp = RM.el("button", "btn peq", "Tornar principal"); bp.type = "button"; bp.addEventListener("click", function () { acaoFoto("POST", "/api/admin/photos/" + p.id + "/main"); }); ac.appendChild(bp); }
      var bd = RM.el("button", "btn peq perigo", "Remover"); bd.type = "button";
      bd.addEventListener("click", function () { if (window.confirm("Remover esta foto?")) acaoFoto("DELETE", "/api/admin/photos/" + p.id); });
      ac.appendChild(bd); f.appendChild(ac); box.appendChild(f);
    });
  }
  function acaoFoto(method, url) {
    RM.request(url, { method: method }).then(function (c) { editando = c; desenharFotos(c); return recarregarLista(); })
      .catch(function (e) { if (!tratarSessao(e)) msg("msg-form", erroTexto(e)); });
  }

  function abrirEdicao(id) {
    RM.api.vehicle(id).then(function (c) {
      editando = c;
      $("f-marca").value = c.brand; $("f-modelo").value = c.model; $("f-versao").value = c.version; $("f-ano").value = c.year;
      $("f-rotulo-ano").value = c.year_label; $("f-cor").value = c.color; $("f-cambio").value = c.transmission;
      $("f-disp").value = c.available ? "1" : "0"; $("f-desc").value = c.description; $("f-detalhes").value = secoesParaTexto(c.sections);
      $("f-fotos").value = ""; desenharFotos(c);
      $("h-form").textContent = "Editar veículo"; $("btn-salvar").textContent = "Salvar alterações"; $("btn-cancelar").hidden = false;
      msg("msg-form", ""); $("h-form").scrollIntoView({ behavior: "smooth", block: "start" });
    }).catch(function (e) { msg("msg-form", e.message); });
  }

  function enviarFotos(id, arquivos, i) {
    if (i >= arquivos.length) return Promise.resolve(null);
    var fd = new FormData(); fd.append("photo", arquivos[i]);
    return RM.request("/api/admin/vehicles/" + id + "/photos", { method: "POST", form: fd }).then(function () { return enviarFotos(id, arquivos, i + 1); });
  }

  $("form-veiculo").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var dados = {
      brand: $("f-marca").value, model: $("f-modelo").value.trim(), version: $("f-versao").value.trim(),
      year: parseInt($("f-ano").value, 10), year_label: $("f-rotulo-ano").value.trim(), color: $("f-cor").value.trim(),
      transmission: $("f-cambio").value, description: $("f-desc").value.trim(), available: $("f-disp").value === "1",
      sections: textoParaSecoes($("f-detalhes").value)
    };
    if (!dados.brand || !dados.model || !dados.year || !dados.transmission) { msg("msg-form", "Preencha fabricante, modelo, ano e transmissão."); return; }
    var arquivos = Array.prototype.slice.call($("f-fotos").files || []);
    var grande = arquivos.filter(function (f) { return f.size > 5 * 1024 * 1024; });
    if (grande.length) { msg("msg-form", "Cada foto pode ter no máximo 5 MB."); return; }
    var criando = !editando, req = criando
      ? RM.request("/api/admin/vehicles", { method: "POST", json: dados })
      : RM.request("/api/admin/vehicles/" + editando.id, { method: "PUT", json: dados });
    var salvo = null;
    $("btn-salvar").disabled = true;
    req.then(function (c) { salvo = c; return enviarFotos(c.id, arquivos, 0); })
      .then(function () { return recarregarLista(); })
      .then(function () {
        if (criando) limparForm(); else { $("f-fotos").value = ""; }
        msg("msg-form", criando ? "Veículo adicionado." : "Alterações salvas.", true);       // depois de limpar, senão a mensagem some
        if (!criando) return RM.api.vehicle(salvo.id).then(function (c) { editando = c; desenharFotos(c); });
      })
      .catch(function (e) {
        if (!tratarSessao(e)) msg("msg-form", (salvo ? "O veículo foi salvo, mas houve erro nas fotos: " : "") + erroTexto(e));
        if (salvo) recarregarLista();
      })
      .then(function () { $("btn-salvar").disabled = false; });
  });

  // ---------- senha ----------
  $("form-senha").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var atual = $("pw-atual").value, nova = $("pw-nova").value, conf = $("pw-conf").value;
    if (!atual || !nova) { msg("msg-senha", "Preencha a senha atual e a nova."); return; }
    if (nova !== conf) { msg("msg-senha", "As senhas novas não são iguais."); return; }
    RM.request("/api/auth/password", { method: "POST", json: { current: atual, new: nova } }).then(function (r) {
      RM.csrf = r.csrf_token; ["pw-atual", "pw-nova", "pw-conf"].forEach(function (i) { $(i).value = ""; });
      msg("msg-senha", "Senha alterada.", true);
    }).catch(function (e) { if (!tratarSessao(e)) msg("msg-senha", erroTexto(e)); });
  });

  iniciar();
})();
