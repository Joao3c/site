// Frontend do painel. Todo conteúdo vindo da API é inserido como texto (textContent), nunca como HTML.
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  let periodo = "semana";
  let usuario = null;

  const reais = (centavos) =>
    centavos == null ? "—" : (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const numero = (n) => (n == null ? "—" : Number(n).toLocaleString("pt-BR"));

  function el(tag, props = {}, filhos = []) {
    const e = document.createElement(tag);
    Object.entries(props).forEach(([k, v]) => {
      if (k === "className") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (typeof v === "function") e.addEventListener(k.replace(/^on/, ""), v);
      else e.setAttribute(k, v);
    });
    filhos.forEach((f) => e.appendChild(f));
    return e;
  }

  async function api(caminho, opcoes = {}) {
    const r = await fetch(caminho, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      ...opcoes,
      body: opcoes.body ? JSON.stringify(opcoes.body) : undefined,
    });
    let dados = {};
    try { dados = await r.json(); } catch (_) { /* sem corpo */ }
    if (r.status === 401) { mostrarLogin(); throw new Error("sessão expirada"); }
    if (!r.ok) throw new Error(dados.erro || "erro na requisição");
    return dados;
  }

  function mostrarLogin() {
    $("#app").classList.add("oculto");
    $("#login").classList.remove("oculto");
  }
  function mostrarApp() {
    $("#login").classList.add("oculto");
    $("#app").classList.remove("oculto");
  }

  // ---------- login ----------
  $("#form-login").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    $("#erro-login").textContent = "";
    try {
      await api("/api/login", { method: "POST", body: { email: f.email.value, senha: f.senha.value } });
      f.senha.value = "";
      await iniciar();
    } catch (e) {
      $("#erro-login").textContent = e.message;
    }
  });

  $("#sair").addEventListener("click", async () => {
    await api("/api/logout", { method: "POST", body: {} }).catch(() => {});
    mostrarLogin();
  });

  // ---------- painel ----------
  async function carregarResumo() {
    const dados = await api(`/api/resumo?periodo=${periodo}`);
    const redes = dados.redes;
    const totais = redes.reduce((a, r) => {
      a.receita += r.receita_liquida_centavos; a.investido += r.investido_centavos;
      a.alcance += r.alcance; a.clientes += r.clientes; a.vendas += r.vendas_qtd;
      return a;
    }, { receita: 0, investido: 0, alcance: 0, clientes: 0, vendas: 0 });

    const kpis = [
      ["Receita líquida atribuída", reais(totais.receita)],
      ["Investimento em mídia", reais(totais.investido)],
      ["Vendas", numero(totais.vendas)],
      ["Clientes", numero(totais.clientes)],
      ["Alcance", numero(totais.alcance)],
      ["Retorno sobre mídia", totais.investido ? (totais.receita / totais.investido).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "x" : "—"],
    ];
    $("#kpis").replaceChildren(...kpis.map(([t, v]) =>
      el("div", { className: "kpi" }, [el("span", { text: t }), el("strong", { text: v })])));

    const linhas = redes.map((r) => {
      const lucroClasse = r.lucro_liquido_centavos >= 0 ? "up" : "down";
      return el("tr", {}, [
        el("td", { text: r.plataforma }),
        el("td", { className: "num", text: reais(r.investido_centavos) }),
        el("td", { className: "num", text: reais(r.receita_liquida_centavos) }),
        el("td", { className: "num", text: numero(r.clientes) }),
        el("td", { className: "num", text: reais(r.custo_por_cliente_centavos) }),
        el("td", { className: "num " + lucroClasse, text: reais(r.lucro_liquido_centavos) }),
      ]);
    });
    $("#ranking").replaceChildren(...linhas);
    $("#nota-lucro").textContent = dados.aviso;

    const maxAlc = Math.max(1, ...redes.map((r) => r.alcance));
    $("#barras").replaceChildren(...redes.map((r) =>
      el("div", { className: "linha-barra" }, [
        el("div", { className: "rotulo" }, [
          el("span", { text: r.plataforma }),
          el("span", { text: `${numero(r.alcance)} · ${numero(r.interacoes)} interações` }),
        ]),
        el("div", { className: "barra" }, [
          el("div", { style: `width:${(r.alcance / maxAlc) * 100}%` }),
        ]),
      ])));
  }

  async function carregarRecomendacoes() {
    const dados = await api("/api/recomendacoes");
    const pendentes = dados.historico.filter((r) => r.status === "pendente");
    const itens = [];
    pendentes.forEach((r) => itens.push(cartaoRecomendacao(r, true)));
    dados.gerar_novas.forEach((r) => itens.push(cartaoRecomendacao(r, false)));
    $("#recomendacoes").replaceChildren(...(itens.length ? itens : [el("p", { className: "nota", text: "Nenhuma recomendação no momento." })]));
  }

  function cartaoRecomendacao(r, persistida) {
    const classes = "rec" + (r.tipo === "alerta" ? " alerta" : "");
    const filhos = [
      el("strong", { text: r.texto }),
      el("p", { text: r.justificativa }),
      el("small", { text: `Confiança: ${r.confianca}` }),
    ];
    if (persistida && r.id) {
      filhos.push(el("div", { className: "acoes-rec" }, [
        el("button", { text: "Aprovar", onclick: () => decidir(r.id, "aprovada") }),
        el("button", { className: "secundario", text: "Rejeitar", onclick: () => decidir(r.id, "rejeitada") }),
      ]));
    }
    return el("div", { className: classes }, filhos);
  }

  async function decidir(id, decisao) {
    try {
      await api(`/api/recomendacao/${id}`, { method: "POST", body: { decisao } });
      await carregarRecomendacoes();
    } catch (e) { alert(e.message); }
  }

  async function carregarFinanceiro() {
    const lista = await api("/api/financeiro");
    if (!lista.length) {
      $("#financeiro").replaceChildren(el("p", { className: "nota", text: "Nenhum período recebido do sistema financeiro." }));
      return;
    }
    const f = lista[0];
    const lucroReal = f.faturamento_liquido_centavos - f.custos_operacionais_centavos - f.despesas_centavos;
    const margem = f.faturamento_bruto_centavos ? (lucroReal / f.faturamento_bruto_centavos) * 100 : 0;
    const linhas = [
      ["Período", f.periodo],
      ["Faturamento bruto", reais(f.faturamento_bruto_centavos)],
      ["Faturamento líquido", reais(f.faturamento_liquido_centavos)],
      ["Custos operacionais", reais(f.custos_operacionais_centavos)],
      ["Impostos", reais(f.impostos_centavos)],
      ["Despesas", reais(f.despesas_centavos)],
      ["Lucro real (estimado*)", reais(lucroReal)],
      ["Margem sobre bruto", margem.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%"],
      ["Orçamento disponível para marketing", reais(f.orcamento_marketing_centavos)],
    ];
    $("#financeiro").replaceChildren(
      el("table", {}, linhas.map(([a, b]) =>
        el("tr", {}, [el("td", { text: a }), el("td", { className: "num", text: b })]))),
      el("p", { className: "nota", text: "*Lucro real estimado = faturamento líquido − custos operacionais − despesas. Premissa a validar com o financeiro: se o faturamento líquido já desconta impostos." }));
  }

  async function carregarAuditoria() {
    const lista = await api("/api/auditoria");
    $("#auditoria").replaceChildren(...lista.slice(0, 30).map((a) =>
      el("div", { text: `${new Date(a.criado_em * 1000).toLocaleString("pt-BR")} — ${a.acao}${a.entidade ? " · " + a.entidade : ""}` })));
  }

  async function carregarContas() {
    const contas = await api("/api/contas");
    $("#select-conta").replaceChildren(...contas.map((c) =>
      el("option", { value: c.id, text: `${c.plataforma} — ${c.nome_conta}` })));
  }

  async function carregarTudo() {
    const tarefas = [carregarResumo(), carregarRecomendacoes(), carregarFinanceiro(), carregarAuditoria()];
    if (usuario && usuario.papel !== "leitor") tarefas.push(carregarContas());
    await Promise.allSettled(tarefas);
    const demo = usuario && usuario.email.endsWith("@demo.local");
    $("#aviso-demo").classList.toggle("oculto", !demo);
    $("#bloco-registro").classList.toggle("oculto", !usuario || usuario.papel === "leitor");
  }

  $("#periodos").addEventListener("click", (ev) => {
    if (!ev.target.dataset.p) return;
    periodo = ev.target.dataset.p;
    document.querySelectorAll("#periodos button").forEach((b) => b.classList.toggle("ativo", b === ev.target));
    carregarResumo().catch(console.error);
  });

  // ---------- formulários de registro ----------
  function enviarFormulario(id, caminho, montar) {
    $(id).addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const f = ev.target;
      try {
        await api(caminho, { method: "POST", body: montar(f) });
        $("#msg-registro").textContent = "Salvo com sucesso.";
        f.reset();
        await carregarTudo();
      } catch (e) {
        $("#msg-registro").textContent = e.message;
      }
    });
  }

  enviarFormulario("#form-gasto", "/api/gasto", (f) => ({
    plataforma: f.plataforma.value, data: f.data.value, valor: f.valor.value, descricao: f.descricao.value,
  }));
  enviarFormulario("#form-venda", "/api/venda", (f) => ({
    data: f.data.value, valor_bruto: f.valor_bruto.value, valor_liquido: f.valor_liquido.value || f.valor_bruto.value,
    plataforma_origem: f.plataforma_origem.value, cliente_id: f.cliente_id.value, id_externo: f.id_externo.value,
  }));
  enviarFormulario("#form-metricas", "/api/metricas", (f) => {
    const corpo = { conta_id: f.conta_id.value, data: f.data.value };
    ["alcance", "visualizacoes", "curtidas", "comentarios", "compartilhamentos", "salvamentos", "seguidores"]
      .forEach((k) => { corpo[k] = Number(f[k].value || 0); });
    return corpo;
  });
  enviarFormulario("#form-conta", "/api/conta", (f) => ({
    plataforma: f.plataforma.value, nome_conta: f.nome_conta.value,
  }));

  // ---------- inicialização ----------
  async function iniciar() {
    try {
      usuario = await api("/api/eu");
      $("#usuario").textContent = `${usuario.email} · ${usuario.papel}`;
      mostrarApp();
      await carregarTudo();
    } catch (_) {
      mostrarLogin();
    }
  }

  const hoje = new Date().toISOString().slice(0, 10);
  document.querySelectorAll('input[type="date"]').forEach((i) => { i.value = hoje; });
  iniciar();
})();
