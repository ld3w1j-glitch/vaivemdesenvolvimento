from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(30), nullable=False, default="cliente")
    telefone = db.Column(db.String(40))
    foto = db.Column(db.String(255))
    endereco = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

class Mercado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(140), nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False, default=-22.228)
    longitude = db.Column(db.Float, nullable=False, default=-45.936)
    telefone = db.Column(db.String(40))
    horario = db.Column(db.String(120))
    logo = db.Column(db.String(255))
    foto_perfil = db.Column(db.String(255))
    foto_apresentacao = db.Column(db.String(255))
    cor_primaria = db.Column(db.String(20), default="#1f8a4c")
    cor_secundaria = db.Column(db.String(20), default="#e8f5ec")
    cor_ponteiro = db.Column(db.String(20), default="#1f8a4c")
    ativo = db.Column(db.Boolean, default=True)

    produtos = db.relationship("Produto", backref="mercado", cascade="all, delete-orphan")

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mercado_id = db.Column(db.Integer, db.ForeignKey("mercado.id"), nullable=False)
    codigo = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.String(180), nullable=False)
    valor = db.Column(db.Float, nullable=False, default=0)
    peso_kg = db.Column(db.Float, nullable=False, default=0)
    categoria = db.Column(db.String(100))
    estoque = db.Column(db.Integer, default=0)
    foto = db.Column(db.String(255))

class Entregador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    veiculo = db.Column(db.String(120), nullable=False)
    capacidade_kg = db.Column(db.Float, nullable=False, default=20)
    status = db.Column(db.String(40), default="disponivel")
    usuario = db.relationship("Usuario", backref="entregador", uselist=False)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    mercado_id = db.Column(db.Integer, db.ForeignKey("mercado.id"), nullable=False)
    entregador_id = db.Column(db.Integer, db.ForeignKey("entregador.id"), nullable=True)
    endereco_entrega = db.Column(db.String(255), nullable=False)
    peso_total = db.Column(db.Float, nullable=False, default=0)
    valor_produtos = db.Column(db.Float, nullable=False, default=0)
    taxa_entrega = db.Column(db.Float, nullable=False, default=0)
    valor_total = db.Column(db.Float, nullable=False, default=0)
    codigo_confirmacao = db.Column(db.String(10), nullable=False)
    qr_code = db.Column(db.String(255))
    status = db.Column(db.String(60), default="aguardando_pagamento")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    cliente = db.relationship("Usuario", foreign_keys=[cliente_id])
    mercado = db.relationship("Mercado")
    entregador = db.relationship("Entregador")
    itens = db.relationship("PedidoItem", backref="pedido", cascade="all, delete-orphan")

class PedidoItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"), nullable=False)
    codigo_produto = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.String(180), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    valor_unitario = db.Column(db.Float, nullable=False)
    peso_unitario = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    produto = db.relationship("Produto")

class ChatMensagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False)
    remetente_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    mensagem = db.Column(db.Text)
    anexo = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    remetente = db.relationship("Usuario")
    pedido = db.relationship("Pedido")

class TaxaEntrega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    peso_min = db.Column(db.Float, nullable=False, default=0)
    peso_max = db.Column(db.Float, nullable=True)
    valor = db.Column(db.Float, nullable=False, default=0)
    descricao = db.Column(db.String(120))
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class RecuperacaoSenha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    telefone = db.Column(db.String(40), nullable=False)
    codigo = db.Column(db.String(10), nullable=False)
    usado = db.Column(db.Boolean, default=False)
    expira_em = db.Column(db.DateTime, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship("Usuario")

class ConfiguracaoSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    nome_site = db.Column(db.String(120), default="VaiVem Mercado")
    slogan = db.Column(db.String(255), default="Mercados do bairro, comparação de preços e entrega local.")
    bairro_regiao = db.Column(db.String(120), default="")
    telefone_suporte = db.Column(db.String(40), default="")
    email_suporte = db.Column(db.String(160), default="")

    logo_site = db.Column(db.String(255))
    icone_site = db.Column(db.String(255))

    cor_principal = db.Column(db.String(20), default="#1f8a4c")
    cor_secundaria = db.Column(db.String(20), default="#e8f5ec")

    comparacao_precos_ativa = db.Column(db.Boolean, default=True)

    tipo_mapa = db.Column(db.String(40), default="openstreetmap")
    google_maps_api_key = db.Column(db.String(255), default="")

    pix_chave = db.Column(db.String(180), default="")
    pix_nome_recebedor = db.Column(db.String(160), default="")
    pix_cidade_recebedor = db.Column(db.String(120), default="")

    mensagem_padrao_cliente = db.Column(db.Text, default="Olá! Seu pedido foi recebido e em breve será atendido.")
    mensagem_padrao_entregador = db.Column(db.Text, default="Olá! Sou o entregador responsável pelo seu pedido.")

    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
