# Plataforma de Redes Sociais e Vendas — MVP

Primeira versão funcional do escopo definido na fase 1 do roadmap. Usa apenas a biblioteca padrão do Python (3.10+) e SQLite, sem dependências externas.

## Como rodar

```bash
cd app

# 1. Criar banco com dados de DEMONSTRAÇÃO fictícios (opcional)
python3 seed.py

# 2. Definir o token de serviço para a integração com o financeiro
export PLATAFORMA_TOKEN_FINANCEIRO="troque-por-um-token-longo-e-aleatorio"

# 3. Iniciar o servidor
python3 servidor.py          # abre em http://127.0.0.1:8000
```

Logins de demonstração (criados pelo `seed.py`):

| Papel | E-mail | Senha |
|---|---|---|
| Administrador | admin@demo.local | trocar-esta-senha-123 |
| Leitor | leitor@demo.local | leitura-demo-123 |

**Troque essas senhas antes de qualquer uso fora da máquina local.**

## Testes

Com o servidor rodando na porta 8000:

```bash
PLATAFORMA_TOKEN_FINANCEIRO="mesmo-token" python3 teste_fumaca.py
```

## O que o MVP faz

- **Login** com senha em PBKDF2-SHA256 (200 mil iterações), sessão com expiração de 8 horas e cookie `HttpOnly`.
- **Permissões:** administrador e operador registram dados; leitor apenas consulta.
- **Painel** com visão por dia, semana, mês e ano, KPIs e ranking de redes por lucro líquido atribuído.
- **Registro manual** de investimento em mídia, vendas (com origem por rede), métricas diárias e contas.
- **Recomendações** com regras explícitas, justificativa e nível de confiança. Exigem aprovação ou rejeição do administrador. Não há alteração automática de orçamento.
- **Integração com o financeiro** por `PUT /api/integracao/financeiro/resumo`, autenticada por token de serviço. Recebe faturamento, custos, impostos e orçamento de marketing.
- **Auditoria** de todas as ações de escrita.
- **Cabeçalhos de segurança:** Content-Security-Policy, X-Frame-Options e X-Content-Type-Options.

## Limitações conhecidas (deliberadas no MVP)

- **Sem conexão OAuth com as redes.** As métricas entram por registro manual ou importação. A conexão real exige credenciais de desenvolvedor e aprovação das plataformas (ver `04-viabilidade-integracoes.md`).
- **Sem IA generativa.** As recomendações são regras transparentes. Previsões e geração de conteúdo ficam para as fases 2 e 3.
- **Atribuição simples:** cada venda carrega uma única plataforma de origem. Não há modelo de atribuição configurável.
- **Ranking só inclui redes com conta cadastrada.** Vendas de uma rede sem conta cadastrada não aparecem no ranking.
- **Lucro real estimado:** assume que o faturamento líquido já desconta impostos. Confirmar com o financeiro.
- **Token de integração compartilhado.** Adequado para teste. Em produção, usar OAuth 2.0 ou mTLS.
- **SQLite e servidor HTTP da biblioteca padrão** servem para uso local e piloto. Para produção: PostgreSQL, servidor WSGI/ASGI atrás de proxy com HTTPS e backup automatizado.
- **Sem HTTPS local.** O servidor escuta apenas em 127.0.0.1. Em produção, colocar atrás de proxy com TLS.
- **Sem proteção contra força bruta no login.** Adicionar limite de tentativas antes de expor na internet.

## Estrutura

```
app/
├── servidor.py        # servidor HTTP, rotas da API e integração
├── db.py              # esquema SQLite
├── seguranca.py       # login, sessões, permissões, auditoria
├── analise.py         # cálculos por rede e regras de recomendação
├── seed.py            # dados de demonstração (fictícios)
├── teste_fumaca.py    # testes automatizados básicos
└── web/
    ├── index.html     # painel
    ├── app.js         # lógica do painel
    └── estilo.css
```

## Próximos passos para produção

1. Migrar para PostgreSQL e adicionar migrações versionadas.
2. Implementar conectores OAuth para Instagram e TikTok, após aprovação das permissões.
3. Adicionar limite de tentativas de login e recuperação de senha.
4. Implementar exportação de relatórios e calendário de publicações (fase 2).
5. Revisar o checklist de LGPD (`../06-checklist-lgpd-seguranca.md`) e preencher o RIPD antes de receber dados reais de clientes.
