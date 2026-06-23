# JGO Armería — Integración Tienda Nube

## Estructura del proyecto

```
📁 C:\Areas\02_Agencia\Clientes\JGO Armeria\
│
├── README.md                              ← Este archivo
├── tiendanube_credentials.md              ← Credenciales API
│
├── productos_jgo_armeria_unificado.csv    ← Catálogo final listo para TN (507 prods)
├── mapping_tn_ids.csv                     ← SKU → TN ID (generado post-import)
├── productos_sync.csv                     ← Para actualizar precios/stocks
├── reporte_unificacion.json               ← Estadísticas de la unificación
│
├── unificar_productos.py                  ← Procesa fuentes → CSV unificado
├── gestionar_tiendanube.py                ← Gestión completa de TN vía API
├── importar_tn_final.py                   ← Importación directa a TN
├── exportar_ids.py                        ← Descarga IDs de TN
│
├── listas/                                ← Listas de precios de proveedores
│   ├── LISTA BERSA SHOP JUNIO 2026 - V1.xlsx
│   ├── LISTA DE PRECIOS - TAURUS ABRIL 2026.pdf
│   ├── LISTA DE PRECIOS BERSA PISTOLAS Y ACCESORIOS - MI - JUNIO 2026.pdf
│   └── LISTAS DE PRECIOS LUBE JUNIO - 9.6.2026.pdf
│
├── productos_jgo_armeria.csv              ← Catálogo base original (sin precios)
├── lista_armas.xlsx                       ← Lista de armas original
├── imagenes_mapping.csv                   ← Mapping imágenes → SKU
├── imagenes_productos/                    ← Imágenes de productos
│
└── memory/                                ← Memoria persistente del agente
```

## Fuentes de datos integradas

| Fuente | Tipo | Productos | Precios |
|--------|------|-----------|---------|
| `productos_jgo_armeria.csv` | CSV base | 66 armas | Sin precio |
| `lista_armas.xlsx` | XLSX | 17 registros | Sin precio |
| PDF Taurus (Trompia SRL) | Abril 2026 | 18 modelos | USD |
| PDF Bersa Pistolas y Accesorios | Junio 2026 | 115 variantes | ARS |
| XLSX Bersa Shop | Junio 2026 | 540 accesorios | ARS |

## Catálogo final (507 productos)

### Por categoría

| Categoría | Cantidad |
|-----------|:--------:|
| Accesorios > Repuestos y Partes | 183 |
| Linternas | 100 |
| Accesorios > AR-15 / BAR9 | 58 |
| Armas > Pistolas | 51 |
| Protección Auditiva | 48 |
| Municiones y Snap Caps | 21 |
| Miras y Red Dots | 20 |
| Armas > Revolveres | 10 |
| Accesorios > Canik | 9 |
| Armas > Escopetas | 5 |
| Cuchillos y Navajas | 1 |
| Merchandising | 1 |

### Por marca (armas)

| Marca | Productos |
|-------|:---------:|
| Glock | 17 |
| Taurus | 16 |
| Beretta | 17 |
| Bersa | 11 |

### Campos completados

- **Precio**: 507/507 (100%)
- **Descripción**: 507/507 (100%)
- **Marca**: 507/507 (100%)
- **SKU**: 507/507 (100%)

> ⚠️ Los precios de Glock y Beretta son de referencia de mercado. Los precios de Taurus vienen del PDF de Trompia (USD). Los precios de Bersa vienen del PDF oficial (ARS). Ajustar según margen comercial.

## Tienda Nube — Estado actual

- **Store ID**: 6696461
- **Tienda**: armeriajgo.mitiendanube.com
- **Productos en TN**: 507
- **Categorías en TN**: 13 (Armas > Pistolas, Armas > Revolveres, Armas > Escopetas, Accesorios, Linternas, Protección Auditiva, Municiones y Snap Caps, Miras y Red Dots, Cuchillos y Navajas, Merchandising, Equipamiento, Seguridad Industrial)

### IDs de categorías en TN

| Categoría | ID |
|-----------|:--:|
| Armas | 38714846 |
| Armas > Pistolas | 38714848 |
| Armas > Revolveres | 38714857 |
| Armas > Escopetas | 38714868 |
| Accesorios | 39479652 |
| Linternas | 39479653 |
| Protección Auditiva | 39479654 |
| Municiones y Snap Caps | 39479655 |
| Miras y Red Dots | 39479656 |
| Cuchillos y Navajas | 39479657 |
| Merchandising | 39479658 |
| Equipamiento | 39479659 |
| Seguridad Industrial | 39479660 |

## Cómo usar los scripts

### 1. Unificar fuentes (cuando haya nuevas listas de precios)

```bash
python unificar_productos.py
```

Esto procesa todas las fuentes en `listas/` y genera:
- `productos_jgo_armeria_unificado.csv` (catálogo completo)
- `reporte_unificacion.json` (estadísticas)

### 2. Gestión de Tienda Nube

```bash
python gestionar_tiendanube.py --list              # Listar productos actuales
python gestionar_tiendanube.py --export-ids         # Descargar mapping SKU→TN ID
python gestionar_tiendanube.py --sync-prices        # Sincronizar precios/stocks
```

### 3. Sincronizar precios desde listas de proveedores

1. Editar `productos_sync.csv` — completar `precio_nuevo` y/o `stock_nuevo`
2. Ejecutar:
```bash
python gestionar_tiendanube.py --sync-pricing
```

El script matchea por **SKU** y actualiza solo los productos modificados vía API de TN (1.5s entre requests por rate limiting).

### 4. Importación inicial (ya ejecutada)

```bash
python importar_tn_final.py     # Subió los 507 productos
python exportar_ids.py          # Descargó IDs y generó mappings
```

## Credenciales API

Ver `tiendanube_credentials.md`

```
API Base: https://api.tiendanube.com/v1/6696461
Authentication: bearer 8ae716d86bdc3e6bd23915943d6b7de233ab7f6b
User-Agent: HeavenIntegration/1.0 (lucas@heaven.com.ar)
```

- Access token generado: 2026-05-11
- Scope: `write_products`
- App base: `C:\laragon\www\heaven-tiendanube`
- Rate limit: 40 requests/minuto

## Flujo de trabajo recomendado

```
┌─────────────────────┐
│  Nueva lista de     │
│  precios (PDF/XLSX) │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  python unificar_   │
│  productos.py       │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  Editar productos_  │
│  sync.csv           │
│  (precio_nuevo)     │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  python gestionar_  │
│  tiendanube.py --   │
│  sync-prices        │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  Precios actualiza- │
│  dos en TN ✅       │
└─────────────────────┘
```

## Notas técnicas

- El CSV usa **UTF-8 BOM** y **`;`** como delimitador (formato TN)
- El script de unificación lee PDFs con `pdfplumber` y XLSX con `openpyxl`
- La importación a TN usa `urllib.request` (std lib) — sin dependencias externas
- Hay rate limiting de 40 req/min en TN → 1.5s de delay entre requests
- Los códigos SKU de armas: `GLC-*` (Glock), `BER-*` (Bersa), `TAU-*` (Taurus), `BEP-*` (Beretta pistola), `BES-*` (Beretta escopeta)
