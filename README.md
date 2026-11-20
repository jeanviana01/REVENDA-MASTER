# Revenda Master

[Catálogo no GitHub Pages](https://jeanviana01.github.io/REVENDA-MASTER/) · [Aplicação completa em Node.js](revenda-master-servidor/revenda-master/NODE.md)

As instruções abaixo descrevem a versão original em Flask, preservada para referência.

Site de uma revenda de carros: catálogo público com busca e página de cada veículo, e uma **área de administrador protegida por login** para
cadastrar, editar e remover veículos, fotos e descrições. Os dados ficam em um banco SQLite no servidor e as fotos em uma pasta do servidor.

> Projeto de demonstração. Antes de usar com clientes reais, leia **Cuidados de segurança** e **Pendências** (final do arquivo e `docs/`).

## 1. O que o site faz

- **Página inicial** (`/`): logo com efeito de luz, vídeo, botões **Fabricantes** e **Buscar**, contato com WhatsApp e mapa.
  - **Fabricantes:** clicar na marca lista os carros dela; clicar de novo fecha a lista.
  - **Buscar:** fabricante, modelo, ano, cor e transmissão. Dá para usar qualquer combinação (basta um filtro). Se nada combinar, aparece
    "Que pena que não temos disponível no momento." com o botão **Gostaria de encomendar?** (abre o WhatsApp já com o pedido).
- **Página do veículo** (`/veiculo?id=…`): foto principal, ano, cor, câmbio, descrição, blocos de detalhes, galeria e botão de WhatsApp.
- **Administrador** (`/admin`): login e senha; cadastro, edição e remoção de veículos; envio, troca de foto principal e remoção de fotos;
  alteração de senha. Não há link público para essa página.

## 2. Tecnologias

Python 3.10+ · Flask 3 · SQLite (módulo `sqlite3`) · Pillow (validação/recompressão de imagens) · python-dotenv ·
front-end em HTML, CSS e JavaScript puros (sem etapa de build) · testes com `unittest` e Playwright (E2E).

> Observação: o servidor foi feito em Flask (e não FastAPI) porque Flask estava disponível no ambiente em que o projeto foi construído e testado.

## 3. Estrutura de pastas

```
revenda-master/
├── README.md                    este arquivo
├── requirements.txt             dependências de execução
├── requirements-dev.txt         + Playwright, só para testes E2E
├── .env.example                 modelo das variáveis de ambiente (sem valores reais)
├── .gitignore                   protege .env, banco, fotos e logs
├── backend/
│   ├── run.py                   servidor de DESENVOLVIMENTO
│   ├── wsgi.py                  ponto de entrada para PRODUÇÃO (gunicorn/waitress)
│   ├── app/
│   │   ├── __init__.py          fábrica da aplicação (create_app), cabeçalhos, CORS, verificação de origem
│   │   ├── config.py            lê o ambiente; recusa SECRET_KEY fraca em produção
│   │   ├── db.py                conexão SQLite e migrações
│   │   ├── security.py          hash de senha (scrypt), limitador de tentativas, CSRF, cabeçalhos
│   │   ├── errors.py            erros da API e tratamento centralizado (sem vazar detalhes)
│   │   ├── logging_setup.py     logs em console e arquivo rotativo
│   │   ├── models/              consultas ao banco (user.py, vehicle.py)
│   │   ├── services/            regras: auth_service, vehicle_service, upload_service
│   │   └── routes/              rotas: public (catálogo), auth (login), admin (CRUD), pages (HTML/arquivos), guards (proteções)
│   ├── migrations/001_init.sql  esquema do banco
│   ├── scripts/                 create_admin.py · seed_catalog.py · audit_static.py
│   ├── seed/                    catálogo inicial (vehicles.json + fotos)
│   └── tests/                   unit/ · integration/ · e2e/ · perf/
├── frontend/
│   ├── index.html · veiculo.html · admin.html
│   └── assets/  css/ (site, veiculo, admin) · js/ (rm, home, veiculo, admin, video) · img/ · video/
└── docs/                        RELATORIO_QA.md · RELATORIO_SEGURANCA.md
```

## 4. Como funciona

**Front-end.** Cada página carrega `assets/js/rm.js` (auxiliares + cliente da API + cartão de veículo) e o script da própria página.
Todo texto vindo do servidor é inserido com `textContent` (nunca `innerHTML`), o que impede XSS. Não há JavaScript nem estilo inline,
então o servidor pode usar uma CSP rígida (`script-src 'self'`). Falhas de rede mostram mensagem e botão "Tentar de novo".

**Back-end.** API JSON em `/api`:

| Rota | Quem acessa | Função |
|---|---|---|
| `GET /api/health` | todos | verifica servidor e banco |
| `GET /api/meta` | todos | marcas, modelos, anos, cores, transmissões, WhatsApp, endereço |
| `GET /api/vehicles?brand=&model=&year=&color=&transmission=&q=` | todos | lista/filtra veículos |
| `GET /api/vehicles/<id>` | todos | detalhes e fotos |
| `POST /api/auth/login` · `GET /api/auth/me` | todos | entrar / ver sessão |
| `POST /api/auth/logout` · `POST /api/auth/password` | admin (+CSRF) | sair / trocar senha |
| `POST/PUT/DELETE /api/admin/vehicles[/<id>]` | admin (+CSRF) | cadastrar, editar, remover |
| `POST /api/admin/vehicles/<id>/photos` · `DELETE /api/admin/photos/<id>` · `POST /api/admin/photos/<id>/main` | admin (+CSRF) | fotos |

**Comunicação.** O navegador chama a API na mesma origem. O login cria uma sessão (cookie `HttpOnly`, `SameSite=Strict`, `Secure` em produção).
Toda escrita exige o cabeçalho `X-CSRF-Token` (entregue no login). As fotos enviadas são validadas e **regravadas** pelo servidor com nome aleatório
e ficam em `UPLOAD_DIR`, servidas em `/uploads/<nome>`.

## 5. Instalação e execução local

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # Windows: copy .env.example .env   (edite o .env)
python backend/scripts/seed_catalog.py      # carrega os 17 veículos de exemplo com fotos
python backend/scripts/create_admin.py      # pergunta usuário e senha (mín. 10 caracteres, letras e números)
python backend/run.py                       # http://127.0.0.1:5000   |   admin: http://127.0.0.1:5000/admin
```

O banco é criado sozinho na primeira execução (`instance/development.sqlite3`). Nenhuma senha vem pronta: **você escolhe a do administrador**.

## 6. Configuração (variáveis de ambiente)

Veja o `.env.example` (todas comentadas). As principais: `APP_ENV` (`development`/`test`/`production`), `SECRET_KEY` (obrigatória em produção,
32+ caracteres; gere com `python -c "import secrets; print(secrets.token_hex(32))"`), `DATABASE_PATH`, `UPLOAD_DIR`, `WHATSAPP_NUMBER`,
`STORE_ADDRESS`, `SESSION_HOURS`, `MAX_UPLOAD_MB`, `LOGIN_MAX_ATTEMPTS`, `TRUST_PROXY_HOPS`, `ALLOWED_ORIGINS`, `COOKIE_SECURE`.
O `.env` fica **só no servidor** e está no `.gitignore`. Em produção a aplicação **não inicia** com `SECRET_KEY` ausente, curta ou igual ao exemplo.

**Ambientes:** *development* (padrão; chave temporária, cookie sem `Secure`, banco `instance/development.sqlite3`), *test* (usado pelos testes automatizados,
com banco e pastas temporárias) e *production* (exige chave forte, cookie `Secure`, HSTS quando a conexão é HTTPS).

## 7. Testes

```bash
python -m unittest discover -s backend/tests/unit -t .          # unitários (20)
python -m unittest discover -s backend/tests/integration -t .   # integração da API (39)
pip install -r requirements-dev.txt && python -m playwright install chromium
python -m unittest discover -s backend/tests/e2e -t .           # ponta a ponta no navegador (15)
python backend/scripts/audit_static.py                          # auditoria estática de segurança do código
python backend/tests/perf/load_test.py 300 30                   # carga: 300 requisições por rota, 30 simultâneas
```

Os resultados da última execução, o que **não** foi testado e as falhas encontradas estão em `docs/RELATORIO_QA.md` e `docs/RELATORIO_SEGURANCA.md`.

## 8. Produção

Não há etapa de build: o front-end é estático e é servido pelo próprio Flask. Para publicar:

1. Servidor Linux com Python 3.10+, `pip install -r requirements.txt` e uma pasta de dados fora do código (ex.: `/var/lib/revenda-master`).
2. `.env` com `APP_ENV=production`, `SECRET_KEY` forte, `DATABASE_PATH`, `UPLOAD_DIR`, `LOG_DIR`, `WHATSAPP_NUMBER`.
3. `python backend/scripts/seed_catalog.py` (se quiser o catálogo de exemplo) e `python backend/scripts/create_admin.py`.
4. Servidor de aplicação (não use `run.py`). Exemplo com gunicorn: `pip install gunicorn && gunicorn -w 2 -b 127.0.0.1:8000 backend.wsgi:app`.
5. Proxy reverso com **HTTPS** (nginx, Caddy etc.) na frente, repassando `X-Forwarded-For/Proto/Host`, e `TRUST_PROXY_HOPS=1` no `.env`.
6. Backup regular do arquivo do banco e da pasta de fotos.

> O passo 4 (gunicorn) e o HTTPS real **não foram testados** no ambiente de desenvolvimento deste projeto. Teste em um servidor de homologação antes.

## 9. Cuidados de segurança

- O que protege o administrador é o **servidor** (login, sessão, CSRF, permissões). Nada secreto vai para o navegador.
- Use senha longa e única; troque a de exemplo na hora. Só o hash (scrypt) é gravado.
- Mantenha `.env`, banco e `instance/` fora do Git e fora de pastas públicas do servidor web.
- Sempre use HTTPS em produção.
- O limitador de tentativas fica em memória de cada processo: com vários *workers*, o limite efetivo é multiplicado. Para limite estrito, use 1 worker ou limite também no proxy.
- Rode um scanner de dependências (ex.: `pip install pip-audit && pip-audit -r requirements.txt`) **antes de publicar** e periodicamente.

## 10. Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `ConfigError: Em produção, defina SECRET_KEY…` | Falta `SECRET_KEY` forte no `.env` (ou no ambiente do servidor). |
| Site abre mas sem carros | Rode `python backend/scripts/seed_catalog.py` (ou cadastre pelo `/admin`). |
| "Usuário ou senha incorretos" | Crie/redefina: `python backend/scripts/create_admin.py --username SEU_USUARIO --reset`. |
| 429 no login | Excesso de tentativas; aguarde (padrão 15 min) ou ajuste `LOGIN_MAX_ATTEMPTS`/`LOGIN_WINDOW_SECONDS`. |
| Upload recusado (413/415) | Foto acima de `MAX_UPLOAD_MB`, formato diferente de PNG/JPG/WebP, imagem corrompida ou enorme. |
| Login "não pega" em produção | O cookie é `Secure`: acesse por HTTPS. |
| Fontes não carregam | As fontes vêm do Google Fonts; sem internet o site usa fontes do sistema. |
| `Address already in use` | Outra coisa usa a porta: `PORT=5001 python backend/run.py`. |
| Testes E2E não rodam | `pip install -r requirements-dev.txt && python -m playwright install chromium`. |
