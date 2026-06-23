#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
processor.py — Web app backend for JGO Armeria.
Wraps unificar_productos.py and gestionar_tiendanube.py with
dynamic paths for the Flask interface.
"""
import os
import sys
import csv
import json
import re
import shutil
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ─────────────────────────────────────────────────────────
# INIT — call this first to set the working directory
# ─────────────────────────────────────────────────────────

WORK_DIR = None
UPLOAD_DIR = None
OUTPUT_DIR = None
DATA_DIR = None

_REQUIRED_DATA = {
    "productos_jgo_armeria.csv": "Catálogo base de productos",
}

def init(app_root=None):
    """Initialize processor with the given application root directory."""
    global WORK_DIR, UPLOAD_DIR, OUTPUT_DIR, DATA_DIR

    if app_root:
        WORK_DIR = Path(app_root)
    else:
        WORK_DIR = Path(__file__).parent.resolve()

    UPLOAD_DIR = WORK_DIR / "uploads"
    OUTPUT_DIR = WORK_DIR / "outputs"
    DATA_DIR = WORK_DIR  # data files are in the root

    # Ensure dirs exist
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Check for required data files
    missing = []
    for fname in _REQUIRED_DATA:
        if not (WORK_DIR / fname).exists():
            missing.append(fname)
    if missing:
        for m in missing:
            print(f"[warn] Required file not found: {m}")

    return WORK_DIR


# ─────────────────────────────────────────────────────────
# FILE DISCOVERY — find uploaded files by type
# ─────────────────────────────────────────────────────────

def discover_uploaded_files():
    """Scan uploads dir and classify files by type."""
    if not UPLOAD_DIR or not UPLOAD_DIR.exists():
        return {"taurus_pdf": None, "bersa_pdf": None, "bersa_shop_xlsx": None, "lube_pdf": None, "unknown": []}

    files = list(UPLOAD_DIR.iterdir())
    result = {"taurus_pdf": None, "bersa_pdf": None, "bersa_shop_xlsx": None, "lube_pdf": None, "unknown": []}

    for f in files:
        if not f.is_file() or f.name.startswith('.'):
            continue
        name_upper = f.name.upper()
        ext = f.suffix.lower()

        if ext == '.pdf':
            if 'TAURUS' in name_upper:
                result['taurus_pdf'] = str(f)
            elif 'BERSA' in name_upper and 'SHOP' not in name_upper:
                result['bersa_pdf'] = str(f)
            elif 'LUBE' in name_upper:
                result['lube_pdf'] = str(f)
            else:
                result['unknown'].append(str(f))

        elif ext == '.xlsx':
            if 'BERSA' in name_upper and 'SHOP' in name_upper:
                result['bersa_shop_xlsx'] = str(f)
            else:
                result['unknown'].append(str(f))

        else:
            result['unknown'].append(str(f))

    return result


def get_upload_summary():
    """Return a human-readable dict of what files are available."""
    files = discover_uploaded_files()
    summary = {}
    for key, label in [
        ("taurus_pdf", "Taurus (PDF)"),
        ("bersa_pdf", "Bersa (PDF)"),
        ("bersa_shop_xlsx", "Bersa Shop (XLSX)"),
        ("lube_pdf", "Lube (PDF)"),
    ]:
        path = files.get(key)
        if path:
            fpath = Path(path)
            summary[key] = {
                "name": fpath.name,
                "size": fpath.stat().st_size,
                "modified": datetime.fromtimestamp(fpath.stat().st_mtime).isoformat(),
            }
        else:
            summary[key] = None

    summary["unknown"] = [Path(p).name for p in files.get("unknown", [])]
    return summary


def clear_uploads():
    """Remove all uploaded files."""
    if UPLOAD_DIR and UPLOAD_DIR.exists():
        for f in UPLOAD_DIR.iterdir():
            if f.is_file():
                f.unlink()
        return True
    return False


# ─────────────────────────────────────────────────────────
# RUN UNIFICATION — wraps unificar_productos.py logic
# ─────────────────────────────────────────────────────────

def run_unification():
    """
    Run the full product unification pipeline.
    Returns a dict with results: success, log, output_csv, stats.
    """
    log_lines = []
    def log(msg):
        log_lines.append(msg)
        print(msg)

    log("=" * 60)
    log("UNIFICADOR DE PRODUCTOS - JGO Armeria (Web)")
    log("=" * 60)

    # --- Step 0: Map uploaded files to expected locations ---
    uploads = discover_uploaded_files()

    # We'll create a temporary working directory with symlinks (or copies on Windows)
    # mapping uploaded files to the names the scripts expect
    import tempfile
    work_dir = Path(tempfile.mkdtemp(prefix="jgo_unify_"))
    log(f"Working directory: {work_dir}")

    # Copy required data files
    for fname in ["productos_jgo_armeria.csv"]:
        src = WORK_DIR / fname
        if src.exists():
            shutil.copy2(src, work_dir / fname)
            log(f"  Copied: {fname}")
        else:
            log(f"  WARN: {fname} not found — some products may be missing")

    # Map uploaded files to expected locations
    file_mappings = {
        "taurus_pdf": "listas/LISTA DE PRECIOS - TAURUS ABRIL 2026.pdf",
        "bersa_pdf": "listas/LISTA DE PRECIOS BERSA PISTOLAS Y ACCESORIOS - MI - JUNIO 2026.pdf",
        "bersa_shop_xlsx": "listas/LISTA BERSA SHOP JUNIO 2026 - V1.xlsx",
        "lube_pdf": "listas/LISTAS DE PRECIOS LUBE JUNIO - 9.6.2026.pdf",
    }

    listas_dir = work_dir / "listas"
    listas_dir.mkdir(exist_ok=True)

    for key, expected_rel in file_mappings.items():
        uploaded = uploads.get(key)
        if uploaded:
            dest = work_dir / expected_rel
            shutil.copy2(uploaded, dest)
            log(f"  Uploaded → {expected_rel}")
        else:
            log(f"  SKIP: {key} — no file uploaded")

    # --- Monkey-patch: import and run with custom PROJECT ---
    # We need to temporarily modify sys.path and patch the module
    original_cwd = os.getcwd()
    os.chdir(str(work_dir))

    try:
        # Import the unifier (it sets PROJECT at import time)
        # We use importlib to reload with a custom PROJECT
        import importlib
        import unificar_productos as up_mod

        # Override the PROJECT path
        up_mod.PROJECT = str(work_dir)

        # --- Step 1: Load base products ---
        log("\n[1/6] Cargar productos base")
        try:
            productos = up_mod.cargar_productos_base()
        except Exception as e:
            log(f"  ERROR: {e}")
            productos = []

        # If no base products, create empty catalog
        if not productos:
            log("  WARN: No base products loaded. Creating empty catalog.")
            # Try reading from the actual data dir
            csv_path = WORK_DIR / "productos_jgo_armeria.csv"
            if csv_path.exists():
                shutil.copy2(csv_path, work_dir / "productos_jgo_armeria.csv")
                try:
                    import importlib
                    importlib.reload(up_mod)
                    up_mod.PROJECT = str(work_dir)
                    productos = up_mod.cargar_productos_base()
                except:
                    pass

        log(f"  -> {len(productos)} productos cargados")

        # --- Step 2: Taurus prices ---
        log("\n[2/6] Extraer precios Taurus (PDF)")
        try:
            precios_taurus = up_mod.extraer_precios_taurus()
        except Exception as e:
            log(f"  Error: {e}")
            precios_taurus = {}

        # --- Step 3: Bersa prices ---
        log("\n[3/6] Extraer precios Bersa (PDF)")
        try:
            precios_bersa = up_mod.extraer_precios_bersa()
        except Exception as e:
            log(f"  Error: {e}")
            precios_bersa = []

        # --- Step 4: Bersa Shop ---
        log("\n[4/6] Extraer productos Bersa Shop (XLSX)")
        try:
            bersa_shop = up_mod.extraer_bersa_shop()
        except Exception as e:
            log(f"  Error: {e}")
            bersa_shop = []

        # --- Step 5: Assign prices and build catalog ---
        log("\n[5/6] Asignar precios y completar datos")
        productos = up_mod.assign_prices(productos, precios_taurus, precios_bersa)

        productos_final = []
        for p in productos:
            nombre = p.get('Nombre', '')
            marca = up_mod.normalize_marca(p.get('Marca', ''))
            url = p.get('Identificador de URL', up_mod.slugify(nombre))
            precio = p.get('Precio', '')
            sku = p.get('SKU', '')
            desc = p.get('Descripcion', nombre)
            cats = p.get('Categorías', '')
            tags = p.get('Tags', up_mod.slugify(marca))

            # Fill empty fields
            if not cats:
                cat = 'Armas > Pistolas'
                if any(x in nombre.lower() for x in ['escopet', 'a300', 'a400', '1301', 'brxi']):
                    cat = 'Armas > Escopetas'
                elif any(x in nombre.lower() for x in ['revolver', 'm8', 'm9', 'm4', 'm6', 'm3']):
                    cat = 'Armas > Revolveres'
            else:
                cat = cats

            tp = up_mod.make_tn_product(nombre, url, cat, precio, marca, desc, tags=tags, sku=sku)
            for prop in ['Nombre de propiedad 1', 'Valor de propiedad 1',
                         'Nombre de propiedad 2', 'Valor de propiedad 2',
                         'Nombre de propiedad 3', 'Valor de propiedad 3']:
                if p.get(prop):
                    tp[prop] = p[prop]
            productos_final.append(tp)

        # 5b. Add Bersa Shop products
        shop_added = 0
        for item in bersa_shop:
            codigo = item['codigo']
            desc = item['descripcion']
            marca = item['marca']
            precio = item['precio']
            categoria = item['categoria']

            if any(p.get('SKU') == codigo for p in productos_final):
                continue
            url = up_mod.slugify(f"{up_mod.slugify(marca)}-{up_mod.slugify(desc[:40])}")
            if any(p.get('Identificador de URL') == url for p in productos_final):
                continue

            nombre = f"{marca} {desc}" if not desc.startswith(marca) else desc
            if len(nombre) > 120:
                nombre = nombre[:117] + "..."

            tp = up_mod.make_tn_product(nombre, url, categoria, precio, marca, desc,
                                         tags=up_mod.slugify(marca), sku=codigo, mpn=codigo)
            productos_final.append(tp)
            shop_added += 1

        log(f"  -> Agregados {shop_added} productos de Bersa Shop")

        # --- Step 6: Deduplicate ---
        log("\n[6/6] Deduplicacion final")
        productos_final = up_mod.deduplicar(productos_final)
        productos_final.sort(key=lambda p: (p.get('Categorías', ''), p.get('Nombre', '')))

        # --- Write output CSV ---
        output_path = work_dir / "productos_jgo_armeria_unificado.csv"
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=up_mod.HEADERS, delimiter=';',
                                    quotechar='"', quoting=csv.QUOTE_ALL,
                                    extrasaction='ignore')
            writer.writeheader()
            writer.writerows(productos_final)

        # --- Copy to outputs dir ---
        output_final = OUTPUT_DIR / "productos_jgo_armeria_unificado.csv"
        shutil.copy2(output_path, output_final)

        # Also copy to root for backward compat
        shutil.copy2(output_path, WORK_DIR / "productos_jgo_armeria_unificado.csv")

        # --- Generate report ---
        total = len(productos_final)
        con_precio = sum(1 for p in productos_final if p.get('Precio'))
        sin_precio = [p for p in productos_final if not p.get('Precio')]
        cats_out = defaultdict(int)
        for p in productos_final:
            cats_out[p.get('Categorías', 'Sin categoría')] += 1

        log(f"\n{'=' * 60}")
        log(f"ARCHIVO GENERADO: {output_final}")
        log(f"Total productos: {total}")
        log(f"Con precio: {con_precio}/{total} ({con_precio*100//total}%)")
        log(f"\nPor categoria:")
        for c, n in sorted(cats_out.items(), key=lambda x: -x[1]):
            log(f"  {c}: {n}")

        report = {
            'total_productos': total,
            'con_precio': con_precio,
            'sin_precio': len(sin_precio),
            'por_categoria': dict(cats_out),
            'timestamp': datetime.now().isoformat(),
            'productos_sin_precio': [
                {'nombre': p['Nombre'], 'sku': p.get('SKU', ''), 'marca': p.get('Marca', '')}
                for p in sin_precio
            ]
        }

        report_path = OUTPUT_DIR / "reporte_unificacion.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # Also to root
        shutil.copy2(report_path, WORK_DIR / "reporte_unificacion.json")

        result = {
            "success": True,
            "log": log_lines,
            "output_csv": str(output_final),
            "total": total,
            "con_precio": con_precio,
            "sin_precio": len(sin_precio),
            "por_categoria": dict(cats_out),
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"\nERROR CRITICO: {e}")
        log(tb)
        result = {
            "success": False,
            "log": log_lines,
            "error": str(e),
            "traceback": tb,
        }

    finally:
        os.chdir(original_cwd)
        # Clean up temp dir
        try:
            shutil.rmtree(work_dir)
        except:
            pass

    return result


# ─────────────────────────────────────────────────────────
# GET OUTPUT FILES
# ─────────────────────────────────────────────────────────

def list_outputs():
    """List generated output files."""
    if not OUTPUT_DIR or not OUTPUT_DIR.exists():
        return []
    files = []
    for f in OUTPUT_DIR.iterdir():
        if f.is_file():
            files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return sorted(files, key=lambda x: x["name"])


def get_last_report():
    """Read the last unification report JSON."""
    report_path = WORK_DIR / "reporte_unificacion.json"
    if report_path.exists():
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return None


# ─────────────────────────────────────────────────────────
# TIENDA NUBE SYNC — wraps gestionar_tiendanube.py
# ─────────────────────────────────────────────────────────

def tn_sync_prices(sync_csv=None, token=None, store_id=None):
    """
    Sync prices from a sync CSV to Tienda Nube.
    If sync_csv is provided, reads from that file.
    Otherwise, uses productos_sync.csv in OUTPUT_DIR or WORK_DIR.
    """
    log_lines = []
    def log(msg):
        log_lines.append(msg)
        print(msg)

    log("=" * 60)
    log("SINCRONIZACION DE PRECIOS - Tienda Nube")
    log("=" * 60)

    # Patch gestionar_tiendanube module
    import gestionar_tiendanube as tn_mod

    if token:
        tn_mod.TN_TOKEN = token
    if store_id:
        tn_mod.TN_STORE_ID = store_id
        tn_mod.TN_API_BASE = f"https://api.tiendanube.com/v1/{store_id}"

    if not sync_csv:
        # Try outputs first, then root
        sync_candidates = [
            OUTPUT_DIR / "productos_sync.csv",
            WORK_DIR / "productos_sync.csv",
        ]
        sync_csv = None
        for c in sync_candidates:
            if c.exists():
                sync_csv = str(c)
                break

    if not sync_csv:
        log("ERROR: No sync file found. Run 'Export IDs' first.")
        return {"success": False, "log": log_lines, "error": "No sync file found"}

    log(f"Sync file: {sync_csv}")

    # Read sync file
    try:
        with open(sync_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        log(f"ERROR reading sync file: {e}")
        return {"success": False, "log": log_lines, "error": str(e)}

    total = len(rows)
    updates = 0
    errors = 0
    log(f"Total rows: {total}")

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

        # Fetch product to get variant ID
        product = tn_mod.tn_request("GET", f"/products/{tn_id}")
        if not product or not product.get('variants'):
            log(f"  [{i}/{total}] ERROR: No se pudo obtener producto {tn_id}")
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
                log(f"  [{i}/{total}] Precio invalido: {new_price}")
                continue

        if new_stock:
            try:
                variant_update["stock"] = int(float(new_stock))
            except:
                pass

        if variant_update:
            variant_update["id"] = variant_id
            result = tn_mod.tn_request("PUT", f"/products/{tn_id}", data={
                "variants": [variant_update]
            })

            if result:
                updates += 1
                changes = []
                if new_price: changes.append(f"precio ${new_price}")
                if new_stock: changes.append(f"stock {new_stock}")
                log(f"  [{i}/{total}] OK: {name[:40]} -> {', '.join(changes)}")
            else:
                errors += 1
                log(f"  [{i}/{total}] ERROR: {name[:40]}")

        time.sleep(tn_mod.RATE_LIMIT_DELAY)

    log(f"\n Sincronización completada: {updates} actualizados, {errors} errores")
    return {"success": errors == 0, "log": log_lines, "updates": updates, "errors": errors}


def tn_export_ids(token=None, store_id=None):
    """
    Download product IDs from TN and generate mapping + sync file.
    """
    log_lines = []
    def log(msg):
        log_lines.append(msg)
        print(msg)

    log("=" * 60)
    log("EXPORTAR IDs - Tienda Nube")
    log("=" * 60)

    import gestionar_tiendanube as tn_mod

    if token:
        tn_mod.TN_TOKEN = token
    if store_id:
        tn_mod.TN_STORE_ID = store_id
        tn_mod.TN_API_BASE = f"https://api.tiendanube.com/v1/{store_id}"

    log("Descargando productos de Tienda Nube...")
    products = tn_mod.paginate("/products")

    if not products:
        log("No se pudieron obtener productos.")
        return {"success": False, "log": log_lines, "error": "No products from TN API"}

    log(f"Obtenidos {len(products)} productos.")

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
    mapping_path = OUTPUT_DIR / "mapping_tn_ids.csv"
    with open(mapping_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=map_headers)
        writer.writeheader()
        writer.writerows(mapping)

    # Also copy to root
    shutil.copy2(mapping_path, WORK_DIR / "mapping_tn_ids.csv")

    # Build sync file
    sync_rows = []
    for m in mapping:
        sync_rows.append({
            'tn_id': m['tn_id'],
            'sku': m['sku'],
            'nombre': m['nombre'],
            'marca': m['marca'],
            'precio_actual': m['precio'],
            'stock_actual': m['stock'],
            'precio_nuevo': '',
            'stock_nuevo': '',
        })

    sync_headers = ['tn_id', 'sku', 'nombre', 'marca', 'precio_actual', 'stock_actual', 'precio_nuevo', 'stock_nuevo', 'notas']
    sync_path = OUTPUT_DIR / "productos_sync.csv"
    with open(sync_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=sync_headers)
        writer.writeheader()
        writer.writerows(sync_rows)

    shutil.copy2(sync_path, WORK_DIR / "productos_sync.csv")

    log(f"\nMapping guardado: {mapping_path}")
    log(f"Sync file: {sync_path}")
    log(f"{len(mapping)} productos mapeados")

    return {"success": True, "log": log_lines, "total": len(mapping)}


def tn_get_stats(token=None, store_id=None):
    """Get product count and basic stats from Tienda Nube."""
    import gestionar_tiendanube as tn_mod

    if token:
        tn_mod.TN_TOKEN = token
    if store_id:
        tn_mod.TN_STORE_ID = store_id
        tn_mod.TN_API_BASE = f"https://api.tiendanube.com/v1/{store_id}"

    try:
        products = tn_mod.paginate("/products")
        if products is None:
            return {"error": "Could not connect to Tienda Nube API"}
        total = len(products)
        published = sum(1 for p in products if p.get('published'))
        with_price = sum(1 for p in products if p.get('variants') and p['variants'][0].get('price'))
        return {
            "total": total,
            "published": published,
            "with_price": with_price,
            "success": True,
        }
    except Exception as e:
        return {"error": str(e), "success": False}
