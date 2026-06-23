#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GESTOR DE TIENDA NUBE -- JGO Armería
====================================
Fases:
  1. Listar productos actuales
  2. Borrar todos los productos (limpieza)
  3. Importar productos desde CSV
  4. Descargar IDs de TN y generar mapping
  5. Sincronizar precios desde listas de proveedores

Usage:
    python gestionar_tiendanube.py --list           # Listar productos actuales
    python gestionar_tiendanube.py --clear           # Borrar todo
    python gestionar_tiendanube.py --import          # Importar CSV
    python gestionar_tiendanube.py --export-ids      # Descargar mapping SKU->TN ID
    python gestionar_tiendanube.py --sync-prices archivo.csv   # Sincronizar precios
"""

import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
import re
import unicodedata

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

PROJECT = r"C:\Areas\02_Agencia\Clientes\JGO Armeria"
TN_STORE_ID = "6696461"
TN_TOKEN = "8ae716d86bdc3e6bd23915943d6b7de233ab7f6b"
TN_USER_AGENT = "HeavenIntegration/1.0 (lucas@heaven.com.ar)"
TN_API_BASE = f"https://api.tiendanube.com/v1/{TN_STORE_ID}"

# Rate limiting
RATE_LIMIT_DELAY = 1.5

# Force mode (skip confirmations)
FORCE_MODE = '--yes' in sys.argv or '-y' in sys.argv

# Mapping CSV path
PRODUCTS_CSV = os.path.join(PROJECT, "productos_jgo_armeria_unificado.csv")
MAPPING_CSV = os.path.join(PROJECT, "mapping_tn_ids.csv")
SYNC_FILE = os.path.join(PROJECT, "productos_sync.csv")

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def tn_request(method, path, data=None, retries=3):
    """Make a request to the TN API."""
    url = f"{TN_API_BASE}{path}"
    headers = {
        "Authentication": f"bearer {TN_TOKEN}",
        "User-Agent": TN_USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(data).encode('utf-8') if data else None

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req) as resp:
                text = resp.read().decode('utf-8')
                remaining = int(resp.headers.get('x-rate-limit-remaining', 1))
                if remaining < 5:
                    print(f"  [rate-limit] {remaining} remaining, pausando...")
                    time.sleep(3)
                # DELETE returns 200 with empty body on success
                if not text.strip():
                    return {"_deleted": True}
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as e:
            err_text = e.read().decode('utf-8') if e.fp else ''
            if e.code == 429:
                wait = int(e.headers.get('Retry-After', 10))
                print(f"  [429] Rate limited, esperando {wait}s...")
                time.sleep(wait)
                continue
            if e.code == 404 and attempt < retries - 1:
                time.sleep(1)
                continue
            print(f"  [HTTP {e.code}] {err_text[:200]}")
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"  [Error] {e}")
            return None

def paginate(path, params=""):
    """Fetch all pages from a TN endpoint."""
    results = []
    page = 1
    while True:
        url = f"{path}?page={page}&per_page=100{params}"
        data = tn_request("GET", url)
        if data is None:
            break
        if isinstance(data, list):
            results.extend(data)
            if len(data) < 100:
                break
        else:
            if results:
                break
            return data
        page += 1
        time.sleep(RATE_LIMIT_DELAY)
    return results

def confirm(msg):
    """Ask for confirmation, unless FORCE_MODE."""
    if FORCE_MODE:
        return True
    safe_msg = msg.replace('\U0001f6ab', '').replace('', '')
    r = input(f"\n[!] {msg}\n  Escribi 'si' para confirmar: ").strip().lower()
    return r == 'si'

def slugify(text):
    text = text.lower().strip()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

# ---------------------------------------------------------
# FASE 1: LISTAR PRODUCTOS ACTUALES
# ---------------------------------------------------------

def cmd_list():
    print("\n[LIST] Listando productos actuales en Tienda Nube...")
    products = paginate("/products")
    if not products:
        print("  No hay productos o error de conexión.")
        return

    print(f"\n  Total: {len(products)} productos")
    print(f"\n  {'ID':>12} | {'SKU':<15} | {'Nombre':<50} | {'Precio':<10}")
    print(f"  {'-'*12}-+-{'-'*15}-+-{'-'*50}-+-{'-'*10}")
    for p in products:
        sku = ''
        price = ''
        if p.get('variants'):
            sku = p['variants'][0].get('sku', '') or ''
            price = str(p['variants'][0].get('price', '') or '')
        name = p.get('name', {}).get('es', '') or p.get('name', '')
        print(f"  {p['id']:>12} | {sku:<15} | {name[:50]:<50} | {price:<10}")

    return products

# ---------------------------------------------------------
# FASE 2: BORRAR TODOS LOS PRODUCTOS
# ---------------------------------------------------------

def cmd_clear():
    print("\n[BIN]  Preparando limpieza de Tienda Nube...")
    products = paginate("/products")
    if not products:
        print("  No hay productos para borrar.")
        return

    total = len(products)
    print(f"  Se borrarán {total} productos.")

    for i, p in enumerate(products, 1):
        pid = p['id']
        name = p.get('name', {}).get('es', p.get('name', ''))
        result = tn_request("DELETE", f"/products/{pid}")
        if result is not None:
            print(f"  [{i}/{total}] OK: {name[:40]} (ID: {pid})")
        else:
            print(f"  [{i}/{total}] ERROR: {name[:40]} (ID: {pid})")
        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n Limpieza completada. {total} productos eliminados.")

# ---------------------------------------------------------
# FASE 3: IMPORTAR PRODUCTOS DESDE CSV
# ---------------------------------------------------------

def csv_to_tn_product(row):
    """Convert a CSV row to TN API product structure."""
    name = row.get('Nombre', '')
    url_id = row.get('Identificador de URL', slugify(name))
    desc = row.get('Descripción', name)
    marca = row.get('Marca', '')
    price = row.get('Precio', '0')
    stock = row.get('Stock', '5')
    sku = row.get('SKU', '')
    tags = row.get('Tags', '')
    seo_title = row.get('Título para SEO', name)
    seo_desc = row.get('Descripción para SEO', desc)
    categoria = row.get('Categorías', '')
    peso = row.get('Peso (kg)', '1')
    alto = row.get('Alto (cm)', '15')
    ancho = row.get('Ancho (cm)', '10')
    prof = row.get('Profundidad (cm)', '30')
    mpn = row.get('MPN (Número de pieza del fabricante)', '')

    # Parse price
    try:
        price_val = float(price.replace(',', '.'))
    except:
        price_val = 0

    # Parse stock
    try:
        stock_val = int(float(stock))
    except:
        stock_val = 5

    # TN API accepts category as string (full path) or list
    # We'll pass the full category path string
    category_val = categoria.strip() if categoria else 'Armas > Pistolas'

    # Build product payload
    product = {
        "name": {"es": name[:200]},
        "description": {"es": desc[:2000]},
        "seo_title": {"es": seo_title[:120]},
        "seo_description": {"es": seo_desc[:250]},
        "handle": {"es": url_id},
        "brand": marca,
        "published": True,
        "free_shipping": False,
        "requires_shipping": True,
        "variants": [{
            "price": str(price_val),
            "promotional_price": None,
            "stock": stock_val,
            "sku": sku,
            "weight": peso,
            "height": alto,
            "width": ancho,
            "depth": prof,
            "barcode": "",
        }],
        "categories": [category_val] if category_val else [],
        "tags": tags,
        "attributes": [],
    }

    # MPN
    if mpn:
        product["variants"][0]["mpn"] = mpn

    return product

def cmd_import():
    """Import products from CSV into TN."""
    if not os.path.exists(PRODUCTS_CSV):
        print(f"  ERROR: No se encuentra {PRODUCTS_CSV}")
        return

    with open(PRODUCTS_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)

    total = len(rows)
    print(f"\n[BOX] Importando {total} productos a Tienda Nube...")

    success = 0
    errors = 0
    for i, row in enumerate(rows, 1):
        name = row.get('Nombre', '')
        sku = row.get('SKU', '')

        product = csv_to_tn_product(row)
        result = tn_request("POST", "/products", data=product)

        if result and result.get('id'):
            success += 1
            tn_id = result['id']
            print(f"  [{i}/{total}] OK: {name[:40]} (TN ID: {tn_id}, SKU: {sku})")
        else:
            errors += 1
            print(f"  [{i}/{total}] ERROR: {name[:40]} (SKU: {sku})")

        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n Importación completada: {success} OK, {errors} errores")

# ---------------------------------------------------------
# FASE 4: EXPORTAR MAPPING SKU -> TN ID
# ---------------------------------------------------------

def cmd_export_ids():
    """Download products from TN and build SKU->TN ID mapping."""
    print("\n[IN] Descargando productos de Tienda Nube con IDs...")
    products = paginate("/products")

    if not products:
        print("  No se pudieron obtener productos.")
        return

    print(f"  Obtenidos {len(products)} productos.")

    # Build mapping
    mapping = []
    for p in products:
        name = p.get('name', {}).get('es', p.get('name', ''))
        tn_id = p['id']
        variants = p.get('variants', [])
        sku = variants[0].get('sku', '') if variants else ''
        price = variants[0].get('price', '') if variants else ''
        stock = variants[0].get('stock', '') if variants else ''
        brand = p.get('brand', '')
        categories = ' > '.join(p.get('categories', []))
        url = p.get('canonical_url', '')

        # Get attributes/properties
        props = {}
        for attr in p.get('attributes', []):
            if attr.get('name') and attr.get('value'):
                props[attr['name']] = attr['value']

        mapping.append({
            'tn_id': tn_id,
            'nombre': name,
            'sku': sku,
            'marca': brand,
            'precio': price,
            'stock': stock,
            'url': url,
            'categorias': categories,
            'propiedades': json.dumps(props, ensure_ascii=False),
        })

    # Write mapping CSV
    map_headers = ['tn_id', 'sku', 'nombre', 'marca', 'precio', 'stock', 'url', 'categorias', 'propiedades']
    with open(MAPPING_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=map_headers)
        writer.writeheader()
        writer.writerows(mapping)

    print(f"\n Mapping guardado en: {MAPPING_CSV}")
    print(f"   {len(mapping)} productos mapeados")

    # También crear el archivo de sync con formato simplificado para actualizar precios
    sync_rows = []
    for m in mapping:
        sync_rows.append({
            'tn_id': m['tn_id'],
            'sku': m['sku'],
            'nombre': m['nombre'],
            'marca': m['marca'],
            'precio_actual': m['precio'],
            'stock_actual': m['stock'],
            'precio_nuevo': '',  # para llenar manualmente o desde script
            'stock_nuevo': '',
        })

    sync_headers = ['tn_id', 'sku', 'nombre', 'marca', 'precio_actual', 'stock_actual', 'precio_nuevo', 'stock_nuevo', 'notas']
    with open(SYNC_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=sync_headers)
        writer.writeheader()
        writer.writerows(sync_rows)

    print(f" Archivo de sync guardado: {SYNC_FILE}")
    print(f"   Editá 'precio_nuevo' y 'stock_nuevo' y corré --sync-prices")

    return mapping

# ---------------------------------------------------------
# FASE 5: SINCRONIZAR PRECIOS
# ---------------------------------------------------------

def cmd_sync_prices(sync_file=None):
    """Sync prices from a sync CSV or from supplier lists."""
    if not sync_file:
        sync_file = SYNC_FILE

    if not os.path.exists(sync_file):
        print(f"  ERROR: No se encuentra {sync_file}")
        print(f"  Primero corré: python gestionar_tiendanube.py --export-ids")
        return

    print(f"\n[SYNC] Sincronizando precios desde: {sync_file}")

    with open(sync_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    updates = 0
    errors = 0
    for i, row in enumerate(rows, 1):
        tn_id = row.get('tn_id', '').strip()
        new_price = row.get('precio_nuevo', '').strip()
        new_stock = row.get('stock_nuevo', '').strip()
        sku = row.get('sku', '')
        name = row.get('nombre', '')

        if not tn_id or not tn_id.isdigit():
            continue
        if not new_price and not new_stock:
            continue

        # Build update payload
        payload = {"variants": [{"id": int(tn_id)}]}  # variant ID same as product for simple products
        # Actually we need to get the variant ID first
        # For simple products, the variant ID differs from product ID
        # Let's fetch the product first to get variant ID
        product = tn_request("GET", f"/products/{tn_id}")
        if not product or not product.get('variants'):
            print(f"  [{i}/{len(rows)}] ERROR: No se pudo obtener producto {tn_id}")
            errors += 1
            continue

        variant = product['variants'][0]
        variant_id = variant['id']
        variant_update = {}

        if new_price:
            try:
                price_val = float(new_price.replace(',', '.'))
                variant_update["price"] = str(price_val)
            except:
                print(f"  [{i}/{len(rows)}] Precio inválido: {new_price}")
                continue

        if new_stock:
            try:
                variant_update["stock"] = int(float(new_stock))
            except:
                pass

        if variant_update:
            variant_update["id"] = variant_id
            result = tn_request("PUT", f"/products/{tn_id}", data={
                "variants": [variant_update]
            })

            if result:
                updates += 1
                changes = []
                if new_price: changes.append(f"precio ${new_price}")
                if new_stock: changes.append(f"stock {new_stock}")
                print(f"  [{i}/{len(rows)}] OK: {name[:40]} -> {', '.join(changes)}")
            else:
                errors += 1
                print(f"  [{i}/{len(rows)}] ERROR: {name[:40]}")

        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n Sincronización completada: {updates} actualizados, {errors} errores")

# ---------------------------------------------------------
# FASE EXTRA: IMPORTAR PRECIOS DESDE LISTAS DE PROVEEDORES
# ---------------------------------------------------------

def cmd_build_sync_from_suppliers():
    """
    Match supplier product data (from PDFs/XLSX) with TN products
    to pre-fill the sync CSV with new prices.
    """
    if not os.path.exists(MAPPING_CSV):
        print("  ERROR: Primero ejecutá --export-ids")
        return

    # Load TN mapping
    tn_products = {}
    with open(MAPPING_CSV, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            sku = row.get('sku', '').strip()
            if sku:
                tn_products[sku.lower()] = row

    # Also match by name
    tn_by_name = {}
    for row in tn_products.values():
        name = row.get('nombre', '').lower()
        tn_by_name[name] = row

    # Load price references from the unifier
    ref_prices = {}
    try:
        with open(os.path.join(PROJECT, 'reporte_unificacion.json'), 'r') as f:
            pass  # reference data
    except:
        pass

    # Load the original CSV to get base prices
    base_prices = {}
    if os.path.exists(PRODUCTS_CSV):
        with open(PRODUCTS_CSV, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f, delimiter=';'):
                sku = row.get('SKU', '').strip()
                if sku:
                    base_prices[sku.lower()] = row.get('Precio', '')

    # Build sync file with current + reference prices
    sync_rows = []
    for sku_lower, tn_data in tn_products.items():
        current_price = tn_data.get('precio', '')
        ref_price = base_prices.get(sku_lower, '')

        sync_rows.append({
            'tn_id': tn_data['tn_id'],
            'sku': tn_data['sku'],
            'nombre': tn_data['nombre'],
            'marca': tn_data.get('marca', ''),
            'precio_actual': current_price,
            'stock_actual': tn_data.get('stock', ''),
            'precio_nuevo': ref_price if ref_price and ref_price != current_price else '',
            'stock_nuevo': '',
            'notas': 'Precio de referencia del catálogo unificado' if ref_price else '',
        })

    sync_headers = ['tn_id', 'sku', 'nombre', 'marca', 'precio_actual', 'stock_actual', 'precio_nuevo', 'stock_nuevo', 'notas']
    with open(SYNC_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=sync_headers)
        writer.writeheader()
        writer.writerows(sync_rows)

    print(f"\n Archivo de sync generado: {SYNC_FILE}")
    updated = sum(1 for r in sync_rows if r['precio_nuevo'])
    print(f"   {updated} productos con precio nuevo sugerido")
    print(f"   Revisalo, ajustá valores y ejecutá --sync-prices")

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == '--list':
        cmd_list()

    elif cmd == '--clear':
        products = cmd_list()
        if products and confirm("Borrar TODOS los productos de Tienda Nube?"):
            cmd_clear()

    elif cmd == '--import':
        if confirm("Importar todos los productos del CSV a Tienda Nube? (debe estar vacía)"):
            cmd_import()

    elif cmd == '--export-ids':
        cmd_export_ids()

    elif cmd == '--sync-prices':
        sync_file = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_sync_prices(sync_file)

    elif cmd == '--build-sync':
        cmd_build_sync_from_suppliers()

    elif cmd == '--full-reset':
        """Full workflow: clear -> import -> export-ids -> build-sync."""
        print("\n[SYNC] EJECUCIÓN COMPLETA: Limpiar + Importar + Mapear")
        products = cmd_list()
        if products and confirm("Borrar todo, importar catálogo y generar mapping?"):
            cmd_clear()
            print("\n" + "=" * 60)
            cmd_import()
            print("\n" + "=" * 60)
            cmd_export_ids()
            print("\n" + "=" * 60)
            cmd_build_sync_from_suppliers()
            print("\n" + "=" * 60)
            print(" Proceso completo finalizado.")
            print(f"   CSV de sincronización: {SYNC_FILE}")
            print("   Editá precios/stocks y ejecutá: python gestionar_tiendanube.py --sync-prices")

    else:
        print(f"Comando desconocido: {cmd}")
        print(__doc__)


if __name__ == '__main__':
    main()
