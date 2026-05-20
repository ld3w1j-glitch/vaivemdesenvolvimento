from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app import db
from app.models import Mercado, Produto, Usuario, Entregador, Pedido, PedidoItem, ChatMensagem, TaxaEntrega, ConfiguracaoSite
from app.utils import salvar_upload, obter_taxas_padrao

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.before_request
def proteger_admin():
    if not current_user.is_authenticated or current_user.tipo != "admin":
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for("auth.login"))

def cor_padrao(valor, padrao):
    valor = (valor or "").strip()
    return valor if valor else padrao

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

def obter_configuracao():
    config = ConfiguracaoSite.query.first()

    if not config:
        config = ConfiguracaoSite()
        db.session.add(config)
        db.session.commit()

    return config

def obter_taxas_entrega_configuradas():
    taxas = TaxaEntrega.query.filter_by(ativo=True).order_by(TaxaEntrega.peso_min.asc()).all()

    if taxas:
        return taxas

    taxas_padrao = []

    for faixa in obter_taxas_padrao():
        taxa = TaxaEntrega(
            peso_min=faixa["peso_min"],
            peso_max=faixa["peso_max"],
            valor=faixa["valor"],
            descricao=faixa["descricao"],
            ativo=True
        )
        taxas_padrao.append(taxa)

    return taxas_padrao

@admin_bp.route("/")
@login_required
def dashboard():
    clientes = Usuario.query.filter_by(tipo="cliente").order_by(Usuario.id.desc()).all()
    entregadores_lista = Entregador.query.all()
    pedidos_recentes = Pedido.query.order_by(Pedido.id.desc()).limit(5).all()
    faturamento_total = sum((p.valor_total or 0) for p in Pedido.query.all())

    return render_template(
        "admin/dashboard.html",
        mercados=Mercado.query.count(),
        produtos=Produto.query.count(),
        entregadores=Entregador.query.count(),
        pedidos=Pedido.query.count(),
        pedidos_recentes=pedidos_recentes,
        faturamento_total=faturamento_total,
        clientes_count=len(clientes),
        clientes=clientes,
        entregadores_lista=entregadores_lista
    )

@admin_bp.route("/modo-teste/cliente")
@login_required
def modo_teste_cliente():
    session["admin_modo_teste"] = "cliente"
    flash("Modo teste cliente ativado. Você continua logado como admin.", "success")
    return redirect(url_for("cliente.dashboard"))

@admin_bp.route("/modo-teste/entregador")
@login_required
def modo_teste_entregador():
    session["admin_modo_teste"] = "entregador"
    flash("Modo teste entregador ativado. Você continua logado como admin.", "success")
    return redirect(url_for("entregador.dashboard"))

@admin_bp.route("/modo-teste/sair")
@login_required
def sair_modo_teste():
    session.pop("admin_modo_teste", None)
    flash("Modo teste encerrado.", "info")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/clientes")
@login_required
def clientes():
    clientes = Usuario.query.filter_by(tipo="cliente").order_by(Usuario.id.desc()).all()
    return render_template("admin/clientes.html", clientes=clientes)

@admin_bp.route("/usuarios/<int:usuario_id>/alterar-senha", methods=["POST"])
@login_required
def alterar_senha_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)

    nova_senha = request.form.get("nova_senha", "")
    confirmar_senha = request.form.get("confirmar_senha", "")
    senha_admin = request.form.get("admin_password", "")

    if usuario.tipo == "admin":
        flash("Por segurança, a senha de outro administrador não pode ser alterada por esta tela.", "danger")
        return redirect(url_for("admin.clientes"))

    if not senha_admin:
        flash("Informe a senha do administrador para alterar a senha do usuário.", "danger")
        return redirect(url_for("admin.clientes"))

    if not current_user.check_senha(senha_admin):
        flash("Senha do administrador incorreta. A senha do usuário não foi alterada.", "danger")
        return redirect(url_for("admin.clientes"))

    if nova_senha != confirmar_senha:
        flash("A nova senha e a confirmação não conferem.", "danger")
        return redirect(url_for("admin.clientes"))

    erros_senha = senha_eh_segura(nova_senha)
    if erros_senha:
        flash("A nova senha precisa " + ", ".join(erros_senha) + ".", "danger")
        return redirect(url_for("admin.clientes"))

    if usuario.check_senha(nova_senha):
        flash("A nova senha não pode ser igual à senha atual do usuário.", "danger")
        return redirect(url_for("admin.clientes"))

    usuario.set_senha(nova_senha)
    db.session.commit()

    flash(f"Senha do usuário {usuario.nome} alterada com sucesso.", "success")
    return redirect(url_for("admin.clientes"))

@admin_bp.route("/clientes/<int:cliente_id>/excluir", methods=["POST"])
@login_required
def excluir_cliente(cliente_id):
    cliente = Usuario.query.get_or_404(cliente_id)
    senha_admin = request.form.get("admin_password", "")

    if cliente.tipo != "cliente":
        flash("Este usuário não é um cliente e não pode ser excluído por esta tela.", "danger")
        return redirect(url_for("admin.clientes"))

    if cliente.id == current_user.id:
        flash("Você não pode excluir o próprio usuário admin por esta tela.", "danger")
        return redirect(url_for("admin.clientes"))

    if not senha_admin:
        flash("Para excluir um cliente, informe a senha do administrador.", "danger")
        return redirect(url_for("admin.clientes"))

    if not current_user.check_senha(senha_admin):
        flash("Senha do administrador incorreta. Cliente não excluído.", "danger")
        return redirect(url_for("admin.clientes"))

    pedidos_cliente = Pedido.query.filter_by(cliente_id=cliente.id).count()

    if pedidos_cliente > 0:
        flash("Este cliente possui pedidos vinculados. Para preservar o histórico, ele não foi excluído.", "danger")
        return redirect(url_for("admin.clientes"))

    try:
        db.session.delete(cliente)
        db.session.commit()
        flash("Cliente excluído com sucesso.", "success")
    except Exception:
        db.session.rollback()
        flash("Não foi possível excluir este cliente porque ele pode estar vinculado a outros registros.", "danger")

    return redirect(url_for("admin.clientes"))

@admin_bp.route("/configuracoes", methods=["GET", "POST"])
@login_required
def configuracoes():
    config = obter_configuracao()

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "salvar_taxas_entrega":
            pesos_min = request.form.getlist("peso_min[]")
            pesos_max = request.form.getlist("peso_max[]")
            valores = request.form.getlist("valor[]")
            descricoes = request.form.getlist("descricao[]")

            try:
                TaxaEntrega.query.delete()

                for i in range(len(valores)):
                    peso_min_raw = pesos_min[i].strip() if i < len(pesos_min) else ""
                    peso_max_raw = pesos_max[i].strip() if i < len(pesos_max) else ""
                    valor_raw = valores[i].strip() if i < len(valores) else ""
                    descricao = descricoes[i].strip() if i < len(descricoes) else ""

                    if not valor_raw:
                        continue

                    db.session.add(TaxaEntrega(
                        peso_min=float(peso_min_raw or 0),
                        peso_max=float(peso_max_raw) if peso_max_raw else None,
                        valor=float(valor_raw or 0),
                        descricao=descricao,
                        ativo=True
                    ))

                db.session.commit()
                flash("Taxas de entrega atualizadas com sucesso.", "success")
            except Exception as erro:
                db.session.rollback()
                flash(f"Não foi possível salvar as taxas. Verifique os valores. Erro: {erro}", "danger")

            return redirect(url_for("admin.configuracoes"))

        if acao == "salvar_site":
            config.nome_site = request.form.get("nome_site", "VaiVem Mercado")
            config.slogan = request.form.get("slogan", "")
            config.bairro_regiao = request.form.get("bairro_regiao", "")
            config.telefone_suporte = request.form.get("telefone_suporte", "")
            config.email_suporte = request.form.get("email_suporte", "")

            config.cor_principal = request.form.get("cor_principal", "#1f8a4c")
            config.cor_secundaria = request.form.get("cor_secundaria", "#e8f5ec")

            config.comparacao_precos_ativa = True if request.form.get("comparacao_precos_ativa") == "on" else False

            config.tipo_mapa = request.form.get("tipo_mapa", "openstreetmap")
            config.google_maps_api_key = request.form.get("google_maps_api_key", "")

            config.pix_chave = request.form.get("pix_chave", "")
            config.pix_nome_recebedor = request.form.get("pix_nome_recebedor", "")
            config.pix_cidade_recebedor = request.form.get("pix_cidade_recebedor", "")

            config.mensagem_padrao_cliente = request.form.get("mensagem_padrao_cliente", "")
            config.mensagem_padrao_entregador = request.form.get("mensagem_padrao_entregador", "")

            if request.form.get("remover_logo_site") == "on":
                config.logo_site = None

            if request.form.get("remover_icone_site") == "on":
                config.icone_site = None

            nova_logo = salvar_upload(request.files.get("logo_site"))
            novo_icone = salvar_upload(request.files.get("icone_site"))

            if nova_logo:
                config.logo_site = nova_logo

            if novo_icone:
                config.icone_site = novo_icone

            db.session.commit()
            flash("Configurações do site salvas com sucesso.", "success")
            return redirect(url_for("admin.configuracoes"))

    taxas_entrega = obter_taxas_entrega_configuradas()
    return render_template("admin/configuracoes.html", config=config, taxas_entrega=taxas_entrega)

@admin_bp.route("/mercados")
@login_required
def mercados():
    return render_template("admin/mercados.html", mercados=Mercado.query.all())

@admin_bp.route("/mercados/novo", methods=["GET", "POST"])
@login_required
def novo_mercado():
    if request.method == "POST":
        mercado = Mercado(
            nome=request.form.get("nome"),
            endereco=request.form.get("endereco"),
            latitude=float(request.form.get("latitude") or -22.228),
            longitude=float(request.form.get("longitude") or -45.936),
            telefone=request.form.get("telefone"),
            horario=request.form.get("horario"),
            logo=salvar_upload(request.files.get("logo")),
            foto_perfil=salvar_upload(request.files.get("foto_perfil")),
            foto_apresentacao=salvar_upload(request.files.get("foto_apresentacao")),
            cor_primaria=cor_padrao(request.form.get("cor_primaria"), "#1f8a4c"),
            cor_secundaria=cor_padrao(request.form.get("cor_secundaria"), "#e8f5ec"),
            cor_ponteiro=cor_padrao(request.form.get("cor_ponteiro"), "#1f8a4c"),
            ativo=True
        )

        db.session.add(mercado)
        db.session.commit()

        flash("Mercado criado.", "success")
        return redirect(url_for("admin.mercados"))

    return render_template("admin/mercado_form.html")

@admin_bp.route("/mercados/<int:mercado_id>/editar", methods=["GET", "POST"])
@login_required
def editar_mercado(mercado_id):
    mercado = Mercado.query.get_or_404(mercado_id)

    if request.method == "POST":
        mercado.nome = request.form.get("nome")
        mercado.endereco = request.form.get("endereco")
        mercado.latitude = float(request.form.get("latitude") or mercado.latitude or -22.228)
        mercado.longitude = float(request.form.get("longitude") or mercado.longitude or -45.936)
        mercado.telefone = request.form.get("telefone")
        mercado.horario = request.form.get("horario")
        mercado.ativo = True if request.form.get("ativo") == "on" else False
        mercado.cor_primaria = cor_padrao(request.form.get("cor_primaria"), "#1f8a4c")
        mercado.cor_secundaria = cor_padrao(request.form.get("cor_secundaria"), "#e8f5ec")
        mercado.cor_ponteiro = cor_padrao(request.form.get("cor_ponteiro"), "#1f8a4c")

        nova_logo = salvar_upload(request.files.get("logo"))
        nova_foto_perfil = salvar_upload(request.files.get("foto_perfil"))
        nova_foto_apresentacao = salvar_upload(request.files.get("foto_apresentacao"))

        if nova_logo:
            mercado.logo = nova_logo

        if nova_foto_perfil:
            mercado.foto_perfil = nova_foto_perfil

        if nova_foto_apresentacao:
            mercado.foto_apresentacao = nova_foto_apresentacao

        db.session.commit()

        flash("Mercado atualizado com sucesso.", "success")
        return redirect(url_for("admin.mercados"))

    return render_template("admin/mercado_editar.html", mercado=mercado)

@admin_bp.route("/mercados/<int:mercado_id>/produtos", methods=["GET", "POST"])
@login_required
def produtos_mercado(mercado_id):
    mercado = Mercado.query.get_or_404(mercado_id)

    if request.method == "POST":
        produto = Produto(
            mercado_id=mercado.id,
            codigo=request.form.get("codigo"),
            descricao=request.form.get("descricao"),
            valor=float(request.form.get("valor") or 0),
            peso_kg=float(request.form.get("peso_kg") or 0),
            categoria=request.form.get("categoria"),
            estoque=int(request.form.get("estoque") or 0),
            foto=salvar_upload(request.files.get("foto"))
        )

        db.session.add(produto)
        db.session.commit()

        flash("Produto adicionado.", "success")
        return redirect(url_for("admin.produtos_mercado", mercado_id=mercado.id))

    return render_template("admin/produtos.html", mercado=mercado, produtos=mercado.produtos)

@admin_bp.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
@login_required
def editar_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    mercado = produto.mercado

    if request.method == "POST":
        produto.codigo = request.form.get("codigo")
        produto.descricao = request.form.get("descricao")
        produto.valor = float(request.form.get("valor") or 0)
        produto.peso_kg = float(request.form.get("peso_kg") or 0)
        produto.categoria = request.form.get("categoria")
        produto.estoque = int(request.form.get("estoque") or 0)

        nova_foto = salvar_upload(request.files.get("foto"))
        if nova_foto:
            produto.foto = nova_foto

        db.session.commit()

        flash("Produto atualizado com sucesso.", "success")
        return redirect(url_for("admin.produtos_mercado", mercado_id=mercado.id))

    return render_template("admin/produto_editar.html", produto=produto, mercado=mercado)

@admin_bp.route("/produtos/<int:produto_id>/excluir", methods=["POST"])
@login_required
def excluir_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    mercado_id = produto.mercado_id
    senha_admin = request.form.get("admin_password", "")

    if not senha_admin:
        flash("Para excluir, informe a senha do administrador.", "danger")
        return redirect(url_for("admin.produtos_mercado", mercado_id=mercado_id))

    if not current_user.check_senha(senha_admin):
        flash("Senha do administrador incorreta. Produto não excluído.", "danger")
        return redirect(url_for("admin.produtos_mercado", mercado_id=mercado_id))

    try:
        db.session.delete(produto)
        db.session.commit()
        flash("Produto excluído com sucesso.", "success")
    except Exception:
        db.session.rollback()
        flash("Não foi possível excluir este produto porque ele pode estar vinculado a algum pedido.", "danger")

    return redirect(url_for("admin.produtos_mercado", mercado_id=mercado_id))

@admin_bp.route("/entregadores", methods=["GET", "POST"])
@login_required
def entregadores():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()

        if not usuario:
            usuario = Usuario(
                nome=request.form.get("nome"),
                email=email,
                tipo="entregador",
                telefone=request.form.get("telefone"),
                foto=salvar_upload(request.files.get("foto"))
            )
            usuario.set_senha(request.form.get("senha") or "123456")
            db.session.add(usuario)
            db.session.flush()
        else:
            usuario.tipo = "entregador"

        entregador = Entregador(
            usuario_id=usuario.id,
            veiculo=request.form.get("veiculo"),
            capacidade_kg=float(request.form.get("capacidade_kg") or 20)
        )

        db.session.add(entregador)
        db.session.commit()

        flash("Entregador criado.", "success")
        return redirect(url_for("admin.entregadores"))

    return render_template("admin/entregadores.html", entregadores=Entregador.query.all())

@admin_bp.route("/pedidos")
@login_required
def pedidos():
    return render_template("admin/pedidos.html", pedidos=Pedido.query.order_by(Pedido.id.desc()).all())

@admin_bp.route("/pedidos/<int:pedido_id>/excluir", methods=["POST"])
@login_required
def excluir_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    senha_admin = request.form.get("admin_password", "")

    if not senha_admin:
        flash("Informe a senha do administrador para excluir o pedido.", "danger")
        return redirect(url_for("admin.pedidos"))

    if not current_user.check_senha(senha_admin):
        flash("Senha do administrador incorreta. Pedido não excluído.", "danger")
        return redirect(url_for("admin.pedidos"))

    try:
        ChatMensagem.query.filter_by(pedido_id=pedido.id).delete()
        PedidoItem.query.filter_by(pedido_id=pedido.id).delete()
        db.session.delete(pedido)
        db.session.commit()
        flash(f"Pedido #{pedido_id} excluído com sucesso.", "success")
    except Exception:
        db.session.rollback()
        flash("Não foi possível excluir este pedido.", "danger")

    return redirect(url_for("admin.pedidos"))

@admin_bp.route("/pedidos/limpar", methods=["POST"])
@login_required
def limpar_pedidos():
    senha_admin = request.form.get("admin_password", "")

    if not senha_admin:
        flash("Informe a senha do administrador para limpar os pedidos.", "danger")
        return redirect(url_for("admin.pedidos"))

    if not current_user.check_senha(senha_admin):
        flash("Senha do administrador incorreta. Histórico de pedidos não foi limpo.", "danger")
        return redirect(url_for("admin.pedidos"))

    try:
        ChatMensagem.query.delete()
        PedidoItem.query.delete()
        Pedido.query.delete()
        db.session.commit()
        flash("Histórico de pedidos limpo com sucesso.", "success")
    except Exception:
        db.session.rollback()
        flash("Não foi possível limpar o histórico de pedidos.", "danger")

    return redirect(url_for("admin.pedidos"))
