from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app import db
from app.models import Mercado, Produto, Pedido, PedidoItem, Usuario
from app.utils import calcular_taxa_entrega, gerar_codigo_confirmacao, gerar_qrcode_pedido, obter_pix_copia_cola_pedido, salvar_upload

try:
    from app.utils import comparacao_precos_ativa
except Exception:
    def comparacao_precos_ativa():
        return True

cliente_bp = Blueprint("cliente", __name__, url_prefix="/cliente")

def cliente_required():
    return (
        current_user.is_authenticated and
        (
            current_user.tipo == "cliente" or
            (current_user.tipo == "admin" and session.get("admin_modo_teste") == "cliente")
        )
    )

@cliente_bp.before_request
def proteger_cliente():
    if not cliente_required():
        flash("Acesso restrito ao cliente.", "danger")
        return redirect(url_for("auth.login"))

def senha_eh_segura(senha):
    erros = []

    if len(senha or "") < 8:
        erros.append("ter pelo menos 8 caracteres")

    if not any(c.isupper() for c in senha):
        erros.append("ter pelo menos uma letra maiúscula")

    if not any(c.islower() for c in senha):
        erros.append("ter pelo menos uma letra minúscula")

    if not any(c.isdigit() for c in senha):
        erros.append("ter pelo menos um número")

    especiais = "!@#$%¨&*()-_=+[]{};:,.<>?/\\|"
    if not any(c in especiais for c in senha):
        erros.append("ter pelo menos um caractere especial, como @, #, ! ou *")

    return erros

def somente_numeros(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())

def montar_endereco_do_form():
    cep = request.form.get("cep", "").strip()
    rua = request.form.get("rua", "").strip()
    numero = request.form.get("numero", "").strip()
    bairro = request.form.get("bairro", "").strip()
    cidade = request.form.get("cidade", "").strip()
    estado = request.form.get("estado", "").strip()
    complemento = request.form.get("complemento", "").strip()
    endereco_manual = request.form.get("endereco_manual", "").strip()

    partes = []

    if rua:
        partes.append(rua)

    if numero:
        partes.append(f"Nº {numero}")

    if bairro:
        partes.append(bairro)

    if cidade or estado:
        partes.append(f"{cidade} - {estado}".strip(" -"))

    if cep:
        partes.append(f"CEP: {cep}")

    if complemento:
        partes.append(f"Complemento: {complemento}")

    if partes:
        return ", ".join(partes)

    return endereco_manual

@cliente_bp.route("/")
@login_required
def dashboard():
    cliente_visual = current_user

    if current_user.tipo == "admin":
        cliente_visual = Usuario.query.filter_by(tipo="cliente").order_by(Usuario.id.asc()).first() or current_user

    pedidos = Pedido.query.filter_by(cliente_id=cliente_visual.id).order_by(Pedido.id.desc()).all()
    mercados = Mercado.query.filter_by(ativo=True).all()

    return render_template(
        "cliente/dashboard.html",
        pedidos=pedidos,
        mercados=mercados,
        cliente_visual=cliente_visual,
        admin_modo_teste=(current_user.tipo == "admin")
    )

@cliente_bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    if current_user.tipo == "admin":
        flash("Perfil de cliente em modo teste. Para editar perfil, use uma conta de cliente real.", "info")
        return redirect(url_for("cliente.dashboard"))

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "dados_perfil":
            nome = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip().lower()
            telefone = request.form.get("telefone", "").strip()
            endereco = montar_endereco_do_form()

            if not nome:
                flash("O nome é obrigatório.", "danger")
                return redirect(url_for("cliente.perfil"))

            if not email:
                flash("O email é obrigatório.", "danger")
                return redirect(url_for("cliente.perfil"))

            email_existente = Usuario.query.filter(Usuario.email == email, Usuario.id != current_user.id).first()
            if email_existente:
                flash("Este email já está sendo usado por outro usuário.", "danger")
                return redirect(url_for("cliente.perfil"))

            telefone_numeros = somente_numeros(telefone)
            if telefone_numeros:
                usuarios = Usuario.query.filter(Usuario.id != current_user.id).all()
                for u in usuarios:
                    if somente_numeros(u.telefone) == telefone_numeros:
                        flash("Este telefone já está sendo usado por outro usuário.", "danger")
                        return redirect(url_for("cliente.perfil"))

            nova_foto = salvar_upload(request.files.get("foto"))
            if nova_foto:
                current_user.foto = nova_foto

            current_user.nome = nome
            current_user.email = email
            current_user.telefone = telefone
            current_user.endereco = endereco

            db.session.commit()

            flash("Perfil atualizado com sucesso.", "success")
            return redirect(url_for("cliente.perfil"))

        if acao == "alterar_senha":
            senha_atual = request.form.get("senha_atual", "")
            nova_senha = request.form.get("nova_senha", "")
            confirmar_senha = request.form.get("confirmar_senha", "")

            if not current_user.check_senha(senha_atual):
                flash("Senha atual incorreta.", "danger")
                return redirect(url_for("cliente.perfil"))

            if nova_senha != confirmar_senha:
                flash("A nova senha e a confirmação não conferem.", "danger")
                return redirect(url_for("cliente.perfil"))

            erros_senha = senha_eh_segura(nova_senha)
            if erros_senha:
                flash("A nova senha precisa " + ", ".join(erros_senha) + ".", "danger")
                return redirect(url_for("cliente.perfil"))

            if current_user.check_senha(nova_senha):
                flash("A nova senha não pode ser igual à senha atual.", "danger")
                return redirect(url_for("cliente.perfil"))

            current_user.set_senha(nova_senha)
            db.session.commit()

            flash("Senha alterada com sucesso.", "success")
            return redirect(url_for("cliente.perfil"))

    return render_template("cliente/perfil.html")

@cliente_bp.route("/mercados")
@login_required
def mercados():
    mercados = Mercado.query.filter_by(ativo=True).all()
    return render_template("cliente/mercados.html", mercados=mercados)

@cliente_bp.route("/mercado/<int:mercado_id>")
@login_required
def mercado_catalogo(mercado_id):
    mercado = Mercado.query.get_or_404(mercado_id)
    categoria_ativa = request.args.get("categoria", "").strip()

    categorias_produtos = [
        {
            "nome": "Padaria",
            "slug": "Padaria",
            "descricao": "Pães, bolos e lanches",
            "imagem": "pao.png",
            "icone": "bread",
        },
        {
            "nome": "Carnes",
            "slug": "Carnes",
            "descricao": "Cortes frescos e açougue",
            "imagem": "carne.png",
            "icone": "meat",
        },
        {
            "nome": "Hortifruti",
            "slug": "Hortifruti",
            "descricao": "Frutas, legumes e verduras",
            "imagem": "tomate.png",
            "icone": "leaf",
        },
        {
            "nome": "Entrega",
            "slug": "Entrega",
            "descricao": "Acompanhe e receba seu pedido",
            "imagem": "capacete.png",
            "icone": "delivery",
        },
        {
            "nome": "Promoções",
            "slug": "Promoções",
            "descricao": "Ofertas e descontos especiais",
            "imagem": "dinheiro-50.png",
            "icone": "percent",
        },
        {
            "nome": "Economia",
            "slug": "Economia",
            "descricao": "Preços baixos e vantagens",
            "imagem": "dinheiro-100.png",
            "icone": "wallet",
        },
    ]

    consulta = Produto.query.filter_by(mercado_id=mercado_id)

    if categoria_ativa:
        consulta = consulta.filter(Produto.categoria.ilike(f"%{categoria_ativa}%"))

    produtos = consulta.order_by(Produto.descricao.asc()).all()
    carrinho = session.get("carrinho", {})

    return render_template(
        "cliente/catalogo.html",
        mercado=mercado,
        produtos=produtos,
        carrinho=carrinho,
        categorias_produtos=categorias_produtos,
        categoria_ativa=categoria_ativa
    )

@cliente_bp.route("/carrinho/add/<int:produto_id>", methods=["POST"])
@login_required
def carrinho_add(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    quantidade = int(request.form.get("quantidade") or 1)
    carrinho = session.get("carrinho", {})
    carrinho[str(produto_id)] = carrinho.get(str(produto_id), 0) + quantidade
    session["carrinho"] = carrinho

    flash("Produto adicionado ao carrinho.", "success")
    return redirect(url_for("cliente.mercado_catalogo", mercado_id=produto.mercado_id))

@cliente_bp.route("/carrinho")
@login_required
def carrinho():
    carrinho = session.get("carrinho", {})
    itens = []
    peso_total = 0
    valor_produtos = 0
    comparacoes = []

    for produto_id, qtd in carrinho.items():
        produto = Produto.query.get(int(produto_id))

        if produto:
            subtotal = produto.valor * qtd
            peso = produto.peso_kg * qtd
            valor_produtos += subtotal
            peso_total += peso

            itens.append({
                "produto": produto,
                "qtd": qtd,
                "subtotal": subtotal,
                "peso": peso
            })

            if comparacao_precos_ativa():
                mais_baratos = Produto.query.filter(
                    Produto.codigo == produto.codigo,
                    Produto.mercado_id != produto.mercado_id,
                    Produto.valor < produto.valor
                ).all()

                for alt in mais_baratos:
                    comparacoes.append({
                        "atual": produto,
                        "alternativo": alt
                    })

    taxa = calcular_taxa_entrega(peso_total)
    total = valor_produtos + taxa

    return render_template(
        "cliente/carrinho.html",
        itens=itens,
        peso_total=peso_total,
        valor_produtos=valor_produtos,
        taxa=taxa,
        total=total,
        comparacoes=comparacoes
    )

@cliente_bp.route("/pedido/finalizar", methods=["POST"])
@login_required
def finalizar_pedido():
    if current_user.tipo == "admin":
        flash("Modo teste: o admin não finaliza pedido real como cliente.", "warning")
        return redirect(url_for("cliente.dashboard"))

    carrinho = session.get("carrinho", {})

    if not carrinho:
        flash("Carrinho vazio.", "warning")
        return redirect(url_for("cliente.dashboard"))

    endereco = request.form.get("endereco_entrega") or current_user.endereco or "Endereço não informado"
    itens_calc = []
    peso_total = 0
    valor_produtos = 0
    mercado_id = None

    for produto_id, qtd in carrinho.items():
        produto = Produto.query.get(int(produto_id))

        if produto:
            mercado_id = produto.mercado_id
            subtotal = produto.valor * qtd
            peso_total += produto.peso_kg * qtd
            valor_produtos += subtotal
            itens_calc.append((produto, qtd, subtotal))

    taxa = calcular_taxa_entrega(peso_total)
    total = valor_produtos + taxa

    pedido = Pedido(
        cliente_id=current_user.id,
        mercado_id=mercado_id,
        endereco_entrega=endereco,
        peso_total=peso_total,
        valor_produtos=valor_produtos,
        taxa_entrega=taxa,
        valor_total=total,
        codigo_confirmacao=gerar_codigo_confirmacao(),
        status="aguardando_entregador"
    )

    db.session.add(pedido)
    db.session.flush()

    for produto, qtd, subtotal in itens_calc:
        item = PedidoItem(
            pedido_id=pedido.id,
            produto_id=produto.id,
            codigo_produto=produto.codigo,
            descricao=produto.descricao,
            quantidade=qtd,
            valor_unitario=produto.valor,
            peso_unitario=produto.peso_kg,
            subtotal=subtotal
        )

        db.session.add(item)

    pedido.qr_code = gerar_qrcode_pedido(pedido.id, pedido.valor_total)
    db.session.commit()

    session["carrinho"] = {}

    flash("Pedido criado. QR Code Pix gerado e pedido liberado para entregadores.", "success")
    return redirect(url_for("cliente.pedido", pedido_id=pedido.id))

@cliente_bp.route("/pedido/<int:pedido_id>")
@login_required
def pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    if current_user.tipo != "admin" and pedido.cliente_id != current_user.id:
        flash("Pedido não pertence a você.", "danger")
        return redirect(url_for("cliente.dashboard"))

    pix_copia_cola = obter_pix_copia_cola_pedido(pedido)

    return render_template("cliente/pedido.html", pedido=pedido, pix_copia_cola=pix_copia_cola)
