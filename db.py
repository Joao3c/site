"""Camada de banco de dados (SQLite, biblioteca padrão)."""
import sqlite3
import os

DB_PATH = os.environ.get(
    "PLATAFORMA_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "plataforma.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS empresa (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    cnpj TEXT,
    moeda TEXT NOT NULL DEFAULT 'BRL'
);
CREATE TABLE IF NOT EXISTS usuario (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id),
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    papel TEXT NOT NULL CHECK (papel IN ('administrador','operador','leitor'))
);
CREATE TABLE IF NOT EXISTS sessao (
    token TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    expira_em REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS conta_rede (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id),
    plataforma TEXT NOT NULL CHECK (plataforma IN ('instagram','tiktok','youtube','facebook','pinterest','linkedin','x','kwai')),
    nome_conta TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'manual' CHECK (status IN ('manual','conectada','expirada'))
);
CREATE TABLE IF NOT EXISTS metrica_diaria (
    id INTEGER PRIMARY KEY,
    conta_id INTEGER NOT NULL REFERENCES conta_rede(id),
    data TEXT NOT NULL,
    alcance INTEGER NOT NULL DEFAULT 0,
    visualizacoes INTEGER NOT NULL DEFAULT 0,
    curtidas INTEGER NOT NULL DEFAULT 0,
    comentarios INTEGER NOT NULL DEFAULT 0,
    compartilhamentos INTEGER NOT NULL DEFAULT 0,
    salvamentos INTEGER NOT NULL DEFAULT 0,
    seguidores INTEGER NOT NULL DEFAULT 0,
    UNIQUE (conta_id, data)
);
CREATE TABLE IF NOT EXISTS gasto_midia (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id),
    plataforma TEXT NOT NULL,
    data TEXT NOT NULL,
    valor_centavos INTEGER NOT NULL,
    descricao TEXT
);
CREATE TABLE IF NOT EXISTS venda (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id),
    id_externo_financeiro TEXT,
    data TEXT NOT NULL,
    valor_bruto_centavos INTEGER NOT NULL,
    valor_liquido_centavos INTEGER NOT NULL,
    plataforma_origem TEXT,
    cliente_id TEXT,
    utm_source TEXT,
    cupom TEXT,
    UNIQUE (empresa_id, id_externo_financeiro)
);
CREATE TABLE IF NOT EXISTS financeiro_resumo (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id),
    periodo TEXT NOT NULL,
    faturamento_bruto_centavos INTEGER NOT NULL,
    faturamento_liquido_centavos INTEGER NOT NULL,
    custos_operacionais_centavos INTEGER NOT NULL,
    impostos_centavos INTEGER NOT NULL,
    despesas_centavos INTEGER NOT NULL,
    orcamento_marketing_centavos INTEGER NOT NULL,
    UNIQUE (empresa_id, periodo)
);
CREATE TABLE IF NOT EXISTS recomendacao (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id),
    tipo TEXT NOT NULL,
    texto TEXT NOT NULL,
    justificativa TEXT NOT NULL,
    confianca TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','aprovada','rejeitada')),
    decidida_por INTEGER REFERENCES usuario(id),
    criada_em REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS log_auditoria (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id),
    usuario_id INTEGER,
    acao TEXT NOT NULL,
    entidade TEXT,
    detalhe TEXT,
    criado_em REAL NOT NULL
);
"""


def conectar():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def inicializar():
    with conectar() as con:
        con.executescript(SCHEMA)
