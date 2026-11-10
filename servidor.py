"""Servidor HTTP (biblioteca padrão). Serve a API e o frontend estático."""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import db
import seguranca as seg
import analise

BASE = os.path.dirname(os.path.abspath(__file__))
ESTATICO = os.path.join(BASE, "web")
TOKEN_FINANCEIRO = os.environ.get("PLATAFORMA_TOKEN_FINANCEIRO", "")
PLATAFORMAS = {"instagram", "tiktok", "youtube", "facebook", "pinterest", "linkedin", "x", "kwai", "producao"}


class Handler(BaseHTTPRequestHandler):
    server_version = "PlataformaRS/0.1"

    # ---------- utilitários ----------
    def _json(self, status, corpo):
        dados = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def _corpo(self):
        tam = int(self.headers.get("Content-Length", 0) or 0)
        if tam > 1_000_000:
            raise ValueError("corpo grande demais")
        return json.loads(self.rfile.read(tam) or b"{}")

    def _usuario(self):
        cookie = self.headers.get("Cookie", "")
        m = re.search(r"sid=([A-Za-z0-9_\-]+)", cookie)
        return seg.usuario_da_sessao(m.group(1) if m else None), (m.group(1) if m else None)

    def _exigir(self, escrita=False):
        u, token = self._usuario()
        if not u:
            self._json(401, {"erro": "não autenticado"})
            return None
        if escrita and not seg.pode_escrever(u):
            self._json(403, {"erro": "sem permissão para esta ação"})
            return None
        return u

    def log_message(self, fmt, *args):
        pass  # evita registrar IPs e dados nos logs padrão

    # ---------- roteamento ----------
    def do_GET(self):
        p = urlparse(self.path)
        if not p.path.startswith("/api/"):
            return self._estatico(p.path)
        u = self._exigir()
        if not u:
            return
        q = parse_qs(p.query)
        periodo = q.get("periodo", ["semana"])[0]
        if p.path == "/api/eu":
            return self._json(200, {"email": u["email"], "papel": u["papel"]})
        if p.path == "/api/resumo":
            return self._json(200, analise.resumo_por_rede(u["empresa_id"], periodo))
        if p.path == "/api/recomendacoes":
            with db.conectar() as con:
                pendentes = [dict(r) for r in con.execute(
                    "SELECT * FROM recomendacao WHERE empresa_id=? ORDER BY criada_em DESC LIMIT 50",
                    (u["empresa_id"],))]
            return self._json(200, {"gerar_novas": analise.gerar_recomendacoes(u["empresa_id"]), "historico": pendentes})
        if p.path == "/api/serie":
            return self._json(200, analise.serie_diaria(u["empresa_id"], periodo))
        if p.path == "/api/contas":
            with db.conectar() as con:
                rows = [dict(r) for r in con.execute(
                    "SELECT id, plataforma, nome_conta FROM conta_rede WHERE empresa_id=? ORDER BY plataforma",
                    (u["empresa_id"],))]
            return self._json(200, rows)
        if p.path == "/api/financeiro":
            with db.conectar() as con:
                rows = [dict(r) for r in con.execute(
                    "SELECT * FROM financeiro_resumo WHERE empresa_id=? ORDER BY periodo DESC LIMIT 24",
                    (u["empresa_id"],))]
            return self._json(200, rows)
        if p.path == "/api/auditoria":
            with db.conectar() as con:
                rows = [dict(r) for r in con.execute(
                    "SELECT * FROM log_auditoria WHERE empresa_id=? ORDER BY criado_em DESC LIMIT 200",
                    (u["empresa_id"],))]
            return self._json(200, rows)
        return self._json(404, {"erro": "rota não encontrada"})

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/login":
            try:
                c = self._corpo()
            except ValueError:
                return self._json(400, {"erro": "requisição inválida"})
            token = seg.login(str(c.get("email", "")), str(c.get("senha", "")))
            if not token:
                return self._json(401, {"erro": "e-mail ou senha incorretos"})
            self.send_response(200)
            self.send_header("Set-Cookie", f"sid={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={seg.SESSAO_HORAS*3600}")
            body = b'{"ok": true}'
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p.path == "/api/logout":
            _, token = self._usuario()
            if token:
                seg.logout(token)
            return self._json(200, {"ok": True})

        u = self._exigir(escrita=True)
        if not u:
            return
        try:
            c = self._corpo()
        except ValueError:
            return self._json(400, {"erro": "requisição inválida"})

        if p.path == "/api/gasto":
            plat = str(c.get("plataforma", ""))
            if plat not in PLATAFORMAS:
                return self._json(400, {"erro": "plataforma inválida"})
            try:
                valor = int(round(float(c["valor"]) * 100))
            except (KeyError, ValueError, TypeError):
                return self._json(400, {"erro": "valor inválido"})
            if valor <= 0:
                return self._json(400, {"erro": "o valor deve ser positivo"})
            data = str(c.get("data", ""))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
                return self._json(400, {"erro": "data deve estar no formato AAAA-MM-DD"})
            with db.conectar() as con:
                con.execute(
                    "INSERT INTO gasto_midia (empresa_id, plataforma, data, valor_centavos, descricao) VALUES (?,?,?,?,?)",
                    (u["empresa_id"], plat, data, valor, str(c.get("descricao", ""))[:200]))
                seg.auditar(con, u["empresa_id"], u["id"], "registrar_gasto", plat, f"{valor} centavos em {data}")
            return self._json(201, {"ok": True})

        if p.path == "/api/venda":
            try:
                bruto = int(round(float(c["valor_bruto"]) * 100))
                liquido = int(round(float(c.get("valor_liquido", c["valor_bruto"])) * 100))
            except (KeyError, ValueError, TypeError):
                return self._json(400, {"erro": "valores inválidos"})
            plat = str(c.get("plataforma_origem", ""))
            if plat not in PLATAFORMAS:
                return self._json(400, {"erro": "plataforma de origem inválida"})
            data = str(c.get("data", ""))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
                return self._json(400, {"erro": "data inválida"})
            with db.conectar() as con:
                con.execute(
                    """INSERT INTO venda (empresa_id, id_externo_financeiro, data, valor_bruto_centavos,
                       valor_liquido_centavos, plataforma_origem, cliente_id, utm_source, cupom)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (u["empresa_id"], c.get("id_externo") or None, data, bruto, liquido, plat,
                     str(c.get("cliente_id", ""))[:64] or None, str(c.get("utm_source", ""))[:64] or None,
                     str(c.get("cupom", ""))[:64] or None))
                seg.auditar(con, u["empresa_id"], u["id"], "registrar_venda", plat, f"{bruto} centavos")
            return self._json(201, {"ok": True})

        if p.path == "/api/metricas":
            try:
                conta_id = int(c["conta_id"])
                data = str(c["data"])
                campos = ["alcance", "visualizacoes", "curtidas", "comentarios",
                          "compartilhamentos", "salvamentos", "seguidores"]
                valores = [max(0, int(c.get(k, 0))) for k in campos]
            except (KeyError, ValueError, TypeError):
                return self._json(400, {"erro": "dados de métricas inválidos"})
            with db.conectar() as con:
                conta = con.execute("SELECT id FROM conta_rede WHERE id=? AND empresa_id=?",
                                    (conta_id, u["empresa_id"])).fetchone()
                if not conta:
                    return self._json(404, {"erro": "conta não encontrada"})
                con.execute(
                    f"""INSERT INTO metrica_diaria (conta_id, data, {', '.join(campos)})
                        VALUES (?, ?, {', '.join('?' for _ in campos)})
                        ON CONFLICT(conta_id, data) DO UPDATE SET
                        {', '.join(f'{k}=excluded.{k}' for k in campos)}""",
                    (conta_id, data, *valores))
                seg.auditar(con, u["empresa_id"], u["id"], "importar_metricas", str(conta_id), data)
            return self._json(201, {"ok": True})

        if p.path == "/api/conta":
            plat = str(c.get("plataforma", ""))
            if plat not in PLATAFORMAS - {"producao"}:
                return self._json(400, {"erro": "plataforma inválida"})
            nome = str(c.get("nome_conta", "")).strip()[:100]
            if not nome:
                return self._json(400, {"erro": "informe o nome da conta"})
            with db.conectar() as con:
                cur = con.execute("INSERT INTO conta_rede (empresa_id, plataforma, nome_conta) VALUES (?,?,?)",
                                  (u["empresa_id"], plat, nome))
                seg.auditar(con, u["empresa_id"], u["id"], "cadastrar_conta", plat, nome)
            return self._json(201, {"id": cur.lastrowid})

        if p.path.startswith("/api/recomendacao/"):
            m = re.fullmatch(r"/api/recomendacao/(\d+)", p.path)
            if not m:
                return self._json(404, {"erro": "rota não encontrada"})
            decisao = str(c.get("decisao", ""))
            if decisao not in ("aprovada", "rejeitada"):
                return self._json(400, {"erro": "decisão inválida"})
            with db.conectar() as con:
                cur = con.execute(
                    "UPDATE recomendacao SET status=?, decidida_por=? WHERE id=? AND empresa_id=? AND status='pendente'",
                    (decisao, u["id"], int(m.group(1)), u["empresa_id"]))
                if cur.rowcount == 0:
                    return self._json(404, {"erro": "recomendação não encontrada ou já decidida"})
                seg.auditar(con, u["empresa_id"], u["id"], f"recomendacao_{decisao}", m.group(1))
            return self._json(200, {"ok": True})

        return self._json(404, {"erro": "rota não encontrada"})

    # ---------- integração com o financeiro (API de entrada) ----------
    def do_PUT(self):
        p = urlparse(self.path)
        if p.path != "/api/integracao/financeiro/resumo":
            return self._json(404, {"erro": "rota não encontrada"})
        # Autenticação de serviço por token compartilhado (em produção: OAuth 2.0 ou mTLS)
        autorizacao = self.headers.get("Authorization", "")
        if not TOKEN_FINANCEIRO or autorizacao != f"Bearer {TOKEN_FINANCEIRO}":
            return self._json(401, {"erro": "token de serviço inválido"})
        try:
            c = self._corpo()
            empresa_id = int(c["empresa_id"])
            periodo = str(c["periodo"])
            campos = {k: int(round(float(c[k]) * 100)) for k in
                      ["faturamento_bruto", "faturamento_liquido", "custos_operacionais",
                       "impostos", "despesas", "orcamento_marketing"]}
        except (KeyError, ValueError, TypeError):
            return self._json(400, {"erro": "payload inválido"})
        if not re.fullmatch(r"\d{4}-\d{2}", periodo):
            return self._json(400, {"erro": "período deve estar no formato AAAA-MM"})
        with db.conectar() as con:
            con.execute(
                """INSERT INTO financeiro_resumo (empresa_id, periodo, faturamento_bruto_centavos,
                   faturamento_liquido_centavos, custos_operacionais_centavos, impostos_centavos,
                   despesas_centavos, orcamento_marketing_centavos)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(empresa_id, periodo) DO UPDATE SET
                   faturamento_bruto_centavos=excluded.faturamento_bruto_centavos,
                   faturamento_liquido_centavos=excluded.faturamento_liquido_centavos,
                   custos_operacionais_centavos=excluded.custos_operacionais_centavos,
                   impostos_centavos=excluded.impostos_centavos,
                   despesas_centavos=excluded.despesas_centavos,
                   orcamento_marketing_centavos=excluded.orcamento_marketing_centavos""",
                (empresa_id, periodo, campos["faturamento_bruto"], campos["faturamento_liquido"],
                 campos["custos_operacionais"], campos["impostos"], campos["despesas"],
                 campos["orcamento_marketing"]))
            seg.auditar(con, empresa_id, None, "integracao_financeiro", periodo, "resumo recebido")
        return self._json(200, {"ok": True})

    # ---------- arquivos estáticos ----------
    def _estatico(self, caminho):
        if caminho in ("/", ""):
            caminho = "/index.html"
        alvo = os.path.realpath(os.path.join(ESTATICO, caminho.lstrip("/")))
        if not alvo.startswith(os.path.realpath(ESTATICO) + os.sep) or not os.path.isfile(alvo):
            self.send_response(404)
            self.end_headers()
            return
        tipos = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8"}
        tipo = tipos.get(os.path.splitext(alvo)[1], "application/octet-stream")
        with open(alvo, "rb") as f:
            dados = f.read()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(dados)


def main(porta=8000):
    db.inicializar()
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    print(f"Plataforma em http://127.0.0.1:{porta}")
    srv.serve_forever()


if __name__ == "__main__":
    main(int(os.environ.get("PORTA", "8000")))
