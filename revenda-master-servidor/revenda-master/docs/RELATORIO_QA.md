# Relatório de QA — Revenda Master

Execução em ambiente de desenvolvimento (Linux, Python 3.12, Flask 3.1.3, Pillow 13.0, Chromium via Playwright 1.63).
Todos os números abaixo vêm de execuções reais dos comandos do README.

## Resumo

| Categoria | Comando | Resultado |
|---|---|---|
| Unitários | `python -m unittest discover -s backend/tests/unit -t .` | **20 testes, todos passaram** |
| Integração (API + banco + HTTP) | `…/integration` | **39 testes, todos passaram** |
| Ponta a ponta (navegador real, servidor real) | `…/e2e` | **15 testes, todos passaram** |
| Auditoria estática de segurança | `python backend/scripts/audit_static.py` | **0 achados** (1 nota de revisão manual, ver abaixo) |
| Compilação dos módulos Python | `python -m compileall backend` | sem erros |
| Carga | `python backend/tests/perf/load_test.py 300 30` | 7 rotas × 300 requisições, 30 simultâneas: **0% de erro**, p95 entre 43 ms e 81 ms |
| Regressão | as três suítes acima, reexecutadas após cada correção | passaram na execução final |

Não há etapa de *build* (front-end estático sem bundler); o equivalente é a compilação Python e a carga das páginas no navegador, sem erros de console.

## O que foi testado

**Funcional (E2E, Chromium):** página inicial (logo, vídeo tocando, botões, links de WhatsApp e mapa); cada uma das 8 marcas lista exatamente os carros que a API
retorna, com fotos carregadas, e o segundo clique fecha a lista; busca com filtros isolados e combinados comparada com a API; fluxo "não encontrado → encomendar";
lista de modelos filtrada pela marca; página de detalhes (blocos, foto, WhatsApp, voltar); ids inválidos; login errado; ciclo completo do administrador
(cadastrar com foto, ver como visitante, editar, segunda foto, tornar principal, remover foto, remover veículo, sair); validações do formulário
(campos vazios, foto > 5 MB, arquivo que não é imagem).

**API (integração):** todos os filtros e combinações; formato dos itens; 404 e erros de parâmetros; CRUD completo; fotos (envio, ordem, principal, remoção, limite por veículo,
arquivos apagados do disco ao remover o veículo); validação de cada campo; autenticação (sucesso, falha, formatos inválidos, limite de tentativas, logout, troca de senha,
cookie adulterado, sessão antiga invalidada).

**Responsividade (E2E):** larguras 360, 390, 768, 1366 e 1920 px na página inicial (com lista aberta), na página do veículo e no admin: sem rolagem horizontal e com os
elementos principais dentro da tela.

**Falhas simuladas:**

| Cenário | Resultado |
|---|---|
| API indisponível (requisição abortada) | mensagem de erro + botão "Tentar de novo"; ao voltar, o site se recupera |
| Servidor responde 500 numa lista | mensagem de erro exibida, sem quebrar a página |
| Banco de dados corrompido/ilegível | API responde 500 genérico (sem SQL, caminhos ou *traceback*); páginas estáticas seguem no ar |
| Dados inválidos / campos obrigatórios vazios | 422 com os campos errados; no formulário, mensagem clara |
| Falha de autenticação | 401 com mensagem igual para "usuário inexistente" e "senha errada" |
| Acesso sem login / sem token CSRF / origem estranha | 401 / 403 / 403 em todas as rotas de escrita |
| Arquivos inexistentes | 404 (páginas, `/assets`, `/uploads`) |
| Fotos indisponíveis | card continua e a foto some sem ícone quebrado |
| Vídeo indisponível | página funciona normalmente com a imagem de capa |
| Requisição interrompida durante a busca | mensagem de erro com nova tentativa |
| Erro inesperado no servidor | 500 genérico com código de referência; o detalhe vai só para o log |

## Falhas encontradas e corrigidas

1. **Login respondia HTTP 500 quando o corpo JSON era uma lista** (ex.: `[1,2]`). Achada por teste de integração. Agora responde 400. Teste de regressão incluído.
2. **Painel do administrador apagava a mensagem de confirmação** ("Veículo adicionado") no mesmo instante em que a mostrava. Achada pelo teste E2E. Corrigido.
3. **Ícone flutuante de WhatsApp do site anterior era decorativo** (não clicável). Agora é um link de verdade e some se `WHATSAPP_NUMBER` não estiver configurado.
4. **Reforço:** imagens muito grandes só geravam um *aviso* no Pillow; agora são recusadas (teste com imagem de ~42 milhões de pixels).

Também houve erros nos próprios testes (esperas bloqueadas pela CSP do site, textos em maiúsculas por CSS, opção "Qualquer modelo" contada como modelo). Foram corrigidos nos testes, sem mudar o comportamento do site.

## Mudanças de comportamento em relação ao site estático anterior

- O catálogo vem do banco, via API. As opções de modelo, cor e ano da busca agora refletem o que existe no catálogo (antes havia modelos "de exemplo" sem carro cadastrado).
- Todo carro tem página de detalhes (antes só os três Volkswagen).
- O painel de administrador antigo (senha conferida no navegador e dados salvos só no navegador) foi **removido** e substituído pelo login no servidor.
  A senha daquela versão deixou de existir; no novo sistema você cria a sua com `create_admin.py`.

## O que NÃO foi testado (e por quê)

- **Outros navegadores:** só Chromium estava disponível. Firefox e Safari/WebKit **não** foram testados.
- **Celulares e tablets reais:** só viewports emulados no Chromium.
- **Servidor de produção** (gunicorn/waitress), **proxy HTTPS real** e **vários workers:** não instalados/testados. O comportamento de cookie `Secure` e HSTS foi testado
  simulando HTTPS no cliente de teste, não com certificado real.
- **Carga com banco grande, muitos uploads ou internet real:** a carga foi local, no servidor de desenvolvimento, com 17 veículos.
- **Scanner de vulnerabilidades de dependências:** sem internet neste ambiente (ver relatório de segurança).
- **Acessibilidade com leitor de tela e auditoria SEO automatizada:** há rótulos, `aria-*`, foco visível, `lang`, `description` e `noindex` no admin, mas não houve auditoria formal.
- **Perfis de usuário diferentes:** só existe o papel "administrador"; não há cenário de "usuário sem permissão" além do visitante sem login.

## Nota da auditoria estática

`backend/app/models/vehicle.py` executa uma consulta montada a partir de uma variável (`list_vehicles`). Foi revisada manualmente: só concatena texto fixo, nomes de coluna de uma
lista fechada e marcadores `?`; todos os valores vão como parâmetros. Os testes de SQL Injection (5 cargas × 5 filtros) confirmam.
