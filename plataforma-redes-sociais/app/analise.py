"""Cálculos de desempenho, atribuição e lucro por rede social."""
from datetime import date, timedelta
from db import conectar

PERIODOS_DIAS = {"dia": 1, "semana": 7, "mes": 30, "ano": 365}
MIN_AMOSTRA_RECOMENDACAO = 14  # dias de histórico antes de recomendar


def intervalo(periodo, hoje=None):
    hoje = hoje or date.today()
    dias = PERIODOS_DIAS.get(periodo, 7)
    inicio = hoje - timedelta(days=dias - 1)
    return inicio.isoformat(), hoje.isoformat()


def resumo_por_rede(empresa_id, periodo, hoje=None):
    """Métricas, investimento, vendas atribuídas e lucro líquido por plataforma."""
    ini, fim = intervalo(periodo, hoje)
    with conectar() as con:
        metricas = con.execute(
            """SELECT c.plataforma,
                      COALESCE(SUM(m.alcance),0) AS alcance,
                      COALESCE(SUM(m.visualizacoes),0) AS visualizacoes,
                      COALESCE(SUM(m.curtidas+m.comentarios+m.compartilhamentos+m.salvamentos),0) AS interacoes
               FROM conta_rede c LEFT JOIN metrica_diaria m
                 ON m.conta_id = c.id AND m.data BETWEEN ? AND ?
               WHERE c.empresa_id = ? GROUP BY c.plataforma""",
            (ini, fim, empresa_id),
        ).fetchall()
        gastos = {
            r["plataforma"]: r["total"]
            for r in con.execute(
                """SELECT plataforma, SUM(valor_centavos) AS total FROM gasto_midia
                   WHERE empresa_id = ? AND data BETWEEN ? AND ? GROUP BY plataforma""",
                (empresa_id, ini, fim),
            )
        }
        vendas = {
            r["plataforma"]: r
            for r in con.execute(
                """SELECT plataforma_origem AS plataforma, COUNT(*) AS qtd,
                          SUM(valor_bruto_centavos) AS bruto, SUM(valor_liquido_centavos) AS liquido,
                          COUNT(DISTINCT cliente_id) AS clientes
                   FROM venda WHERE empresa_id = ? AND data BETWEEN ? AND ?
                   GROUP BY plataforma_origem""",
                (empresa_id, ini, fim),
            )
        }
        custo_producao = con.execute(
            """SELECT COALESCE(SUM(valor_centavos),0) AS t FROM gasto_midia
               WHERE empresa_id = ? AND plataforma = 'producao' AND data BETWEEN ? AND ?""",
            (empresa_id, ini, fim),
        ).fetchone()["t"]

    linhas = []
    for m in metricas:
        p = m["plataforma"]
        v = vendas.get(p)
        investido = gastos.get(p, 0)
        receita_liquida = v["liquido"] if v and v["liquido"] else 0
        clientes = v["clientes"] if v and v["clientes"] else 0
        linhas.append({
            "plataforma": p,
            "alcance": m["alcance"],
            "visualizacoes": m["visualizacoes"],
            "interacoes": m["interacoes"],
            "investido_centavos": investido,
            "vendas_qtd": v["qtd"] if v else 0,
            "vendas_bruto_centavos": v["bruto"] if v and v["bruto"] else 0,
            "receita_liquida_centavos": receita_liquida,
            "clientes": clientes,
            "custo_por_cliente_centavos": round(investido / clientes) if clientes else None,
            "lucro_liquido_centavos": receita_liquida - investido,
        })
    linhas.sort(key=lambda x: x["lucro_liquido_centavos"], reverse=True)
    return {
        "periodo": {"inicio": ini, "fim": fim},
        "redes": linhas,
        "custo_producao_centavos": custo_producao,
        "aviso": "Lucro líquido = receita líquida atribuída menos investimento em mídia. "
                 "Não inclui custo de produção, que é apresentado separadamente.",
    }


def serie_diaria(empresa_id, periodo, hoje=None):
    """Séries diárias por rede, com zeros nos dias sem registro, para os gráficos."""
    ini, fim = intervalo(periodo, hoje)
    dias = []
    d = date.fromisoformat(ini)
    while d.isoformat() <= fim:
        dias.append(d.isoformat())
        d += timedelta(days=1)
    indice = {dia: i for i, dia in enumerate(dias)}

    def serie_vazia():
        return {k: [0] * len(dias) for k in
                ["visualizacoes", "alcance", "interacoes", "seguidores", "vendas", "receita_centavos"]}

    plataformas = {}
    with conectar() as con:
        for r in con.execute(
            """SELECT m.data, c.plataforma,
                      SUM(m.visualizacoes) AS visualizacoes, SUM(m.alcance) AS alcance,
                      SUM(m.curtidas+m.comentarios+m.compartilhamentos+m.salvamentos) AS interacoes,
                      SUM(m.seguidores) AS seguidores
               FROM metrica_diaria m JOIN conta_rede c ON c.id = m.conta_id
               WHERE c.empresa_id = ? AND m.data BETWEEN ? AND ?
               GROUP BY m.data, c.plataforma""",
            (empresa_id, ini, fim)):
            s = plataformas.setdefault(r["plataforma"], serie_vazia())
            i = indice[r["data"]]
            s["visualizacoes"][i] = r["visualizacoes"] or 0
            s["alcance"][i] = r["alcance"] or 0
            s["interacoes"][i] = r["interacoes"] or 0
            s["seguidores"][i] = r["seguidores"] or 0

        for r in con.execute(
            """SELECT data, plataforma_origem AS plataforma, COUNT(*) AS qtd,
                      SUM(valor_liquido_centavos) AS receita
               FROM venda WHERE empresa_id = ? AND data BETWEEN ? AND ?
               GROUP BY data, plataforma_origem""",
            (empresa_id, ini, fim)):
            s = plataformas.setdefault(r["plataforma"], serie_vazia())
            i = indice[r["data"]]
            s["vendas"][i] = r["qtd"]
            s["receita_centavos"][i] = r["receita"] or 0

    totais = {}
    for p, s in plataformas.items():
        totais[p] = {
            "visualizacoes": sum(s["visualizacoes"]),
            "alcance": sum(s["alcance"]),
            "interacoes": sum(s["interacoes"]),
            "seguidores_atual": s["seguidores"][-1] if any(s["seguidores"]) else 0,
            "vendas": sum(s["vendas"]),
            "receita_centavos": sum(s["receita_centavos"]),
        }
    return {"periodo": {"inicio": ini, "fim": fim}, "dias": dias,
            "series": plataformas, "totais": totais}


def gerar_recomendacoes(empresa_id, hoje=None):
    """Regras transparentes. Cada recomendação traz justificativa e nível de confiança."""
    ini, fim = intervalo("mes", hoje)
    resumo = resumo_por_rede(empresa_id, "mes", hoje)
    recs = []
    redes = [r for r in resumo["redes"] if r["clientes"] > 0 and r["investido_centavos"] > 0]

    with conectar() as con:
        dias_historico = con.execute(
            "SELECT COUNT(DISTINCT data) AS d FROM metrica_diaria m JOIN conta_rede c ON c.id = m.conta_id WHERE c.empresa_id = ?",
            (empresa_id,),
        ).fetchone()["d"]

    if dias_historico < MIN_AMOSTRA_RECOMENDACAO:
        return [{
            "tipo": "sistema",
            "texto": "Ainda não há histórico suficiente para recomendações.",
            "justificativa": f"São necessários pelo menos {MIN_AMOSTRA_RECOMENDACAO} dias de métricas. Hoje há {dias_historico}.",
            "confianca": "não aplicável",
        }]

    if len(redes) >= 2:
        melhor = min(redes, key=lambda r: r["custo_por_cliente_centavos"])
        pior = max(redes, key=lambda r: r["custo_por_cliente_centavos"])
        if pior["custo_por_cliente_centavos"] > melhor["custo_por_cliente_centavos"] * 1.5:
            amostra = pior["clientes"] + melhor["clientes"]
            confianca = "alta" if amostra >= 30 else "média" if amostra >= 10 else "baixa"
            recs.append({
                "tipo": "orcamento",
                "texto": f"Avalie reduzir o investimento em {pior['plataforma']} e realocar parte para {melhor['plataforma']}.",
                "justificativa": (f"No mês, {pior['plataforma']} custou R$ {pior['custo_por_cliente_centavos']/100:.2f} por cliente; "
                                  f"{melhor['plataforma']} custou R$ {melhor['custo_por_cliente_centavos']/100:.2f}. "
                                  f"Amostra de {amostra} clientes."),
                "confianca": confianca,
            })

    for r in resumo["redes"]:
        if r["investido_centavos"] > 0 and r["lucro_liquido_centavos"] < 0:
            recs.append({
                "tipo": "alerta",
                "texto": f"Campanha em {r['plataforma']} está com prejuízo no período. Considere pausar ou revisar.",
                "justificativa": (f"Receita líquida atribuída de R$ {r['receita_liquida_centavos']/100:.2f} "
                                  f"contra investimento de R$ {r['investido_centavos']/100:.2f}."),
                "confianca": "média" if r["vendas_qtd"] >= 5 else "baixa",
            })

    if not recs:
        recs.append({
            "tipo": "info",
            "texto": "Nenhum ponto de atenção identificado no período.",
            "justificativa": "Nenhuma rede apresentou prejuízo nem custo por cliente fora do padrão.",
            "confianca": "média",
        })
    return recs
