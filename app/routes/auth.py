from datetime import datetime, timedelta
import base64
import os
import random
import urllib.parse
import urllib.request

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import Usuario, RecuperacaoSenha

auth_bp = Blueprint("auth", __name__)

def somente_numeros(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())

def telefone_para_e164(telefone):
    numeros = somente_numeros(telefone)
    country_code = os.getenv("DEFAULT_COUNTRY_CODE", "55")

    if not numeros:
        return ""

    if numeros.startswith(country_code) and len(numeros) >= 12:
        return "+" + numeros

    return "+" + country_code + numeros

def formatar_telefone_simples(telefone):
    numeros = somente_numeros(telefone)

    if len(numeros) >= 3:
        return f"({numeros[:2]}) {numeros[2:]}"

    return telefone

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

def buscar_usuario_por_telefone(telefone):
    telefone_digitado = somente_numeros(telefone)

    if not telefone_digitado:
        return None

    usuarios = Usuario.query.all()

    for usuario in usuarios:
        if somente_numeros(usuario.telefone) == telefone_digitado:
            return usuario

    return None

def enviar_sms_twilio(telefone_destino, mensagem):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_phone = os.getenv("TWILIO_PHONE_NUMBER", "").strip()

    if not account_sid or not auth_token or not twilio_phone:
        return False, "Twilio não configurado no arquivo .env."

    telefone_e164 = telefone_para_e164(telefone_destino)

    if not telefone_e164:
        return False, "Telefone inválido."

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    data = urllib.parse.urlencode({
        "From": twilio_phone,
        "To": telefone_e164,
        "Body": mensagem
    }).encode("utf-8")

    auth_raw = f"{account_sid}:{auth_token}".encode("utf-8")
    auth_header = base64.b64encode(auth_raw).decode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if 200 <= response.status < 300:
                return True, "SMS enviado com sucesso."
            return False, f"Twilio retornou status {response.status}."
    except Exception as erro:
        return False, f"Erro ao enviar SMS: {erro}"

def enviar_codigo_recuperacao(telefone, codigo):
    mensagem = f"Seu codigo de recuperacao do VaiVem Mercado e: {codigo}. Ele expira em 10 minutos."

    provider = os.getenv("SMS_PROVIDER", "teste").strip().lower()

    if provider == "twilio":
        enviado, detalhe = enviar_sms_twilio(telefone, mensagem)

        if enviado:
            return True, detalhe, False

        session["codigo_recuperacao_debug"] = codigo
        session["telefone_recuperacao_debug"] = telefone
        return False, detalhe, True

    session["codigo_recuperacao_debug"] = codigo
    session["telefone_recuperacao_debug"] = telefone
    return False, "Modo teste ativo. Código exibido na tela.", True

@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.tipo == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.tipo == "entregador":
            return redirect(url_for("entregador.dashboard"))
        return redirect(url_for("cliente.dashboard"))

    return render_template("index.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Compatível com template novo e antigo:
        # novo: name="login"
        # antigo: name="email"
        login_digitado = (
            request.form.get("login", "") or
            request.form.get("email", "")
        ).strip()

        senha = request.form.get("senha", "")

        usuario = None

        if "@" in login_digitado:
            usuario = Usuario.query.filter_by(email=login_digitado.lower()).first()
        else:
            usuario = buscar_usuario_por_telefone(login_digitado)

        if usuario and usuario.check_senha(senha):
            login_user(usuario)
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("auth.index"))

        flash("Email, telefone ou senha inválidos.", "danger")

    return render_template("auth/login.html")

@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        telefone = request.form.get("telefone", "").strip()

        cep = request.form.get("cep", "").strip()
        rua = request.form.get("rua", "").strip()
        numero = request.form.get("numero", "").strip()
        bairro = request.form.get("bairro", "").strip()
        cidade = request.form.get("cidade", "").strip()
        estado = request.form.get("estado", "").strip()
        complemento = request.form.get("complemento", "").strip()

        erros_senha = senha_eh_segura(senha)
        if erros_senha:
            flash("A senha precisa " + ", ".join(erros_senha) + ".", "danger")
            return redirect(url_for("auth.cadastro"))

        if Usuario.query.filter_by(email=email).first():
            flash("Este email já está cadastrado.", "warning")
            return redirect(url_for("auth.cadastro"))

        telefone_numeros = somente_numeros(telefone)

        if not telefone_numeros:
            flash("Informe um telefone válido. Ele será usado para login e recuperação de senha.", "danger")
            return redirect(url_for("auth.cadastro"))

        if buscar_usuario_por_telefone(telefone):
            flash("Este telefone já está cadastrado.", "warning")
            return redirect(url_for("auth.cadastro"))

        partes_endereco = []

        if rua:
            partes_endereco.append(rua)

        if numero:
            partes_endereco.append(f"Nº {numero}")

        if bairro:
            partes_endereco.append(bairro)

        if cidade or estado:
            partes_endereco.append(f"{cidade} - {estado}".strip(" -"))

        if cep:
            partes_endereco.append(f"CEP: {cep}")

        if complemento:
            partes_endereco.append(f"Complemento: {complemento}")

        endereco_completo = ", ".join(partes_endereco)

        usuario = Usuario(
            nome=nome,
            email=email,
            tipo="cliente",
            telefone=formatar_telefone_simples(telefone),
            endereco=endereco_completo
        )

        usuario.set_senha(senha)

        db.session.add(usuario)
        db.session.commit()

        flash("Cadastro criado com sucesso. Agora você pode entrar com email ou telefone.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/cadastro.html")

@auth_bp.route("/recuperar-senha", methods=["GET", "POST"])
def recuperar_senha():
    if request.method == "POST":
        telefone = request.form.get("telefone", "").strip()
        usuario = buscar_usuario_por_telefone(telefone)

        if not usuario:
            flash("Não encontramos uma conta com este telefone.", "danger")
            return redirect(url_for("auth.recuperar_senha"))

        codigo = str(random.randint(100000, 999999))
        expira_em = datetime.utcnow() + timedelta(minutes=10)

        RecuperacaoSenha.query.filter_by(usuario_id=usuario.id, usado=False).update({"usado": True})

        recuperacao = RecuperacaoSenha(
            usuario_id=usuario.id,
            telefone=formatar_telefone_simples(telefone),
            codigo=codigo,
            usado=False,
            expira_em=expira_em
        )

        db.session.add(recuperacao)
        db.session.commit()

        sms_enviado, detalhe, mostrar_codigo_teste = enviar_codigo_recuperacao(telefone, codigo)

        if sms_enviado:
            flash("Enviamos um código por SMS para o telefone informado.", "success")
        else:
            flash(detalhe, "warning")

            if mostrar_codigo_teste:
                flash(f"Modo teste local: código gerado {codigo}", "info")

        return redirect(url_for("auth.redefinir_senha", telefone=somente_numeros(telefone)))

    return render_template("auth/recuperar_senha.html")

@auth_bp.route("/redefinir-senha", methods=["GET", "POST"])
def redefinir_senha():
    telefone_query = request.args.get("telefone", "")

    if request.method == "POST":
        telefone = request.form.get("telefone", "").strip()
        codigo = request.form.get("codigo", "").strip()
        nova_senha = request.form.get("nova_senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")

        usuario = buscar_usuario_por_telefone(telefone)

        if not usuario:
            flash("Telefone não encontrado.", "danger")
            return redirect(url_for("auth.redefinir_senha"))

        recuperacao = RecuperacaoSenha.query.filter_by(
            usuario_id=usuario.id,
            codigo=codigo,
            usado=False
        ).order_by(RecuperacaoSenha.id.desc()).first()

        if not recuperacao:
            flash("Código inválido ou já utilizado.", "danger")
            return redirect(url_for("auth.redefinir_senha", telefone=somente_numeros(telefone)))

        if recuperacao.expira_em < datetime.utcnow():
            recuperacao.usado = True
            db.session.commit()
            flash("Código expirado. Solicite um novo código.", "danger")
            return redirect(url_for("auth.recuperar_senha"))

        if nova_senha != confirmar_senha:
            flash("A nova senha e a confirmação não conferem.", "danger")
            return redirect(url_for("auth.redefinir_senha", telefone=somente_numeros(telefone)))

        erros_senha = senha_eh_segura(nova_senha)
        if erros_senha:
            flash("A nova senha precisa " + ", ".join(erros_senha) + ".", "danger")
            return redirect(url_for("auth.redefinir_senha", telefone=somente_numeros(telefone)))

        if usuario.check_senha(nova_senha):
            flash("A nova senha não pode ser igual à senha anterior.", "danger")
            return redirect(url_for("auth.redefinir_senha", telefone=somente_numeros(telefone)))

        usuario.set_senha(nova_senha)
        recuperacao.usado = True

        db.session.commit()

        flash("Senha redefinida com sucesso. Faça login com seu telefone e nova senha.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/redefinir_senha.html", telefone=telefone_query)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.index"))
