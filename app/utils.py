import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

def obter_taxas_padrao():
    return [
        {"peso_min": 0.0, "peso_max": 5.0, "valor": 5.0, "descricao": "Até 5kg"},
        {"peso_min": 5.01, "peso_max": 15.0, "valor": 8.0, "descricao": "De 5kg até 15kg"},
        {"peso_min": 15.01, "peso_max": 25.0, "valor": 12.0, "descricao": "De 15kg até 25kg"},
        {"peso_min": 25.01, "peso_max": None, "valor": 20.0, "descricao": "Acima de 25kg"},
    ]

def obter_configuracao_site():
    try:
        from app.models import ConfiguracaoSite
        from app import db

        config = ConfiguracaoSite.query.first()

        if not config:
            config = ConfiguracaoSite()
            db.session.add(config)
            db.session.commit()

        return config
    except Exception:
        return None

def comparacao_precos_ativa():
    config = obter_configuracao_site()

    if not config:
        return True

    return bool(config.comparacao_precos_ativa)

def calcular_taxa_entrega(peso_kg):
    peso_kg = float(peso_kg or 0)

    try:
        from app.models import TaxaEntrega

        faixas = TaxaEntrega.query.filter_by(ativo=True).order_by(TaxaEntrega.peso_min.asc()).all()

        if faixas:
            for faixa in faixas:
                peso_min = float(faixa.peso_min or 0)
                peso_max = faixa.peso_max

                if peso_kg >= peso_min and (peso_max is None or peso_kg <= float(peso_max)):
                    return float(faixa.valor or 0)
    except Exception:
        pass

    for faixa in obter_taxas_padrao():
        peso_min = faixa["peso_min"]
        peso_max = faixa["peso_max"]

        if peso_kg >= peso_min and (peso_max is None or peso_kg <= peso_max):
            return faixa["valor"]

    return 20.0

def salvar_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1]
    final_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], final_name)

    file_storage.save(path)

    return final_name

def gerar_codigo_confirmacao():
    return str(uuid.uuid4().int)[:6]

def gerar_qrcode_pedido(pedido_id, valor_total):
    filename = f"qrcode_pedido_{pedido_id}.svg"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)

    config = obter_configuracao_site()
    pix_chave = config.pix_chave if config else ""
    pix_nome = config.pix_nome_recebedor if config else ""

    payload = f"PIX-SIMULADO|PEDIDO:{pedido_id}|VALOR:{valor_total:.2f}|CHAVE:{pix_chave}|NOME:{pix_nome}"
    seed = sum(ord(c) for c in payload)
    size = 25
    cell = 8
    total = size * cell

    def in_marker(x, y):
        return (x < 7 and y < 7) or (x >= size - 7 and y < 7) or (x < 7 and y >= size - 7)

    def marker_dark(x, y):
        local_x = x if x < 7 else x - (size - 7)
        local_y = y if y < 7 else y - (size - 7)
        return local_x in (0, 6) or local_y in (0, 6) or (2 <= local_x <= 4 and 2 <= local_y <= 4)

    rects = []

    for y in range(size):
        for x in range(size):
            dark = marker_dark(x, y) if in_marker(x, y) else ((x * 17 + y * 31 + seed) % 7) in (0, 2, 5)

            if dark:
                rects.append(f'<rect x="{x*cell}" y="{y*cell}" width="{cell}" height="{cell}" fill="#111827"/>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{total}" viewBox="0 0 {total} {total}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        + ''.join(rects) +
        f'<title>{payload}</title></svg>'
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)

    return filename
