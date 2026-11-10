// Gráficos em SVG puro (sem bibliotecas externas, compatível com a CSP do servidor).
// Todo texto vindo da API é inserido com textContent.
(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const $ = (sel) => document.querySelector(sel);

  const CORES = {
    instagram: "#d6337a", tiktok: "#111827", youtube: "#c53030", facebook: "#2b6cb0",
    pinterest: "#b83280", linkedin: "#0a66c2", x: "#4a5568", kwai: "#ff7a00", producao: "#718096",
  };
  const NOMES = {
    visualizacoes: "Visualizações", alcance: "Alcance", interacoes: "Interações",
    seguidores: "Seguidores", vendas: "Vendas", receita_centavos: "Receita líquida",
  };
  // Mapeia a métrica escolhida para a chave dos totais e para a série diária.
  const CHAVE_TOTAL = {
    visualizacoes: "visualizacoes", alcance: "alcance", interacoes: "interacoes",
    seguidores: "seguidores_atual", vendas: "vendas", receita_centavos: "receita_centavos",
  };

  let periodo = "semana";
  let metrica = "visualizacoes";
  let dados = null;

  const numero = (n) => Number(n || 0).toLocaleString("pt-BR");
  const reais = (c) => ((c || 0) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const formatar = (m, v) => (m === "receita_centavos" ? reais(v) : numero(v));

  function svgEl(tag, attrs = {}, texto) {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    if (texto !== undefined) e.textContent = texto;
    return e;
  }

  function el(tag, props = {}, filhos = []) {
    const e = document.createElement(tag);
    Object.entries(props).forEach(([k, v]) => {
      if (k === "className") e.className = v;
      else if (k === "text") e.textContent = v;
      else e.setAttribute(k, v);
    });
    filhos.forEach((f) => e.appendChild(f));
    return e;
  }

  async function carregar() {
    const r = await fetch(`/api/serie?periodo=${periodo}`, { credentials: "same-origin" });
    const conteudo = document.querySelectorAll("#conteudo > section");
    if (r.status === 401) {
      $("#sem-acesso").classList.remove("oculto");
      conteudo.forEach((x) => x.classList.add("oculto"));
      return;
    }
    dados = await r.json();
    $("#sem-acesso").classList.add("oculto");
    conteudo.forEach((x) => x.classList.remove("oculto"));
    desenhar();
  }

  function desenhar() {
    desenharKpis();
    desenharLinha();
    desenharBarras();
    desenharPizza();
    desenharTabela();
  }

  // ---------- KPIs ----------
  function desenharKpis() {
    const t = Object.values(dados.totais);
    const soma = (k) => t.reduce((a, x) => a + (x[k] || 0), 0);
    const visual = soma("visualizacoes"), alc = soma("alcance"), inter = soma("interacoes");
    const taxa = alc ? ((inter / alc) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%" : "—";
    const cards = [
      ["Visualizações", numero(visual)],
      ["Alcance", numero(alc)],
      ["Interações", numero(inter)],
      ["Taxa de interação", taxa],
      ["Seguidores (atual)", numero(soma("seguidores_atual"))],
      ["Vendas", numero(soma("vendas"))],
      ["Receita líquida", reais(soma("receita_centavos"))],
    ];
    $("#kpis").replaceChildren(...cards.map(([a, b]) =>
      el("div", { className: "kpi" }, [el("span", { text: a }), el("strong", { text: b })])));
  }

  // ---------- linha: evolução diária ----------
  function desenharLinha() {
    const W = 800, H = 280, ml = 70, mr = 20, mt = 20, mb = 40;
    const dias = dados.dias;
    const nomes = Object.keys(dados.series);
    $("#titulo-linha").textContent = `${NOMES[metrica]} por dia`;
    const cont = $("#grafico-linha");
    const legenda = $("#legenda-linha");

    if (!dias.length || !nomes.length) {
      cont.replaceChildren(el("div", { className: "vazio", text: "Sem dados no período." }));
      legenda.replaceChildren();
      return;
    }

    const serie = (n) => dados.series[n][metrica] || [];
    const max = Math.max(1, ...nomes.flatMap((n) => serie(n)));
    const n = dias.length;
    const x = (i) => ml + (n === 1 ? (W - ml - mr) / 2 : (i * (W - ml - mr)) / (n - 1));
    const y = (v) => mt + (1 - v / max) * (H - mt - mb);

    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "grafico", role: "img",
      "aria-label": `Gráfico de linha: ${NOMES[metrica]} por dia` });

    // eixo Y com 4 marcas
    for (let k = 0; k <= 4; k++) {
      const v = (max * k) / 4;
      const yy = y(v);
      svg.appendChild(svgEl("line", { x1: ml, x2: W - mr, y1: yy, y2: yy, class: "eixo" }));
      svg.appendChild(svgEl("text", { x: ml - 8, y: yy + 4, "text-anchor": "end" }, formatar(metrica, Math.round(v))));
    }
    // eixo X com rótulos espaçados
    const passo = Math.max(1, Math.ceil(n / 8));
    const indices = [];
    for (let i = 0; i < n; i += passo) indices.push(i);
    if (indices[indices.length - 1] !== n - 1) {
      // o último dia sempre aparece, mas sem colidir com o rótulo anterior
      if (indices.length && n - 1 - indices[indices.length - 1] < passo) indices.pop();
      indices.push(n - 1);
    }
    indices.forEach((i) => {
      const [, mes, dia] = dias[i].split("-");
      svg.appendChild(svgEl("text", { x: x(i), y: H - 14, "text-anchor": "middle" }, `${dia}/${mes}`));
    });

    // uma linha por rede
    nomes.forEach((nome) => {
      const valores = serie(nome);
      const cor = CORES[nome] || "#2b6cb0";
      const d = valores.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
      svg.appendChild(svgEl("path", { d, fill: "none", stroke: cor, "stroke-width": 2.5, "stroke-linejoin": "round" }));
      if (n <= 31) {
        valores.forEach((v, i) => {
          const c = svgEl("circle", { cx: x(i), cy: y(v), r: 3, fill: cor });
          const titulo = svgEl("title", {}, `${nome} · ${dias[i]} · ${formatar(metrica, v)}`);
          c.appendChild(titulo);
          svg.appendChild(c);
        });
      }
    });

    cont.replaceChildren(svg);
    legenda.replaceChildren(...nomes.map((nome) =>
      el("span", { style: `--cor:${CORES[nome] || "#2b6cb0"}`, text: nome })));
  }

  // ---------- barras: total por rede ----------
  function desenharBarras() {
    const chave = CHAVE_TOTAL[metrica];
    $("#titulo-barras").textContent = `Total de ${NOMES[metrica].toLowerCase()} por rede`;
    const linhas = Object.entries(dados.totais)
      .map(([nome, t]) => ({ nome, valor: t[chave] || 0 }))
      .sort((a, b) => b.valor - a.valor);
    const max = Math.max(1, ...linhas.map((l) => l.valor));
    if (!linhas.length) {
      $("#grafico-barras").replaceChildren(el("div", { className: "vazio", text: "Sem dados no período." }));
      return;
    }
    $("#grafico-barras").replaceChildren(...linhas.map((l) =>
      el("div", { className: "linha-barra" }, [
        el("div", { className: "rotulo" }, [
          el("span", { text: l.nome }),
          el("span", { text: formatar(metrica, l.valor) }),
        ]),
        el("div", { className: "barra" }, [
          el("div", { style: `width:${(l.valor / max) * 100}%;background:${CORES[l.nome] || "#2b6cb0"}` }),
        ]),
      ])));
  }

  // ---------- pizza: participação ----------
  function desenharPizza() {
    const chave = CHAVE_TOTAL[metrica];
    const fatias = Object.entries(dados.totais)
      .map(([nome, t]) => ({ nome, valor: Math.max(0, t[chave] || 0) }))
      .filter((f) => f.valor > 0);
    const total = fatias.reduce((a, f) => a + f.valor, 0);
    const cont = $("#grafico-pizza");
    const legenda = $("#legenda-pizza");
    if (!total) {
      cont.replaceChildren(el("div", { className: "vazio", text: "Sem dados no período." }));
      legenda.replaceChildren();
      return;
    }

    const R = 90, cx = 110, cy = 110;
    const svg = svgEl("svg", { viewBox: "0 0 220 220", width: 220, height: 220, role: "img",
      "aria-label": `Participação por rede em ${NOMES[metrica].toLowerCase()}` });
    let angulo = -Math.PI / 2;
    fatias.forEach((f) => {
      const cor = CORES[f.nome] || "#2b6cb0";
      const share = f.valor / total;
      if (fatias.length === 1 || share >= 0.9999) {
        svg.appendChild(svgEl("circle", { cx, cy, r: R, fill: cor }));
      } else {
        const a2 = angulo + share * 2 * Math.PI;
        const x1 = cx + R * Math.cos(angulo), y1 = cy + R * Math.sin(angulo);
        const x2 = cx + R * Math.cos(a2), y2 = cy + R * Math.sin(a2);
        const grande = share > 0.5 ? 1 : 0;
        const path = svgEl("path", {
          d: `M${cx},${cy} L${x1.toFixed(2)},${y1.toFixed(2)} A${R},${R} 0 ${grande} 1 ${x2.toFixed(2)},${y2.toFixed(2)} Z`,
          fill: cor, stroke: "#fff", "stroke-width": 1.5,
        });
        path.appendChild(svgEl("title", {}, `${f.nome}: ${(share * 100).toFixed(1)}%`));
        svg.appendChild(path);
        angulo = a2;
      }
    });
    cont.replaceChildren(svg);
    legenda.replaceChildren(...fatias.map((f) =>
      el("span", { style: `--cor:${CORES[f.nome] || "#2b6cb0"}`,
        text: `${f.nome} ${((f.valor / total) * 100).toFixed(1).replace(".", ",")}%` })));
  }

  // ---------- tabela ----------
  function desenharTabela() {
    const linhas = Object.entries(dados.totais)
      .sort((a, b) => b[1].visualizacoes - a[1].visualizacoes)
      .map(([nome, t]) => {
        const taxa = t.alcance ? ((t.interacoes / t.alcance) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%" : "—";
        return el("tr", {}, [
          el("td", { text: nome }),
          el("td", { className: "num", text: numero(t.visualizacoes) }),
          el("td", { className: "num", text: numero(t.alcance) }),
          el("td", { className: "num", text: numero(t.interacoes) }),
          el("td", { className: "num", text: taxa }),
          el("td", { className: "num", text: numero(t.seguidores_atual) }),
          el("td", { className: "num", text: numero(t.vendas) }),
          el("td", { className: "num", text: reais(t.receita_centavos) }),
        ]);
      });
    $("#tabela-resumo").replaceChildren(...linhas);
  }

  // ---------- controles ----------
  $("#periodos").addEventListener("click", (ev) => {
    if (!ev.target.dataset.p) return;
    periodo = ev.target.dataset.p;
    document.querySelectorAll("#periodos button").forEach((b) => b.classList.toggle("ativo", b === ev.target));
    carregar().catch(console.error);
  });
  $("#metricas").addEventListener("click", (ev) => {
    if (!ev.target.dataset.m) return;
    metrica = ev.target.dataset.m;
    document.querySelectorAll("#metricas button").forEach((b) => b.classList.toggle("ativo", b === ev.target));
    if (dados) desenhar();
  });

  carregar().catch(console.error);
})();
