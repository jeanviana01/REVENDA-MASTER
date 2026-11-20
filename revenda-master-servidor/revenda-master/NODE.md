# Revenda Master · Node.js

O site usa HTML, CSS e JavaScript no navegador e Node.js 24 com SQLite no servidor. Preserva a interface original e importa o catálogo de exemplo com 17 veículos e 17 fotos na primeira inicialização de um banco novo.

## Executar

Na raiz da aplicação, copie .env.node.example para .env e defina uma senha inicial de pelo menos 12 caracteres. Execute:

```sh
npm start
```

Abra http://localhost:4173/. O painel fica em http://localhost:4173/admin. Configure WHATSAPP_NUMBER somente se houver um contato público autorizado para a loja.

## Hospedar

Use um serviço compatível com Node.js 24 e com volume persistente. No repositório, a raiz da aplicação é revenda-master-servidor/revenda-master. Use npm start e /api/health como rota de verificação. Configure NODE_ENV=production, DATA_DIR apontando para o volume e ADMIN_PASSWORD como segredo. Use uma única instância e mantenha HTTPS no proxy da hospedagem. PORT pode ser definido pelo provedor.

O servidor aceita o banco SQLite da versão anterior por DATABASE_PATH e as fotos por UPLOAD_DIR. Trabalhe com uma cópia consistente do banco e da pasta de fotos ao migrar. Os usuários existentes mantêm seus hashes de senha. Faça backup periódico do diretório de dados.

O GitHub Pages é uma vitrine do catálogo de exemplo. As alterações administrativas são feitas na aplicação Node.js hospedada.
