#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Tienda Nube CSV from lista_armas.xlsx"""

import csv
import re
import unicodedata
from collections import defaultdict, Counter

def slugify(text):
    text = text.lower().strip()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    return text

HEADERS = [
    "Identificador de URL", "Nombre", "Categorías",
    "Nombre de propiedad 1", "Valor de propiedad 1",
    "Nombre de propiedad 2", "Valor de propiedad 2",
    "Nombre de propiedad 3", "Valor de propiedad 3",
    "Precio", "Precio promocional", "Peso (kg)", "Alto (cm)", "Ancho (cm)", "Profundidad (cm)",
    "Stock", "SKU", "Código de barras", "Mostrar en tienda", "Envío sin cargo",
    "Descripción", "Tags", "Título para SEO", "Descripción para SEO",
    "Marca", "Producto Físico", "MPN (Número de pieza del fabricante)", "Sexo", "Rango de edad", "Costo"
]

def make_product(url, nombre, categoria, precio='', desc='', marca='', tags='',
                 prop1='', val1='', prop2='', val2='', prop3='', val3='',
                 sku='', stock='5', seo_title='', seo_desc=''):
    return {
        "Identificador de URL": url,
        "Nombre": nombre,
        "Categorías": categoria,
        "Nombre de propiedad 1": prop1, "Valor de propiedad 1": val1,
        "Nombre de propiedad 2": prop2, "Valor de propiedad 2": val2,
        "Nombre de propiedad 3": prop3, "Valor de propiedad 3": val3,
        "Precio": precio, "Precio promocional": "", "Peso (kg)": "1", "Alto (cm)": "15", "Ancho (cm)": "10", "Profundidad (cm)": "30",
        "Stock": stock, "SKU": sku, "Código de barras": "", "Mostrar en tienda": "SI", "Envío sin cargo": "NO",
        "Descripción": desc, "Tags": tags, "Título para SEO": seo_title or nombre, "Descripción para SEO": seo_desc or desc,
        "Marca": marca, "Producto Físico": "SI", "MPN (Número de pieza del fabricante)": "", "Sexo": "", "Rango de edad": "", "Costo": ""
    }

rows = []
sku_counter = 1

# ==================== GLOCK ====================
glock_products = [
    ("17 gen3", "9mm"), ("17 gen5", "9mm"), ("19 gen5", "9mm"), ("19 gen4", "9mm"),
    ("19x arena", "9mm"), ("21 gen4", "45acp"), ("22 gen4", "40s&w"), ("25", "380acp"),
    ("30 gen4", "45acp"), ("30s", "45acp"), ("35 gen4", "40s&w"), ("43 gen4", "9mm"),
    ("44 gen4", "22lr"), ("45mos gen4", "9mm"), ("45compacta", "9mm"), ("48", "9mm"), ("48 dt", "9mm")
]

for modelo, calibre in glock_products:
    cal_formatted = calibre.upper() if calibre.lower() != "9mm" else "9mm"
    nombre = f"Glock {modelo} {cal_formatted}"
    url = slugify(f"glock-{modelo}-{calibre}")
    cap_desc = {
        "9mm": "9mm, ideal para defensa personal y tiro deportivo",
        "45acp": ".45 ACP, potente y confiable",
        "40s&w": ".40 S&W, excelente rendimiento",
        "380acp": ".380 ACP, compacta y precisa",
        "22lr": ".22 LR, ideal para entrenamiento y tiro recreativo"
    }.get(calibre.lower(), calibre)
    desc = f"Pistola Glock {modelo} calibre {cap_desc}. Fabricada por Glock, Austria. Máxima confiabilidad y precisión."
    seo = f"Pistola Glock {modelo} {cal_formatted} | JGO Armería"
    modelo_tag = modelo.split()[0]
    rows.append(make_product(url, nombre, "Armas > Pistolas", desc=desc, marca="Glock",
                            tags=f"glock,{modelo_tag},{calibre}", seo_title=seo,
                            sku=f"GLC-{sku_counter:03d}"))
    sku_counter += 1

# ==================== BERSA ====================
bersa_products = [
    ("TPR9CX FDE", "9mm"), ("TPR9X Cerakote OD c/caño rosca", "9mm"),
    ("TPR9 Cerakote Bright", "9mm"), ("TPR9 Duo Tono", "9mm"),
    ("TPR9 CL", "9mm"), ("BP9CC FDE Optics Ready Pavon", "9mm"),
    ("BP9CC FDE Frame", "9mm"), ("BP9CC Flat Dark Earth", "9mm"),
    ("BP9 FS OD FDE", "9mm"), ("BP9 FS FDE", "9mm"), ("BP9 FS Pavon", "9mm")
]

for modelo, calibre in bersa_products:
    nombre = f"Bersa {modelo} {calibre}"
    modelo_slug_base = modelo.split()[0].lower()
    url = slugify(f"bersa-{modelo_slug_base}-{slugify(modelo.split()[1] if len(modelo.split()) > 1 else '')}")
    desc = f"Pistola Bersa {modelo} calibre {calibre}. Fabricada por Bersa, Argentina. Alta precisión y confiabilidad."
    seo = f"Pistola Bersa {modelo} {calibre} | JGO Armería"
    rows.append(make_product(url, nombre, "Armas > Pistolas", desc=desc, marca="Bersa",
                            tags=f"bersa,{modelo_slug_base},{calibre}", seo_title=seo,
                            sku=f"BER-{sku_counter:03d}"))
    sku_counter += 1

# ==================== TAURUS ====================
taurus_data = [
    ("Revolver", "38SPL", "M825 PM", "Pavonado", '4"', "6 tiros", "Alza fija"),
    ("Revolver", "357M", "627 CP", "Inox", '4"', "7 tiros", "Tracker"),
    ("Revolver", "357M", "627 IM", "Inox", '6"', "7 tiros", "Tracker"),
    ("Revolver", "38SP", "856 UL", "Pavonado", '2"', "6 tiros", "Ultra Lite"),
    ("Revolver", "22LR", "M96", "Pavonado", '6"', "6 tiros", ""),
    ("Revolver", "22LR/22MAG", "M992", "Inox/Mate", '4"', "9 tiros", ""),
    ("Revolver", "44MG", "M444 IG", "Inox", '6.5"', "6 tiros", ""),
    ("Revolver", "38SP", "M855", "Pavonado", '4"', "5 tiros", "Alza fija"),
    ("Revolver", "22LR", "M94", "Inox", '4"', "9 tiros", ""),
    ("Revolver", "38SP", "M85", "Pavonado", '2"', "5 tiros", ""),
    ("Pistola", "9mm", "Commander 1911", "Pavonado mate", "", "9 tiros x2", ""),
    ("Pistola", "45ACP", "Commander 1911", "Pavonado mate", "", "8 tiros x2", ""),
    ("Pistola", "45ACP", "Commander 1911", "Inox", "", "8 tiros x2", ""),
    ("Pistola", "9mm", "G3C", "Inox/Marrón", "", "12 tiros", ""),
    ("Pistola", "40 S&W", "MTH40C", "Pavonado", "", "11-15 tiros", ""),
    ("Pistola", "9mm", "G2C", "Pavonado/Gris", "", "17 tiros", ""),
    ("Pistola", "9mm", "G2C", "Pavonado/Sint.", "", "17 tiros", ""),
    ("Pistola", "9mm", "G3C", "Toro Pavonado/Sint.", "", "17 tiros", ""),
    ("Pistola", "9mm", "MTS9", "Pavonada", "", "17 tiros", ""),
    ("Pistola", "9mm", "G3C", "Verde/Negro", "", "17 tiros", ""),
    ("Pistola", "9mm", "G3C", "Arena/Negro", "", "17 tiros", ""),
]

taurus_groups = defaultdict(list)
for entry in taurus_data:
    key = (entry[0], entry[2])  # (tipo, modelo)
    taurus_groups[key].append(entry)

for (tipo, modelo), variants in taurus_groups.items():
    cat = "Armas > Revolveres" if tipo == "Revolver" else "Armas > Pistolas"
    marca = "Taurus"

    if len(variants) == 1:
        _, cal, mod, acabado, pulg, cap, extra = variants[0]
        nombre = f"Taurus {mod} {cal} {acabado}"
        url = slugify(f"taurus-{mod}-{slugify(cal)}-{slugify(acabado)}")
        extras = []
        if pulg: extras.append(f"cañón {pulg}")
        if cap: extras.append(f"capacidad {cap}")
        extra_text = " - " + ", ".join(extras) if extras else ""
        desc = f"{tipo} Taurus {mod} calibre {cal}. Acabado {acabado}.{extra_text}"
        seo = f"{tipo} Taurus {mod} {cal} | JGO Armería"
        rows.append(make_product(url, nombre, cat, desc=desc, marca=marca,
                                tags=f"taurus,{slugify(mod)},{slugify(cal)}",
                                seo_title=seo, sku=f"TAU-{sku_counter:03d}"))
        sku_counter += 1
    else:
        all_cals = sorted(set(v[1] for v in variants))
        all_acab = sorted(set(v[3] for v in variants))
        varies_cal = len(all_cals) > 1
        varies_acab = len(all_acab) > 1

        prop1_name = ""
        prop2_name = ""
        if varies_cal and varies_acab:
            prop1_name = "Calibre"
            prop2_name = "Acabado"
        elif varies_cal:
            prop1_name = "Calibre"
        elif varies_acab:
            prop1_name = "Acabado"

        base_url = slugify(f"taurus-{modelo}")
        base_nombre = f"Taurus {modelo}"

        for _, cal, mod, acabado, pulg, cap, extra in variants:
            val1 = cal if prop1_name == "Calibre" else (acabado if prop1_name == "Acabado" else "")
            val2 = acabado if prop2_name == "Acabado" else ""

            extras = []
            if pulg: extras.append(f"cañón {pulg}")
            if cap: extras.append(f"capacidad {cap}")
            extra_text = " - " + ", ".join(extras) if extras else ""

            desc = f"{tipo} Taurus {mod} calibre {cal}. Acabado {acabado}.{extra_text}"
            variant_nombre = f"{base_nombre} - {cal} {acabado}"
            seo = f"{tipo} Taurus {mod} {cal} {acabado} | JGO Armería"
            rows.append(make_product(base_url, variant_nombre, cat,
                                    prop1=prop1_name, val1=val1,
                                    prop2=prop2_name, val2=val2,
                                    desc=desc, marca=marca,
                                    tags=f"taurus,{slugify(mod)},{slugify(cal)}",
                                    seo_title=seo, sku=f"TAU-{sku_counter:03d}"))
            sku_counter += 1

# ==================== BERETTA PISTOLAS ====================
beretta_pistolas = [
    ("Beretta", "9mm", "9x9", "Pavonada", "", "17-20 tiros"),
    ("Beretta", "9mm", "APX", "Pavonada", "", "17-20 tiros"),
    ("Beretta", "9mm", "92 Compact", "Pavonada", "", "17-20 tiros"),
    ("Beretta", "9mm", "9x9 Storm Subcompact", "Pavonada", "", "17-20 tiros"),
    ("Beretta", "9mm", "APX Cany", "Pavonada", "", "17-20 tiros"),
    ("Beretta", "9mm", "APX Cany", "FDE Arena", "", "17-20 tiros"),
    ("Beretta", "9mm", "APX Compact", "Pavonada", "", "17-20 tiros"),
    ("Beretta", "9mm", "U22 NEOS", "Inox", "", "17-20 tiros"),
    ("Beretta", "9mm", "9x9", "Inox", "", "17-20 tiros"),
    ("Beretta", "9mm", "92FS", "Pavonada", "", "17-20 tiros"),
    ("Beretta", "9mm", "3032 Tomcat", "Pavonada", "", "17-20 tiros"),
    ("Beretta", "9mm", "APX AI", "Estándar", "", "17-20 tiros"),
]

beretta_groups = defaultdict(list)
for entry in beretta_pistolas:
    beretta_groups[entry[2]].append(entry)

for modelo, variants in beretta_groups.items():
    unique_acabados = list(dict.fromkeys(v[3] for v in variants if v[3]))
    has_variants = len(unique_acabados) > 1

    if not has_variants or len(variants) == 1:
        for _, cal, mod, acabado, pulg, cap in variants:
            acabado_clean = acabado if acabado else "Estándar"
            nombre = f"Beretta {mod} {cal} {acabado_clean}"
            url = slugify(f"beretta-{slugify(mod)}-{slugify(acabado_clean)}")
            desc = f"Pistola Beretta {mod} calibre {cal}. Acabado {acabado_clean}."
            seo = f"Pistola Beretta {mod} {cal} | JGO Armería"
            rows.append(make_product(url, nombre, "Armas > Pistolas", desc=desc, marca="Beretta",
                                    tags=f"beretta,{slugify(mod)},{cal}", seo_title=seo,
                                    sku=f"BEP-{sku_counter:03d}"))
            sku_counter += 1
    else:
        base_url = slugify(f"beretta-{modelo}")
        for _, cal, mod, acabado, pulg, cap in variants:
            acabado_clean = acabado if acabado else "Estándar"
            nombre = f"Beretta {mod} - {acabado_clean}"
            desc = f"Pistola Beretta {mod} calibre {cal}. Acabado {acabado_clean}."
            seo = f"Pistola Beretta {mod} {acabado_clean} | JGO Armería"
            rows.append(make_product(base_url, nombre, "Armas > Pistolas",
                                    prop1="Acabado", val1=acabado_clean,
                                    desc=desc, marca="Beretta",
                                    tags=f"beretta,{slugify(mod)},{cal}",
                                    seo_title=seo, sku=f"BEP-{sku_counter:03d}"))
            sku_counter += 1

# ==================== ESCOPETAS BERETTA ====================
escopetas = [
    ("Beretta", "12", "A300 Ultim Black", "Culata Sintética", "", ""),
    ("Beretta", "12", "A400 Lite", "Camo", "", ""),
    ("Beretta", "12", "A400 Lite", "Sintético", "", ""),
    ("Beretta", "12", "1301 Tactical", "FDE", "", ""),
    ("Beretta", "12", "BRXI", "Cal 300 Winchester", "", ""),
]

for _, cal, mod, acabado, pulg, cap in escopetas:
    nombre = f"Beretta {mod} {slugify(acabado).upper() if slugify(acabado) else ''} Cal. {cal}"
    url = slugify(f"beretta-{slugify(mod)}-{slugify(acabado)}")
    desc = f"Escopeta Beretta {mod} {acabado} calibre {cal}."
    seo = f"Escopeta Beretta {mod} | JGO Armería"
    rows.append(make_product(url, nombre, "Armas > Escopetas", desc=desc, marca="Beretta",
                            tags=f"beretta,escopeta,{slugify(mod)}", seo_title=seo,
                            sku=f"BES-{sku_counter:03d}"))
    sku_counter += 1

# Write CSV
output_file = "productos_jgo_armeria.csv"
with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=HEADERS, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(rows)

print(f"OK - CSV generado: {output_file}")
print(f"Total de productos (filas): {len(rows)}")
print()

# Show sample
print("Muestra:")
for row in rows[:3]:
    print(f"  URL: {row['Identificador de URL']}")
    print(f"  Nombre: {row['Nombre']}")
    print(f"  Categoría: {row['Categorías']}")
    print(f"  Marca: {row['Marca']}")
    print()

# Count by category
cats = Counter(r['Categorías'] for r in rows)
print("Productos por categoría:")
for cat, count in cats.most_common():
    print(f"  {cat}: {count}")
print()

# Count products with variations
variation_urls = set()
for row in rows:
    if row['Nombre de propiedad 1']:
        variation_urls.add(row['Identificador de URL'])

print(f"Productos con variantes: {len(variation_urls)}")
for url in sorted(variation_urls):
    variants = [r for r in rows if r['Identificador de URL'] == url]
    print(f"  {url}: {len(variants)} variantes")
