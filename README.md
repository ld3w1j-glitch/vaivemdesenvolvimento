# VaiVem Mercado — Flask Corrigido

Versão corrigida sem `Pillow` e sem `qrcode`, para evitar erro no Python 3.14 no Windows.

## Como rodar

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Acesse:

```text
http://127.0.0.1:5000
```

## Admin inicial

```text
Email: admin@vaivem.com
Senha: admin123
```

## O que tem nesta versão

- Login e cadastro
- Área admin
- Área cliente
- Área entregador
- Admin cria mercados
- Admin cria produtos
- Admin cria entregadores
- Cliente vê mercados no mapa
- Cliente adiciona produtos ao carrinho
- Cálculo de peso
- Cálculo de taxa de entrega
- Comparação de preços pelo código do produto
- Pedido com QR Code visual simulado em SVG
- Código de confirmação de entrega
- Entregador aceita pedido
- Chat com anexo
- Finalização por código

## Observação

O QR Code desta versão é visual/simulado. Para PIX real, depois será necessário integrar uma API de pagamento.
