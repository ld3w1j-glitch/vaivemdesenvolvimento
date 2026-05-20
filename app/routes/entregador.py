from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from app import db
from app.models import Pedido, Entregador

entregador_bp = Blueprint("entregador", __name__, url_prefix="/entregador")

def admin_em_modo_teste_entregador():
    return (
        current_user.is_authenticated and
        current_user.tipo == "admin" and
        session.get("admin_modo_teste") == "entregador"
    )

def get_entregador():
    if not current_user.is_authenticated:
        return None

    if current_user.tipo == "entregador":
        return Entregador.query.filter_by(usuario_id=current_user.id).first()

    if admin_em_modo_teste_entregador():
        return Entregador.query.first()

    return None

@entregador_bp.before_request
def proteger_entregador():
    if not current_user.is_authenticated:
        flash("Faça login para continuar.", "danger")
        return redirect(url_for("auth.login"))

    if current_user.tipo == "admin" and session.get("admin_modo_teste") == "entregador":
        return None

    if current_user.tipo == "entregador":
        return None

    flash("Acesso restrito ao entregador.", "danger")
    return redirect(url_for("auth.login"))

@entregador_bp.route("/")
@login_required
def dashboard():
    entregador = get_entregador()
    admin_modo_teste = admin_em_modo_teste_entregador()

    disponiveis = Pedido.query.filter_by(status="aguardando_entregador").order_by(Pedido.id.desc()).all()

    if entregador:
        meus = Pedido.query.filter_by(entregador_id=entregador.id).order_by(Pedido.id.desc()).all()
    else:
        meus = []

    concluidos = [p for p in meus if p.status == "concluido"]
    valor_total = sum(p.taxa_entrega for p in concluidos)

    return render_template(
        "entregador/dashboard.html",
        entregador=entregador,
        disponiveis=disponiveis,
        meus=meus,
        concluidos=concluidos,
        valor_total=valor_total,
        admin_modo_teste=admin_modo_teste
    )

@entregador_bp.route("/pedido/<int:pedido_id>")
@login_required
def pedido(pedido_id):
    return render_template(
        "entregador/pedido.html",
        pedido=Pedido.query.get_or_404(pedido_id),
        entregador=get_entregador(),
        admin_modo_teste=admin_em_modo_teste_entregador()
    )

@entregador_bp.route("/pedido/<int:pedido_id>/aceitar", methods=["POST"])
@login_required
def aceitar(pedido_id):
    if admin_em_modo_teste_entregador():
        flash("Modo teste: o admin visualiza o fluxo, mas não aceita pedido real como entregador.", "warning")
        return redirect(url_for("entregador.pedido", pedido_id=pedido_id))

    entregador = get_entregador()
    pedido = Pedido.query.get_or_404(pedido_id)

    if not entregador:
        flash("Cadastro de entregador não encontrado para este usuário.", "danger")
        return redirect(url_for("entregador.dashboard"))

    if pedido.status != "aguardando_entregador":
        flash("Este pedido não está disponível.", "warning")
        return redirect(url_for("entregador.dashboard"))

    if pedido.peso_total > entregador.capacidade_kg:
        flash("Pedido acima da sua capacidade de carga.", "danger")
        return redirect(url_for("entregador.pedido", pedido_id=pedido.id))

    pedido.entregador_id = entregador.id
    pedido.status = "aceito_pelo_entregador"
    db.session.commit()

    flash("Pedido aceito.", "success")
    return redirect(url_for("chat.chat_pedido", pedido_id=pedido.id))

@entregador_bp.route("/pedido/<int:pedido_id>/finalizar", methods=["POST"])
@login_required
def finalizar(pedido_id):
    if admin_em_modo_teste_entregador():
        flash("Modo teste: o admin visualiza o fluxo, mas não finaliza entrega real.", "warning")
        return redirect(url_for("entregador.pedido", pedido_id=pedido_id))

    entregador = get_entregador()
    pedido = Pedido.query.get_or_404(pedido_id)

    if not entregador:
        flash("Cadastro de entregador não encontrado para este usuário.", "danger")
        return redirect(url_for("entregador.dashboard"))

    if pedido.entregador_id != entregador.id:
        flash("Pedido não pertence a você.", "danger")
        return redirect(url_for("entregador.dashboard"))

    if request.form.get("codigo_confirmacao", "").strip() != pedido.codigo_confirmacao:
        flash("Código incorreto.", "danger")
        return redirect(url_for("entregador.pedido", pedido_id=pedido.id))

    pedido.status = "concluido"
    db.session.commit()

    flash("Entrega concluída.", "success")
    return redirect(url_for("entregador.dashboard"))
