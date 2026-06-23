#!/usr/bin/env python3
"""Import CSV products to Tienda Nube with correct category IDs."""
import csv, json, sys, time, urllib.request, urllib.error, re

TN_BASE = 'https://api.tiendanube.com/v1/6696461'
TN_AUTH = 'bearer 8ae716d86bdc3e6bd23915943d6b7de233ab7f6b'
TN_UA = 'HeavenIntegration/1.0 (lucas@heaven.com.ar)'

CATEGORIES = {
    'Armas > Pistolas': 38714848,
    'Armas > Revolveres': 38714857,
    'Armas > Escopetas': 38714868,
    'Armas > Carabinas y Rifles': 38714846,
    'Linternas': 39479653,
    'Proteccion Auditiva': 39479654,
    'Proteccion Auditiva': 39479654,
    'Municiones y Snap Caps': 39479655,
    'Miras y Red Dots': 39479656,
    'Cuchillos y Navajas': 39479657,
    'Merchandising': 39479658,
    'Equipamiento > Seguridad Industrial': 39479660,
    'Equipamiento': 39479659,
}
ACCESORIOS_ID = 39479652

def get_cat_id(cat_str):
    cat_str = cat_str.strip().replace('Accesorios > AR-15 / BAR9', 'Accesorios')
    cat_str = cat_str.strip().replace('Accesorios > Repuestos y Partes', 'Accesorios')
    cat_str = cat_str.strip().replace('Accesorios > Canik', 'Accesorios')
    cat_str = cat_str.strip().replace('Accesorios', 'Accesorios')
    return CATEGORIES.get(cat_str, ACCESORIOS_ID)

def tn_post(path, data):
    h = {'Authentication': TN_AUTH, 'User-Agent': TN_UA, 'Content-Type': 'application/json'}
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(TN_BASE + path, data=body, headers=h, method='POST')
    try:
        with urllib.request.urlopen(req) as r:
            t = r.read().decode('utf-8')
            return json.loads(t)
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8')[:300]
        return {'_error': 'HTTP ' + str(e.code) + ': ' + text}

CSV = r'C:\Areas\02_Agencia\Clientes\JGO Armeria\productos_jgo_armeria_unificado.csv'
with open(CSV, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f, delimiter=';'))

total = len(rows)
print('Importing', total, 'products to Tienda Nube...')
ok = 0
err = 0

for i, row in enumerate(rows, 1):
    name = (row.get('Nombre') or '')[:200]
    desc = (row.get('Descripcion') or name)[:2000]
    marca = row.get('Marca', '')
    sku = row.get('SKU', '')
    cat_str = row.get('Categorias', '')
    cat_id = get_cat_id(cat_str)

    price = row.get('Precio', '0').replace(',', '.')
    try: price_val = float(price)
    except: price_val = 0

    url_id = row.get('Identificador de URL', '') or re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    stock = int(float(row.get('Stock', '5')))
    peso = row.get('Peso (kg)', '1')

    payload = {
        'name': {'es': name},
        'description': {'es': desc},
        'handle': {'es': url_id},
        'brand': marca,
        'published': True,
        'free_shipping': False,
        'requires_shipping': True,
        'categories': [cat_id],
        'tags': row.get('Tags', ''),
        'variants': [{
            'price': str(price_val),
            'stock': stock,
            'sku': sku,
            'weight': peso,
            'height': row.get('Alto (cm)', '15'),
            'width': row.get('Ancho (cm)', '10'),
            'depth': row.get('Profundidad (cm)', '30'),
        }],
    }

    result = tn_post('/products', payload)
    if result and result.get('id'):
        ok += 1
        sys.stdout.write('\r ' + str(i) + '/' + str(total) + ' OK: ' + name[:50] + ' (ID: ' + str(result['id']) + ', cat: ' + str(cat_id) + ')   ')
    else:
        err += 1
        sys.stdout.write('\r ' + str(i) + '/' + str(total) + ' ERROR: ' + name[:50] + ' - ' + str(result.get('_error',''))[:50] + '   ')
    sys.stdout.flush()
    time.sleep(1.5)

print()
print()
print('OK:', ok, '- ERRORES:', err)
