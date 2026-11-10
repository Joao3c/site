"""Teste de fumaça: verifica autenticação, permissões, validação e integração.

Uso (com o servidor rodando na porta 8765, banco de demonstração e token configurados):
    PLATAFORMA_TOKEN_FINANCEIRO=... python3 teste_fumaca.py
"""
import http.client
import json
import os
import sys

HOST, PORTA = "127.0.0.1", int(os.environ.get("PORTA", "8765"))
TOKEN = os.environ.get("PLATAFORMA_TOKEN_FINANCEIRO", "")
falhas = []


def req(metodo, caminho, corpo=None, cookie=None, cabecalhos=None):
    conn = http.client.HTTPConnection(HOST, PORTA, timeout=5)
    h = {"Content-Type": "application/json", **(cabecalhos or {})}
    if cookie:
        h["Cookie"] = cookie
    conn.request(metodo, caminho, body=json.dumps(corpo) if corpo is not None else None, headers=h)
    r = conn.getresponse()
    dados = r.read()
    cookie_novo = r.getheader("Set-Cookie")
    conn.close()
    try:
        j = json.loads(dados)
    except ValueError:
        j = None
    return r.status, j, cookie_novo, r.getheaders()


def verifica(nome, condicao):
    print(("OK   " if condicao else "FALHA") + " " + nome)
    if not condicao:
        falhas.append(nome)


st, _, _, _ = req("GET", "/api/resumo")
verifica("rota protegida sem login retorna 401", st == 401)

st, _, cookie_adm, _ = req("POST", "/api/login", {"email": "admin@demo.local", "senha": "trocar-esta-senha-123"})
verifica("login do administrador", st == 200 and cookie_adm is not None)
cookie_adm = cookie_adm.split(";")[0]

st, _, _, _ = req("POST", "/api/login", {"email": "admin@demo.local", "senha": "errada"})
verifica("senha incorreta é rejeitada", st == 401)

st, j, _, _ = req("GET", "/api/resumo?periodo=mes", cookie=cookie_adm)
verifica("resumo por rede responde com redes", st == 200 and "redes" in j)

st, _, cookie_leit, _ = req("POST", "/api/login", {"email": "leitor@demo.local", "senha": "leitura-demo-123"})
cookie_leit = cookie_leit.split(";")[0]
st, _, _, _ = req("POST", "/api/gasto", {"plataforma": "tiktok", "data": "2026-11-09", "valor": 10}, cookie=cookie_leit)
verifica("leitor não consegue registrar gasto", st == 403)

st, _, _, _ = req("POST", "/api/gasto", {"plataforma": "tiktok", "data": "2026-11-09", "valor": -5}, cookie=cookie_adm)
verifica("valor negativo é rejeitado", st == 400)

st, _, _, _ = req("POST", "/api/gasto", {"plataforma": "x; DROP", "data": "2026-11-09", "valor": 5}, cookie=cookie_adm)
verifica("plataforma fora da lista é rejeitada", st == 400)

st, _, _, _ = req("PUT", "/api/integracao/financeiro/resumo", {}, cabecalhos={})
verifica("integração financeira sem token é rejeitada", st == 401)

if TOKEN:
    st, _, _, _ = req("PUT", "/api/integracao/financeiro/resumo",
                      {"empresa_id": 1, "periodo": "2026-09", "faturamento_bruto": 1000,
                       "faturamento_liquido": 800, "custos_operacionais": 300, "impostos": 100,
                       "despesas": 100, "orcamento_marketing": 50},
                      cabecalhos={"Authorization": f"Bearer {TOKEN}"})
    verifica("integração financeira com token grava resumo", st == 200)
else:
    print("PULA integração com token (PLATAFORMA_TOKEN_FINANCEIRO não definido)")

st, _, _, cabs = req("GET", "/")
nomes = {k.lower(): v for k, v in cabs}
verifica("cabeçalho Content-Security-Policy presente", "content-security-policy" in nomes)
verifica("cabeçalho X-Frame-Options presente", "x-frame-options" in nomes)

print()
if falhas:
    print(f"{len(falhas)} falha(s).")
    sys.exit(1)
print("Todos os testes passaram.")
