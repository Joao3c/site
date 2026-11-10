"""Cria uma empresa de DEMONSTRAÇÃO com dados fictícios. Não usar em produção."""
import random
from datetime import date, timedelta
import db
import seguranca as seg

random.seed(42)


def main():
    db.inicializar()
    with db.conectar() as con:
        if con.execute("SELECT 1 FROM empresa").fetchone():
            print("Banco já possui dados. Nada foi alterado.")
            return
        cur = con.execute("INSERT INTO empresa (nome, cnpj) VALUES (?,?)",
                          ("Empresa Demonstração (fictícia)", "00.000.000/0001-00"))
        emp = cur.lastrowid
        seg.criar_usuario(con, emp, "admin@demo.local", "trocar-esta-senha-123", "administrador")
        seg.criar_usuario(con, emp, "leitor@demo.local", "leitura-demo-123", "leitor")

        contas = {}
        for plat, nome in [("instagram", "@demo_loja"), ("tiktok", "@demo_loja_tv")]:
            contas[plat] = con.execute(
                "INSERT INTO conta_rede (empresa_id, plataforma, nome_conta) VALUES (?,?,?)",
                (emp, plat, nome)).lastrowid

        hoje = date.today()
        perfil = {"instagram": (900, 0.04, 40), "tiktok": (1400, 0.07, 55)}
        for dia in range(60):
            d = (hoje - timedelta(days=dia)).isoformat()
            for plat, cid in contas.items():
                alc, tx, seg_ = perfil[plat]
                alcance = int(alc * random.uniform(0.7, 1.4))
                con.execute(
                    """INSERT INTO metrica_diaria (conta_id, data, alcance, visualizacoes, curtidas,
                       comentarios, compartilhamentos, salvamentos, seguidores)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (cid, d, alcance, int(alcance * 1.3), int(alcance * tx),
                     int(alcance * tx * 0.1), int(alcance * tx * 0.15), int(alcance * tx * 0.2),
                     seg_ * (60 - dia) // 10 + 500))

        for dia in range(60):
            d = (hoje - timedelta(days=dia)).isoformat()
            con.execute("INSERT INTO gasto_midia (empresa_id, plataforma, data, valor_centavos, descricao) VALUES (?,?,?,?,?)",
                        (emp, "instagram", d, 6000 + random.randint(-500, 500), "Impulsionamento (fictício)"))
            con.execute("INSERT INTO gasto_midia (empresa_id, plataforma, data, valor_centavos, descricao) VALUES (?,?,?,?,?)",
                        (emp, "tiktok", d, 3000 + random.randint(-300, 300), "Anúncios (fictício)"))
            if dia % 7 == 0:
                con.execute("INSERT INTO gasto_midia (empresa_id, plataforma, data, valor_centavos, descricao) VALUES (?,?,?,?,?)",
                            (emp, "producao", d, 25000, "Produção semanal de vídeos (fictício)"))

        for i in range(180):
            d = (hoje - timedelta(days=random.randint(0, 59))).isoformat()
            plat = random.choices(["instagram", "tiktok", "producao"], weights=[45, 40, 0])[0]
            bruto = random.randint(8000, 26000)
            liquido = int(bruto * 0.84)
            con.execute(
                """INSERT INTO venda (empresa_id, id_externo_financeiro, data, valor_bruto_centavos,
                   valor_liquido_centavos, plataforma_origem, cliente_id, utm_source, cupom)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (emp, f"DEMO-{i:04d}", d, bruto, liquido, plat, f"cli-{random.randint(1,120):03d}",
                 plat, None))

        con.execute(
            """INSERT INTO financeiro_resumo (empresa_id, periodo, faturamento_bruto_centavos,
               faturamento_liquido_centavos, custos_operacionais_centavos, impostos_centavos,
               despesas_centavos, orcamento_marketing_centavos) VALUES (?,?,?,?,?,?,?,?)""",
            (emp, hoje.strftime("%Y-%m"), 4800000, 4032000, 1900000, 720000, 500000, 300000))

        seg.auditar(con, emp, None, "seed", None, "dados de demonstração criados")
    print("Demonstração criada.")
    print("  administrador: admin@demo.local / trocar-esta-senha-123")
    print("  leitor:        leitor@demo.local / leitura-demo-123")


if __name__ == "__main__":
    main()
