#!/usr/bin/env python3
"""Importar CSV unificado a Tienda Nube."""
import csv, json, sys, time, urllib.request, urllib.error, re, unicodedata

TN_BASE = 'https://api.tiendanube.com/v1/6696461'
TN_AUTH = 'bearer 8ae716d86bdc3e6bd23915943d6b7de233ab7f6b'
TN_UA = 'HeavenIntegration/1.0 (lucas@heaven.com.ar)'

def tn_post(path, data):
    h = {'Authentication': TN_AUTH, 'User-Agent': TN_UA, 'Content-Type': 'application/json'}
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(TN_BASE + path, data=body, headers=h, method='POST')
    try:
        with urllib.request.urlopen(req) as r:
            t = r.read().decode('utf-8')
            return json.loads(t)
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8')[:200]
        print(f'  [HTTP {e.code}] {text}')
        return None

CSV = r'C:\Areas\02_Agencia\Clientes\JGO Armeria\productos_jgo_armeria_unificado.csv'
with open(CSV, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f, delimiter=';'))

total = len(rows)
ok = 0
err = 0

for i, row in enumerate(rows, 1):
    name = (row.get('Nombre') or '')[:200]
    desc = (row.get('Descripcion') or name)[:2000]
    price = row.get('Precio', '0').replace(',', '.')
    try: price_val = float(price)
    except: price_val = 0
    sku = row.get('SKU', '')
    marca = row.get('Marca', '')
    cat = row.get('Categorias', 'Armas > Pistolas')
    url_id = row.get('Identificador de URL', '') or re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    stock = int(float(row.get('Stock', '5')))
    peso = row.get('Peso (kg)', '1')
    tags = row.get('Tags', '')

    payload = {
        "name": {"es": name},
        "description": {"es": desc},
        "handle": {"es": url_id},
        "brand": marca,
        "published": True,
        "free_shipping": False,
        "requires_shipping": True,
        "categories": [cat],
        "tags": tags,
        "variants": [{
            "price": str(price_val),
            "stock": stock,
            "sku": sku,
            "weight": peso,
            "height": row.get('Alto (cm)', '15'),
            "width": row.get('Ancho (cm)', '10'),
            "depth": row.get('Profundidad (cm)', '30'),
        }],
    }

    result = tn_post('/products', payload)
    if result and result.get('id'):
        ok += 1
        sys.stdout.write(f'\r  [{i}/{total}] OK: {name[:40]} (ID: {result[\"id\"]})   ')
    else:
        err += 1
        sys.stdout.write(f'\r  [{i}/{total}] ERROR: {name[:40]}                ')
    sys.stdout.flush()
    time.sleep(1.5)

print(f'\n\nOK: {ok}, ERRORES: {err}')
