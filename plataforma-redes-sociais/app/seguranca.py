"""Autenticação, sessões, permissões e auditoria."""
import hashlib
import hmac
import secrets
import time
from db import conectar

SESSAO_HORAS = 8
ITERACOES = 200_000
PAPEIS_ESCRITA = {"administrador", "operador"}


def gerar_hash(senha: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), ITERACOES).hex()


def criar_usuario(con, empresa_id, email, senha, papel):
    salt = secrets.token_hex(16)
    con.execute(
        "INSERT INTO usuario (empresa_id, email, senha_hash, salt, papel) VALUES (?,?,?,?,?)",
        (empresa_id, email.lower(), gerar_hash(senha, salt), salt, papel),
    )


def login(email, senha):
    with conectar() as con:
        u = con.execute("SELECT * FROM usuario WHERE email = ?", (email.lower(),)).fetchone()
        if not u or not hmac.compare_digest(u["senha_hash"], gerar_hash(senha, u["salt"])):
            return None
        token = secrets.token_urlsafe(32)
        con.execute(
            "INSERT INTO sessao (token, usuario_id, expira_em) VALUES (?,?,?)",
            (token, u["id"], time.time() + SESSAO_HORAS * 3600),
        )
        return token


def usuario_da_sessao(token):
    if not token:
        return None
    with conectar() as con:
        row = con.execute(
            """SELECT u.* FROM sessao s JOIN usuario u ON u.id = s.usuario_id
               WHERE s.token = ? AND s.expira_em > ?""",
            (token, time.time()),
        ).fetchone()
        return dict(row) if row else None


def logout(token):
    with conectar() as con:
        con.execute("DELETE FROM sessao WHERE token = ?", (token,))


def pode_escrever(usuario):
    return usuario and usuario["papel"] in PAPEIS_ESCRITA


def auditar(con, empresa_id, usuario_id, acao, entidade=None, detalhe=None):
    con.execute(
        "INSERT INTO log_auditoria (empresa_id, usuario_id, acao, entidade, detalhe, criado_em) VALUES (?,?,?,?,?,?)",
        (empresa_id, usuario_id, acao, entidade, detalhe, time.time()),
    )
