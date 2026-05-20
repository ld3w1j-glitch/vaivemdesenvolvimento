from app import db
from app.models import Usuario, Mercado, Produto, Entregador

def seed_database():
    if not Usuario.query.filter_by(email="admin@vaivem.com").first():
        admin = Usuario(nome="Administrador", email="admin@vaivem.com", tipo="admin", telefone="0000-0000")
        admin.set_senha("admin123")
        db.session.add(admin)

    if Mercado.query.count() == 0:
        m1 = Mercado(nome="Mercado Central", endereco="Centro, Pouso Alegre - MG", latitude=-22.2280, longitude=-45.9368, telefone="(35) 99999-1111", horario="08:00 às 20:00")
        m2 = Mercado(nome="Mercado Alvorada", endereco="Bairro São João, Pouso Alegre - MG", latitude=-22.2355, longitude=-45.9252, telefone="(35) 99999-2222", horario="07:00 às 21:00")
        db.session.add_all([m1, m2])
        db.session.flush()

        db.session.add_all([
            Produto(mercado_id=m1.id, codigo="789001", descricao="Arroz 5kg", valor=29.90, peso_kg=5, categoria="Mercearia", estoque=30),
            Produto(mercado_id=m1.id, codigo="789002", descricao="Feijão 1kg", valor=8.90, peso_kg=1, categoria="Mercearia", estoque=40),
            Produto(mercado_id=m1.id, codigo="789003", descricao="Óleo 900ml", valor=6.90, peso_kg=0.9, categoria="Mercearia", estoque=25),
            Produto(mercado_id=m2.id, codigo="789001", descricao="Arroz 5kg", valor=27.50, peso_kg=5, categoria="Mercearia", estoque=20),
            Produto(mercado_id=m2.id, codigo="789002", descricao="Feijão 1kg", valor=9.20, peso_kg=1, categoria="Mercearia", estoque=35),
            Produto(mercado_id=m2.id, codigo="789004", descricao="Açúcar 5kg", valor=18.90, peso_kg=5, categoria="Mercearia", estoque=18),
        ])

    db.session.commit()
