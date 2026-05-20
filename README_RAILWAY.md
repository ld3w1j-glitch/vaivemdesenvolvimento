# VaiVem Mercado — pronto para Railway

Este pacote já está preparado para subir no Railway.

## Arquivos adicionados

- `Procfile` — comando de inicialização com Gunicorn.
- `railway.json` — configuração de build/deploy do Railway.
- `runtime.txt` — fixa Python 3.11.9.
- `requirements.txt` — inclui Flask, Gunicorn e suporte a PostgreSQL.
- `.env.example` — exemplo das variáveis necessárias.

## Como subir

1. Envie esta pasta para um repositório no GitHub.
2. No Railway, clique em **New Project**.
3. Escolha **Deploy from GitHub repo**.
4. Selecione o repositório deste projeto.
5. Em **Variables**, adicione:

```env
FLASK_ENV=production
SECRET_KEY=coloque-uma-chave-grande-e-segura-aqui
```

6. Clique em **Deploy**.

## Banco de dados

Por padrão, o projeto usa SQLite em `instance/vaivem.db`.

Para teste simples no Railway, isso pode subir normalmente. Para uso real, recomendo adicionar PostgreSQL no Railway:

1. No projeto Railway, clique em **New**.
2. Escolha **Database > PostgreSQL**.
3. O Railway cria a variável `DATABASE_URL` automaticamente.
4. Faça redeploy da aplicação.

O código já aceita `DATABASE_URL` e corrige automaticamente URLs começando com `postgres://` para `postgresql://`.

## Login admin inicial

```text
Email: admin@vaivem.com
Senha: admin123
```

## Observações importantes

- Uploads feitos pelo usuário dentro do Railway podem sumir em redeploy se você não configurar volume/persistência externa.
- Para produção real, o ideal é usar PostgreSQL e depois configurar armazenamento externo para imagens.
