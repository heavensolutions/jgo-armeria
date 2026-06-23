#!/usr/bin/env python3
"""Export TN product IDs and create mapping CSV + sync file."""
import csv, json, sys, time, urllib.request, urllib.error

TN_BASE = 'https://api.tiendanube.com/v1/6696461'
TN_AUTH = 'bearer 8ae716d86bdc3e6bd23915943d6b7de233ab7f6b'
TN_UA = 'HeavenIntegration/1.0 (lucas@heaven.com.ar)'
PROJECT = r'C:\Areas\02_Agencia\Clientes\JGO Armeria'

def tn_get(path):
    h = {'Authentication': TN_AUTH, 'User-Agent': TN_UA}
    req = urllib.request.Request(TN_BASE + path, headers=h)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

def paginate(path):
    results = []
    page = 1
    while True:
        data = tn_get(path + '?page={}&per_page=100'.format(page))
        if not data: break
        results.extend(data)
        if len(data) < 100: break
        page += 1
        time.sleep(1.5)
    return results

print('Downloading products from TN...')
products = paginate('/products')
print('Got {} products'.format(len(products)))

# Build mapping
mapping = []
sync_rows = []
for p in products:
    name = p.get('name', {}).get('es', '') or ''
    tn_id = p['id']
    variants = p.get('variants', [])
    v = variants[0] if variants else {}
    sku = v.get('sku', '') or ''
    price = v.get('price', '') or ''
    stock = v.get('stock', '') or 0
    brand = p.get('brand', '')
    cat_ids = p.get('categories', [])
    url = p.get('canonical_url', '')
    p_time = p.get('published', True)

    cat_name = ''
    # We"ll get category names separately
    mapping.append({
        'tn_id': tn_id, 'sku': sku, 'nombre': name,
        'marca': brand, 'precio': price, 'stock': stock,
        'url': url, 'publicado': 'SI' if p_time else 'NO'
    })

    sync_rows.append({
        'tn_id': tn_id, 'sku': sku, 'nombre': name,
        'marca': brand, 'precio_actual': price, 'stock_actual': stock,
        'precio_nuevo': '', 'stock_nuevo': '', 'notas': ''
    })

# Save mapping CSV
mapping_path = PROJECT + '/mapping_tn_ids.csv'
with open(mapping_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['tn_id','sku','nombre','marca','precio','stock','url','publicado'])
    w.writeheader()
    w.writerows(mapping)

# Save sync CSV
sync_path = PROJECT + '/productos_sync.csv'
with open(sync_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['tn_id','sku','nombre','marca','precio_actual','stock_actual','precio_nuevo','stock_nuevo','notas'])
    w.writeheader()
    w.writerows(sync_rows)

print()
print('MAPPING: ' + mapping_path + ' ({} products)'.format(len(mapping)))
print('SYNC:    ' + sync_path + ' ({} products)'.format(len(sync_rows)))
print()
print('Done! Edit productos_sync.csv and run sync-prices to update.')
