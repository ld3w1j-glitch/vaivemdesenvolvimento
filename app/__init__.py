import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
from sqlalchemy import text

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Faça login para continuar."

def atualizar_banco_sqlite():
    """
    Atualiza o banco SQLite antigo sem apagar dados.
    Adiciona colunas novas nas tabelas antigas quando necessário.
    """
    try:
        if db.engine.url.get_backend_name() != "sqlite":
            return

        def colunas_da_tabela(nome_tabela):
            colunas = db.session.execute(text(f"PRAGMA table_info({nome_tabela})")).fetchall()
            return [col[1] for col in colunas]

        tabelas = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        nomes_tabelas = [t[0] for t in tabelas]

        if "mercado" in nomes_tabelas:
            colunas_mercado = colunas_da_tabela("mercado")

            novas_colunas_mercado = {
                "foto_perfil": "ALTER TABLE mercado ADD COLUMN foto_perfil VARCHAR(255)",
                "foto_apresentacao": "ALTER TABLE mercado ADD COLUMN foto_apresentacao VARCHAR(255)",
                "cor_primaria": "ALTER TABLE mercado ADD COLUMN cor_primaria VARCHAR(20) DEFAULT '#1f8a4c'",
                "cor_secundaria": "ALTER TABLE mercado ADD COLUMN cor_secundaria VARCHAR(20) DEFAULT '#e8f5ec'",
                "cor_ponteiro": "ALTER TABLE mercado ADD COLUMN cor_ponteiro VARCHAR(20) DEFAULT '#1f8a4c'",
            }

            for nome, sql in novas_colunas_mercado.items():
                if nome not in colunas_mercado:
                    db.session.execute(text(sql))

        db.session.commit()
    except Exception:
        db.session.rollback()

def create_app():
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

    database_url = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(app.instance_path, "vaivem.db")
    )

    # Compatibilidade com provedores que ainda entregam URLs no formato postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import Usuario, ConfiguracaoSite

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    @app.context_processor
    def carregar_configuracao_site():
        config = ConfiguracaoSite.query.first()

        if not config:
            config = ConfiguracaoSite()
            db.session.add(config)
            db.session.commit()

        return {"config_site": config}

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.cliente import cliente_bp
    from app.routes.entregador import entregador_bp
    from app.routes.chat import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(cliente_bp)
    app.register_blueprint(entregador_bp)
    app.register_blueprint(chat_bp)

    with app.app_context():
        from app.seed import seed_database
        db.create_all()
        atualizar_banco_sqlite()
        seed_database()

        if not ConfiguracaoSite.query.first():
            db.session.add(ConfiguracaoSite())
            db.session.commit()

    return app
