import os
import re
import unicodedata
import uuid
from decimal import Decimal, ROUND_HALF_UP
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


def _normalizar_texto_pix(texto, limite):
    """Remove acentos/símbolos inválidos e limita conforme padrão Pix EMV."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^A-Za-z0-9 .,&\-]", "", texto).strip().upper()
    return texto[:limite] or "NAO INFORMADO"


def _campo_emv(identificador, valor):
    valor = str(valor)
    return f"{identificador}{len(valor):02d}{valor}"


def _crc16_ccitt(payload):
    crc = 0xFFFF
    for char in payload.encode("utf-8"):
        crc ^= char << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def gerar_payload_pix(valor_total, pedido_id=None):
    """
    Gera payload Pix Copia e Cola real no padrão BR Code/EMV.
    O QR gerado com esse texto é reconhecido por apps bancários como pagamento Pix.
    """
    config = obter_configuracao_site()

    pix_chave = (config.pix_chave if config else "").strip()
    pix_nome = _normalizar_texto_pix(config.pix_nome_recebedor if config else "", 25)
    pix_cidade = _normalizar_texto_pix(config.pix_cidade_recebedor if config else "", 15)

    if not pix_chave:
        return ""

    valor = Decimal(str(valor_total or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    txid = f"PEDIDO{pedido_id}" if pedido_id else "VAIVEM"
    txid = re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "VAIVEM"

    merchant_account = _campo_emv("00", "br.gov.bcb.pix") + _campo_emv("01", pix_chave)
    additional_data = _campo_emv("05", txid)

    payload_sem_crc = "".join([
        _campo_emv("00", "01"),
        _campo_emv("26", merchant_account),
        _campo_emv("52", "0000"),
        _campo_emv("53", "986"),
        _campo_emv("54", f"{valor:.2f}"),
        _campo_emv("58", "BR"),
        _campo_emv("59", pix_nome),
        _campo_emv("60", pix_cidade),
        _campo_emv("62", additional_data),
        "6304",
    ])

    return payload_sem_crc + _crc16_ccitt(payload_sem_crc)


def gerar_qrcode_pedido(pedido_id, valor_total):
    """Cria o QR Code Pix real em SVG e salva também o texto copia e cola."""
    filename = f"qrcode_pedido_{pedido_id}.svg"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    payload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], f"qrcode_pedido_{pedido_id}.txt")

    payload = gerar_payload_pix(valor_total, pedido_id)

    if not payload:
        # Mantém um arquivo simples para a tela informar que falta configurar o Pix.
        with open(payload_path, "w", encoding="utf-8") as f:
            f.write("")
        return None

    try:
        import qrcode
        import qrcode.image.svg

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        img.save(path)
    except Exception:
        # Fallback: gera PNG se o backend SVG não estiver disponível.
        import qrcode

        filename = f"qrcode_pedido_{pedido_id}.png"
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        img = qrcode.make(payload)
        img.save(path)

    with open(payload_path, "w", encoding="utf-8") as f:
        f.write(payload)

    return filename


def obter_pix_copia_cola_pedido(pedido):
    """Lê o payload salvo; se não existir, recria com os dados atuais do pedido."""
    if not pedido:
        return ""

    payload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], f"qrcode_pedido_{pedido.id}.txt")

    if os.path.exists(payload_path):
        with open(payload_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    payload = gerar_payload_pix(pedido.valor_total, pedido.id)

    if payload:
        with open(payload_path, "w", encoding="utf-8") as f:
            f.write(payload)

    return payload
