"""Auditoria tecnica, objetiva e local de imagens do Visual Master.

As heuristicas abaixo sao sinais para revisao humana, nunca percentuais de
"qualidade" nem uma aprovacao editorial automatica.
"""
from __future__ import annotations

import hashlib
import io
import mimetypes
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


def audit_image(data: bytes, filename: str = "imagem") -> dict:
    if not data:
        raise ValueError("A imagem esta vazia.")
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        width, height = image.size
        fmt = (image.format or Path(filename).suffix.lstrip(".") or "unknown").upper()
        mime = Image.MIME.get(image.format or "") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        alpha = "A" in image.getbands() or "transparency" in image.info
        gray = image.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_variance = round(ImageStat.Stat(edges).var[0], 2)
        # Conteudo muito proximo das quatro bordas pode indicar recorte apertado.
        border = max(1, min(width, height) // 100)
        border_stat = ImageStat.Stat(gray.crop((0, 0, width, border))).mean[0]
        border_stat += ImageStat.Stat(gray.crop((0, height - border, width, height))).mean[0]
        border_stat += ImageStat.Stat(gray.crop((0, 0, border, height))).mean[0]
        border_stat += ImageStat.Stat(gray.crop((width - border, 0, width, height))).mean[0]
        tight_crop_signal = border_stat / 4 < 235

    min_side = min(width, height)
    identity_quality = "boa referencia de identidade" if min_side >= 512 else "referencia utilizavel, revisar detalhes de identidade"
    print_quality = "PPI não calculado: tamanho físico final não informado. Readiness para impressão não avaliado."
    return {
        "width_px": width, "height_px": height, "format": fmt, "mime_type": mime,
        "file_size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "aspect_ratio": round(width / height, 4) if height else None,
        "has_alpha": alpha, "edge_variance": edge_variance,
        "sharpness_signal": "baixo; revisar visualmente" if edge_variance < 80 else "sem sinal forte de baixa nitidez",
        "compression_signal": "formato com perdas; revisar artefatos" if fmt in {"JPEG", "JPG"} else "nenhum sinal inferido apenas pelo formato",
        "possible_tight_crop": tight_crop_signal,
        "identity_reference_quality": identity_quality,
        "final_print_quality": print_quality,
        "ppi": None,
        "print_readiness": "not_assessed",
        "disclaimer": "Heuristicas tecnicas; nao substituem QA visual ou validacao de PPI no tamanho final.",
    }


def audit_path(path: str) -> dict:
    p = Path(path)
    return audit_image(p.read_bytes(), p.name)
