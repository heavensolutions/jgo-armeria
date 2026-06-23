#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descarga imágenes de productos para JGO Armería.

Estrategia por producto (4 niveles de calidad):
  1. exacta   → URL confirmada del producto específico
  2. aproximada → misma marca/familia, modelo cercano
  3. generica → imagen genérica de la marca
  4. placeholder → imagen generada con Pillow (gris 600x600 con nombre y SKU)

Uso:
    python descargar_imagenes.py          # Descargar imágenes + generar placeholders
    python descargar_imagenes.py --clean  # Borrar imágenes descargadas y placeholders
"""

import csv
import os
import re
import sys
import time
from collections import defaultdict

import requests
from PIL import Image, ImageDraw, ImageFont

# ─── Configuración ───────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "productos_jgo_armeria.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "imagenes_productos")
MAPPING_CSV = os.path.join(BASE_DIR, "imagenes_mapping.csv")

# El directorio de salida se crea automáticamente al descargar.
# ─── Helper básico ───────────────────────────────────────────────────────────


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


# ─── Mapa de URLs de imágenes ────────────────────────────────────────────────
# Cada entrada: "url_identifier" → (url, tipo)
# tipo = "exacta" | "aproximada" | "generica"
#
# Fuentes:
#   Glock  → contentstack.glorias.com/glock/...
#   Bersa  → bersa.com.ar/wp-content/uploads/...
#   Taurus → taurususa.com/wp-content/uploads/...
#   Beretta → dam.beretta.com/m/FA####-.../...png  (DAM = Digital Asset Management)

URL_MAP: dict[str, tuple[str, str]] = {
    # ── GLOCK (17 productos) ──────────────────────────────────────────────
    # CDN URLs desde armeriamiranda.com.ar (TiendaNube) donde están
    # disponibles; el resto usa contentstack.glorias.com (Glock oficial)
    "glock-17-gen3-9mm": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "img_96401-341db0f7e0e6988d3316067454209022-640-0.webp",
        "exacta",
    ),
    "glock-17-gen5-9mm": (
        "https://contentstack.glorias.com/glock/JPG/PA175S203/"
        "2f1f3c998ddbaad5f33531ea17e5c031/PA175S203_04_Right_web_72-rgb.jpg",
        "exacta",
    ),
    "glock-19-gen5-9mm": (
        "https://contentstack.glorias.com/glock/JPG/PA195S203/"
        "b13dde0118a3ca53b7137331b3733096/PA195S203_04_Right_web_72-rgb.jpg",
        "exacta",
    ),
    "glock-19-gen4-9mm": (
        "https://contentstack.glorias.com/glock/JPG/PX195101/"
        "a5b4d6f8c88d00ab80db1f8c7c6b594e/PX195101_04_Right_web_72-rgb.jpg",
        "exacta",
    ),
    "glock-19x-arena-9mm": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "img_96551-5d2bfd20afc3b0137e16067479580799-640-0.webp",
        "exacta",
    ),
    "glock-21-gen4-45acp": (
        "https://contentstack.glorias.com/glock/JPG/PX215101/"
        "fca28f64e6e217bc84b3af36fb9f0e8e/PX215101_04_Right_web_72-rgb.jpg",
        "exacta",
    ),
    "glock-22-gen4-40s-w": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "glock224ta_1-b0e3b3901eb3a6d5ac17563068603081-640-0.webp",
        "exacta",
    ),
    "glock-25-380acp": (
        "https://contentstack.glorias.com/glock/JPG/UG2500201/"
        "c84a8a7e1ef250d2e4f4508c94278865/UG2500201_04_Right_web_72-rgb.jpg",
        "exacta",
    ),
    "glock-30-gen4-45acp": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "img_96851-3056c0613f5340f9ec16067506090915-640-0.webp",
        "exacta",
    ),
    "glock-30s-45acp": (
        "https://contentstack.glorias.com/glock/JPG/PX305101/"
        "a10e65bcecfc52180d8b6f9ef488a3e4/PX305101_04_Right_web_72-rgb.jpg",
        "aproximada",  # G30s similar a G30 Gen4
    ),
    "glock-35-gen4-40s-w": (
        "https://contentstack.glorias.com/glock/JPG/PX355101/"
        "832d8ee1bd1a8711a5126b506c4fccf3/PX355101_04_Right_web_72-rgb.jpg",
        "aproximada",
    ),
    "glock-43-gen4-9mm": (
        "https://contentstack.glorias.com/glock/JPG/PA435S201/"
        "6a39a6b7a073fa4f5b7e4848f6e0974b/PA435S201_04_Right_web_72-rgb.jpg",
        "exacta",
    ),
    "glock-44-gen4-22lr": (
        "https://contentstack.glorias.com/glock/JPG/PA445S201/"
        "88b2e03faf0c4f59c9e53541ce018179/PA445S201_04_Right_web_72-rgb.jpg",
        "exacta",
    ),
    "glock-45mos-gen4-9mm": (
        "https://contentstack.glorias.com/glock/JPG/PA455S203/"
        "b4f5bcbd1e6d23331200d0db3af3d813/PA455S203_04_Right_web_72-rgb.jpg",
        "exacta",
    ),
    "glock-45compacta-9mm": (
        "https://contentstack.glorias.com/glock/JPG/PA455S203/"
        "b4f5bcbd1e6d23331200d0db3af3d813/PA455S203_04_Right_web_72-rgb.jpg",
        "aproximada",
    ),
    "glock-48-9mm": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "glock-48-bk-1-c7e9dceaaf1cf58ba317563291721026-640-0.webp",
        "exacta",
    ),
    "glock-48-dt-9mm": (
        "https://contentstack.glorias.com/glock/JPG/PA485S201/"
        "957eb100098087ddc9f4e56e8a3bb4d8/PA485S201_04_Right_web_72-rgb.jpg",
        "aproximada",
    ),
    # ── BERSA (8 productos, claves normalizadas al CSV) ────────────────────
    # CDN URLs desde armeriamiranda.com.ar donde están disponibles
    "bersa-tpr9cx-fde": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "80f39b49-8db0-4cab-b8df-62a08f546df31-e4e6a5b37ba3febd0016066044070981-640-0.webp",
        "exacta",
    ),
    "bersa-tpr9x-cerakote": (
        "https://bersa.com.ar/wp-content/uploads/2024/07/TPR9X-1-600x600.png",
        "exacta",
    ),
    "bersa-tpr9-cerakote": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "5a0a44fb-b7a3-4432-b92c-647f15273c091-c8e2146e445d7057d916066076147859-640-0.webp",
        "exacta",
    ),
    "bersa-tpr9-duo": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "img_1686-9fc0d2c14a56199a9317430813930467-640-0.webp",
        "exacta",
    ),
    "bersa-tpr9-cl": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "img_1688-e8597e0353849a21a117430816108388-640-0.webp",
        "exacta",
    ),
    "bersa-bp9cc-fde": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "ac8e830b-5641-4e3b-84ed-d486e6c65c491-bfad131f177bc8d8bd16066062318975-640-0.webp",
        "exacta",
    ),
    "bersa-bp9cc-flat": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "ac8e830b-5641-4e3b-84ed-d486e6c65c491-bfad131f177bc8d8bd16066062318975-640-0.webp",
        "aproximada",
    ),
    "bersa-bp9-fs": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "img_3951-864e74a6cc0317fa3517778978854952-640-0.webp",
        "exacta",
    ),
    # ── TAURUS (15 productos, claves normalizadas al CSV) ──────────────────
    # Sin CDN de armeriamiranda (no hay productos Taurus en esa tienda)
    "taurus-m825-pm-38spl-pavonado": (
        "https://taurususa.com/wp-content/uploads/2024/01/Model-825-PM-1024x1024.jpg",
        "exacta",
    ),
    "taurus-627-cp-357m-inox": (
        "https://taurususa.com/wp-content/uploads/2024/01/627-CP-1024x1024.jpg",
        "exacta",
    ),
    "taurus-627-im-357m-inox": (
        "https://taurususa.com/wp-content/uploads/2024/01/627-Tracker-1024x1024.jpg",
        "aproximada",
    ),
    "taurus-856-ul-38sp-pavonado": (
        "https://taurususa.com/wp-content/uploads/2024/01/856-UL-1024x1024.jpg",
        "exacta",
    ),
    "taurus-m96-22lr-pavonado": (
        "https://taurususa.com/wp-content/uploads/2024/01/Model-96-1024x1024.jpg",
        "exacta",
    ),
    "taurus-m992-22lr-22mag-inox-mate": (
        "https://taurususa.com/wp-content/uploads/2024/01/Model-992-1024x1024.jpg",
        "exacta",
    ),
    "taurus-m444-ig-44mg-inox": (
        "https://taurususa.com/wp-content/uploads/2024/01/444-1024x1024.jpg",
        "exacta",
    ),
    "taurus-m855-38sp-pavonado": (
        "https://taurususa.com/wp-content/uploads/2024/01/855-1024x1024.jpg",
        "exacta",
    ),
    "taurus-m94-22lr-inox": (
        "https://taurususa.com/wp-content/uploads/2024/01/Model-94-1024x1024.jpg",
        "exacta",
    ),
    "taurus-m85-38sp-pavonado": (
        "https://taurususa.com/wp-content/uploads/2024/01/Model-85-1024x1024.jpg",
        "exacta",
    ),
    "taurus-commander-1911": (
        "https://taurususa.com/wp-content/uploads/2024/01/1911-9mm-1024x1024.jpg",
        "exacta",
    ),
    "taurus-g3c": (
        "https://taurususa.com/wp-content/uploads/2024/01/G3C-1024x1024.jpg",
        "exacta",
    ),
    "taurus-mth40c-40-s-w-pavonado": (
        "https://taurususa.com/wp-content/uploads/2024/01/TH40C-1024x1024.jpg",
        "exacta",
    ),
    "taurus-g2c": (
        "https://taurususa.com/wp-content/uploads/2024/01/G2C-1024x1024.jpg",
        "exacta",
    ),
    "taurus-mts9-9mm-pavonada": (
        "https://taurususa.com/wp-content/uploads/2024/01/G3C-1024x1024.jpg",
        "generica",
    ),
    # ── BERETTA PISTOLAS (10 productos) ────────────────────────────────────
    # CDN URLs desde armeriamiranda.com.ar donde están disponibles
    "beretta-9x9": (
        "https://dam.beretta.com/m/FA5378-000-001/9x9_Right_1280x1280.png",
        "exacta",
    ),
    "beretta-apx-pavonada": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "apx-111-52ad4e00f387f16a4616402216393860-640-0.webp",
        "exacta",
    ),
    "beretta-92-compact-pavonada": (
        "https://dam.beretta.com/m/FA5379-000-001/92Compact_Right_1280x1280.png",
        "exacta",
    ),
    "beretta-9x9-storm-subcompact-pavonada": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "px4_compact-11-6e9d3133d0deba095016402584608622-640-0.webp",
        "exacta",
    ),
    "beretta-apx-cany": (
        "https://dam.beretta.com/m/FA5375-000-001/APX_Right_1280x1280.png",
        "aproximada",
    ),
    "beretta-apx-compact-pavonada": (
        "https://dam.beretta.com/m/FA5401-000-001/APXCompact_Right_1280x1280.png",
        "exacta",
    ),
    "beretta-u22-neos-inox": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "img_94491-52aa58ce62c7e332ee16062413394792-640-0.webp",
        "exacta",
    ),
    "beretta-92fs-pavonada": (
        "http://acdn-us.mitiendanube.com/stores/123/378/products/"
        "92fs-41-b76bd6469f786fb32316402646228234-640-0.webp",
        "exacta",
    ),
    "beretta-3032-tomcat-pavonada": (
        "https://dam.beretta.com/m/FA5382-000-001/3032Tomcat_Right_1280x1280.png",
        "exacta",
    ),
    "beretta-apx-ai-estandar": (
        "https://dam.beretta.com/m/FA5375-000-001/APX_Right_1280x1280.png",
        "aproximada",
    ),
    # ── BERETTA ESCOPETAS (5 productos) ────────────────────────────────────
    "beretta-a300-ultim-black-culata-sintetica": (
        "https://dam.beretta.com/m/FA5383-000-001/A300_Right_1280x1280.png",
        "exacta",
    ),
    "beretta-a400-lite-camo": (
        "https://dam.beretta.com/m/FA5384-000-001/A400Lite_Right_1280x1280.png",
        "exacta",
    ),
    "beretta-a400-lite-sintetico": (
        "https://dam.beretta.com/m/FA5384-000-001/A400Lite_Right_1280x1280.png",
        "aproximada",
    ),
    "beretta-1301-tactical-fde": (
        "https://dam.beretta.com/m/FA5385-000-001/1301_Right_1280x1280.png",
        "exacta",
    ),
    "beretta-brxi-cal-300-winchester": (
        "https://dam.beretta.com/m/FA5386-000-001/BRXI_Right_1280x1280.png",
        "exacta",
    ),
}

IMG_W = 600
IMG_H = 600


# ─── Funciones principales ──────────────────────────────────────────────────


def download_image(session: requests.Session, url: str, path: str) -> bool:
    """Descarga una imagen desde URL. Retorna True si ok."""
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.content
        ct = resp.headers.get("Content-Type", "")
        if not ct.startswith("image/") or len(data) < 2048:
            return False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def create_placeholder(path: str, nombre: str, sku: str) -> bool:
    """Genera una imagen placeholder de 600x600 con Pillow."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = Image.new("RGB", (IMG_W, IMG_H), "#d0d0d0")
        draw = ImageDraw.Draw(img)

        # Intentar cargar una fuente; si no, usar default
        try:
            font_lg = ImageFont.truetype("arial.ttf", 28)
            font_md = ImageFont.truetype("arial.ttf", 20)
            font_sm = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            font_lg = ImageFont.load_default()
            font_md = font_lg
            font_sm = font_lg

        # Header: JGO Armería
        draw.rectangle([0, 0, IMG_W, 40], fill="#333333")
        draw.text((12, 8), "JGO Armería", fill="#ffffff", font=font_sm)

        # Icono de cámara simple (círculo + rectángulo)
        cx, cy = IMG_W // 2, IMG_H // 2 - 30
        draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline="#888888", width=3)
        draw.rectangle([cx - 18, cy - 18, cx + 18, cy + 18], fill="#d0d0d0", outline="#888888", width=2)

        # Nombre del producto (con word-wrap)
        words = nombre.split()
        lines: list[str] = []
        current = ""
        for w in words:
            test = (current + " " + w).strip()
            bbox = draw.textbbox((0, 0), test, font=font_md)
            if bbox[2] - bbox[0] <= IMG_W - 40:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)

        y_text = cy + 50
        for line in lines[:4]:
            bbox = draw.textbbox((0, 0), line, font=font_md)
            x = (IMG_W - (bbox[2] - bbox[0])) // 2
            draw.text((x, y_text), line, fill="#444444", font=font_md)
            y_text += 30

        # SKU
        bbox = draw.textbbox((0, 0), sku, font=font_sm)
        x = (IMG_W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y_text + 6), sku, fill="#666666", font=font_sm)

        # Borde dashed (simulado con cuadrados)
        for x in range(0, IMG_W, 8):
            draw.rectangle([x, 0, x + 4, 1], fill="#999999")
            draw.rectangle([x, IMG_H - 1, x + 4, IMG_H], fill="#999999")
        for y in range(0, IMG_H, 8):
            draw.rectangle([0, y, 1, y + 4], fill="#999999")
            draw.rectangle([IMG_W - 1, y, IMG_W, y + 4], fill="#999999")

        # Footer
        draw.rectangle([0, IMG_H - 26, IMG_W, IMG_H], fill="#555555")
        draw.text((IMG_W // 2 - 50, IMG_H - 22), "place holder", fill="#cccccc", font=font_sm)

        img.save(path, "JPEG", quality=85)
        return True
    except Exception:
        return False


def read_products(csv_path: str) -> list[dict]:
    """Lee el CSV y devuelve lista de productos (sin duplicados por URL)."""
    productos: list[dict] = []
    seen_urls: set[str] = set()

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        for row in reader:
            id_url = row.get("Identificador de URL", "").strip()
            nombre = row.get("Nombre", "").strip()
            sku = row.get("SKU", "").strip()
            marca = row.get("Marca", "").strip()
            categoria = row.get("Categorías", "").strip()

            if not id_url or not nombre:
                continue

            if id_url not in seen_urls:
                seen_urls.add(id_url)
                productos.append({
                    "id_url": id_url,
                    "nombre": nombre,
                    "sku": sku,
                    "marca": marca,
                    "categoria": categoria,
                })

    return productos


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    productos = read_products(CSV_PATH)
    print(f"=== JGO Armería - Descargador de Imágenes ===")
    print(f"Productos únicos (por URL): {len(productos)}")
    print(f"URLs mapeadas: {len(URL_MAP)}")
    print(f"Directorio: {OUTPUT_DIR}")
    print()

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    })

    stats: dict[str, int] = {"exacta": 0, "aproximada": 0, "generica": 0, "placeholder": 0, "error": 0}
    mapping_rows: list[dict] = []

    for prod in productos:
        id_url = prod["id_url"]
        nombre = prod["nombre"]
        sku = prod["sku"]
        filename = f"{id_url}.jpg"
        output_path = os.path.join(OUTPUT_DIR, filename)

        # Si ya existe, contar y seguir
        if os.path.exists(output_path) and os.path.getsize(output_path) > 2048:
            status = "existente"
            tipo = "exacta"
            stats["exacta"] += 1
            mapping_rows.append({
                "SKU": sku,
                "url_identifier": id_url,
                "filename": filename,
                "tipo": tipo,
                "status": status,
                "producto": nombre,
            })
            continue

        if id_url in URL_MAP:
            url, tipo = URL_MAP[id_url]
            print(f"  Descargando: {nombre} [{tipo}]...", end=" ", flush=True)
            ok = download_image(session, url, output_path)
            if ok:
                kb = os.path.getsize(output_path) // 1024
                print(f"OK ({kb} KB)")
                stats[tipo] += 1
                mapping_rows.append({
                    "SKU": sku,
                    "url_identifier": id_url,
                    "filename": filename,
                    "tipo": tipo,
                    "status": "descargada",
                    "producto": nombre,
                })
            else:
                print("FAIL -> placeholder")
                stats["error"] += 1
                if create_placeholder(output_path, nombre, sku):
                    stats["placeholder"] += 1
                mapping_rows.append({
                    "SKU": sku,
                    "url_identifier": id_url,
                    "filename": filename,
                    "tipo": "placeholder (fallback)",
                    "status": "placeholder",
                    "producto": nombre,
                })
        else:
            # Sin URL mapeada → placeholder
            print(f"  Placeholder: {nombre}")
            if create_placeholder(output_path, nombre, sku):
                stats["placeholder"] += 1
            mapping_rows.append({
                "SKU": sku,
                "url_identifier": id_url,
                "filename": filename,
                "tipo": "placeholder",
                "status": "placeholder",
                "producto": nombre,
            })

        # Pequeña pausa entre descargas
        if id_url in URL_MAP:
            time.sleep(0.3)

    # ── Escribir mapping CSV ──────────────────────────────────────────────
    map_headers = ["SKU", "url_identifier", "filename", "tipo", "status", "producto"]
    with open(MAPPING_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=map_headers, delimiter=";", quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(mapping_rows)

    # ── Resumen ───────────────────────────────────────────────────────────
    total = len(productos)
    print()
    print("=" * 55)
    print("  RESUMEN")
    print("=" * 55)
    print(f"  Exactas:      {stats['exacta']:3d} / {total}")
    print(f"  Aproximadas:  {stats['aproximada']:3d} / {total}")
    print(f"  Genéricas:    {stats['generica']:3d} / {total}")
    print(f"  Placeholders: {stats['placeholder']:3d} / {total}")
    print(f"  Errores:      {stats['error']:3d} / {total}")
    print()
    real = stats["exacta"] + stats["aproximada"] + stats["generica"]
    print(f"  Con imagen real: {real}/{total}")
    print(f"  Con placeholder: {stats['placeholder']}/{total}")
    print()
    print(f"  Mapping: {MAPPING_CSV}")
    print()

    # Productos que necesitan imagen manual
    faltantes = [r for r in mapping_rows if r["status"] in ("placeholder",)]
    if faltantes:
        print(f"  Productos SIN imagen real ({len(faltantes)}):")
        for r in faltantes:
            print(f"    - {r['producto']} ({r['url_identifier']})")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        import shutil
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
            print(f"Directorio eliminado: {OUTPUT_DIR}")
        if os.path.exists(MAPPING_CSV):
            os.remove(MAPPING_CSV)
            print(f"Mapping eliminado: {MAPPING_CSV}")
    else:
        main()
