from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Pedido, ChatMensagem, Entregador
from app.utils import salvar_upload

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

def pode_acessar_chat(pedido):
    if current_user.tipo == "admin":
        return True
    if current_user.tipo == "cliente" and pedido.cliente_id == current_user.id:
        return True
    if current_user.tipo == "entregador":
        entregador = Entregador.query.filter_by(usuario_id=current_user.id).first()
        return entregador and pedido.entregador_id == entregador.id
    return False

@chat_bp.route("/pedido/<int:pedido_id>", methods=["GET", "POST"])
@login_required
def chat_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if not pode_acessar_chat(pedido):
        flash("Você não tem acesso a este chat.", "danger")
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        db.session.add(ChatMensagem(pedido_id=pedido.id, remetente_id=current_user.id, mensagem=request.form.get("mensagem"), anexo=salvar_upload(request.files.get("anexo"))))
        db.session.commit()
        return redirect(url_for("chat.chat_pedido", pedido_id=pedido.id))

    mensagens = ChatMensagem.query.filter_by(pedido_id=pedido.id).order_by(ChatMensagem.criado_em.asc()).all()
    return render_template("chat/chat.html", pedido=pedido, mensagens=mensagens)
