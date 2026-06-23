#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — JGO Armeria Web Interface
Flask app for uploading supplier price lists, running unification,
and syncing prices to Tienda Nube.
"""
import os
import sys
import csv
import json
import io
from pathlib import Path
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_file, jsonify, Response,
)
from dotenv import load_dotenv

# Load .env before anything
load_dotenv()

# -----------------------------------------------------------
# App config
# -----------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "jgo-armeria-dev-key-change-me")

# Auth config
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme123")
DEBUG = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes")

# TN credentials
TN_ACCESS_TOKEN = os.getenv("TN_ACCESS_TOKEN", "")
TN_STORE_ID = os.getenv("TN_STORE_ID", "6696461")

# -----------------------------------------------------------
# Initialize processor
# -----------------------------------------------------------

import processor as proc

APP_ROOT = Path(__file__).parent.resolve()
proc.init(str(APP_ROOT))

UPLOAD_FOLDER = str(proc.UPLOAD_DIR)
OUTPUT_FOLDER = str(proc.OUTPUT_DIR)

# Ensure dirs exist
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# Set up logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------
# Auth helpers
# -----------------------------------------------------------

def check_auth(username, password):
    return username == APP_USERNAME and password == APP_PASSWORD

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                'Authentication required',
                401,
                {'WWW-Authenticate': 'Basic realm="JGO Armeria Login"'}
            )
        return f(*args, **kwargs)
    return decorated

def optional_auth(f):
    """Use session-based auth, fallback to basic auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("authenticated"):
            return f(*args, **kwargs)
        auth = request.authorization
        if auth and check_auth(auth.username, auth.password):
            return f(*args, **kwargs)
        return Response(
            'Authentication required',
            401,
            {'WWW-Authenticate': 'Basic realm="JGO Armeria Login"'}
        )
    return decorated

# -----------------------------------------------------------
# Routes
# -----------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if check_auth(username, password):
            session["authenticated"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        flash("Usuario o contraseña incorrectos", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@optional_auth
def dashboard():
    """Main dashboard."""
    uploads = proc.get_upload_summary()
    outputs = proc.list_outputs()
    report = proc.get_last_report()

    # Check for TN mapping data
    mapping_path = APP_ROOT / "productos_sync.csv"
    has_mapping = mapping_path.exists()

    # Check TN credentials
    tn_configured = bool(TN_ACCESS_TOKEN)

    return render_template(
        "dashboard.html",
        uploads=uploads,
        outputs=outputs,
        report=report,
        has_mapping=has_mapping,
        tn_configured=tn_configured,
        now=datetime.now(),
    )


# -----------------------------------------------------------
# Upload routes
# -----------------------------------------------------------

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv"}

@app.route("/upload", methods=["GET", "POST"])
@optional_auth
def upload():
    if request.method == "POST":
        if "files" not in request.files:
            flash("No se seleccionaron archivos", "error")
            return redirect(url_for("upload"))

        files = request.files.getlist("files")
        uploaded = 0
        errors = 0

        for file in files:
            if file and file.filename:
                ext = Path(file.filename).suffix.lower()
                if ext not in ALLOWED_EXTENSIONS:
                    flash(f"Formato no soportado: {file.filename}", "error")
                    errors += 1
                    continue

                save_path = Path(app.config["UPLOAD_FOLDER"]) / file.filename
                file.save(str(save_path))
                uploaded += 1
                logger.info(f"Uploaded: {file.filename}")

        if uploaded:
            flash(f"Subidos {uploaded} archivo(s) correctamente", "success")
        return redirect(url_for("upload"))

    files = proc.get_upload_summary()
    return render_template("upload.html", files=files)


@app.route("/upload/clear", methods=["POST"])
@optional_auth
def upload_clear():
    proc.clear_uploads()
    flash("Archivos eliminados", "success")
    return redirect(url_for("upload"))


# -----------------------------------------------------------
# Process routes
# -----------------------------------------------------------

@app.route("/process")
@optional_auth
def process_page():
    """Show process page with current file status."""
    uploads = proc.get_upload_summary()
    report = proc.get_last_report()

    # Check which data files are available
    taurus_ok = uploads.get("taurus_pdf") is not None
    bersa_ok = uploads.get("bersa_pdf") is not None
    bersa_shop_ok = uploads.get("bersa_shop_xlsx") is not None
    base_ok = (APP_ROOT / "productos_jgo_armeria.csv").exists()

    ready = taurus_ok or bersa_ok or bersa_shop_ok or base_ok

    return render_template(
        "process.html",
        uploads=uploads,
        report=report,
        taurus_ok=taurus_ok,
        bersa_ok=bersa_ok,
        bersa_shop_ok=bersa_shop_ok,
        base_ok=base_ok,
        ready=ready,
    )


@app.route("/process/run", methods=["POST"])
@optional_auth
def process_run():
    """Execute product unification."""
    flash("Procesando listas de precios... Esto puede tomar unos segundos.", "info")

    try:
        result = proc.run_unification()

        if result["success"]:
            flash(
                f"Unificación completada: {result['total']} productos "
                f"({result['con_precio']} con precio)",
                "success",
            )
        else:
            flash(f"Error durante la unificación: {result.get('error', 'Desconocido')}", "error")
            # Show last 5 log lines
            for line in result.get("log", [])[-5:]:
                flash(line, "warning")

        return redirect(url_for("process_result"))

    except Exception as e:
        logger.exception("Error running unification")
        flash(f"Error crítico: {e}", "error")
        return redirect(url_for("process_page"))


@app.route("/process/result")
@optional_auth
def process_result():
    """Show process results."""
    report = proc.get_last_report()
    outputs = proc.list_outputs()
    return render_template("process_result.html", report=report, outputs=outputs)


# -----------------------------------------------------------
# Download routes
# -----------------------------------------------------------

@app.route("/download/<filename>")
@optional_auth
def download_file(filename):
    """Download a generated output file."""
    # Check outputs dir first
    filepath = Path(app.config["OUTPUT_FOLDER"]) / filename
    if not filepath.exists():
        # Fallback to root
        filepath = APP_ROOT / filename
    if not filepath.exists():
        flash(f"Archivo no encontrado: {filename}", "error")
        return redirect(url_for("dashboard"))

    return send_file(str(filepath), as_attachment=True, download_name=filename)


@app.route("/outputs")
@optional_auth
def outputs():
    """List all output files."""
    files = proc.list_outputs()
    report = proc.get_last_report()
    return render_template("outputs.html", files=files, report=report)


@app.route("/outputs/clean", methods=["POST"])
@optional_auth
def outputs_clean():
    """Clean output files."""
    out_dir = Path(app.config["OUTPUT_FOLDER"])
    for f in out_dir.iterdir():
        if f.is_file():
            f.unlink()
    flash("Archivos de salida eliminados", "success")
    return redirect(url_for("outputs"))


# -----------------------------------------------------------
# Tienda Nube routes
# -----------------------------------------------------------

@app.route("/tiendanube")
@optional_auth
def tiendanube():
    """Tienda Nube management page."""
    import gestionar_tiendanube as tn_mod

    token = TN_ACCESS_TOKEN
    store_id = TN_STORE_ID

    # Patch module
    if token:
        tn_mod.TN_TOKEN = token
    if store_id:
        tn_mod.TN_STORE_ID = store_id
        tn_mod.TN_API_BASE = f"https://api.tiendanube.com/v1/{store_id}"

    # Get stats
    stats = proc.tn_get_stats(token, store_id)
    mapping_path = APP_ROOT / "mapping_tn_ids.csv"
    sync_path = APP_ROOT / "productos_sync.csv"
    has_mapping = mapping_path.exists()

    # Check sync file for pending updates
    pending_updates = 0
    if sync_path.exists():
        try:
            with open(sync_path, 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    if row.get('precio_nuevo', '').strip() or row.get('stock_nuevo', '').strip():
                        pending_updates += 1
        except:
            pass

    return render_template(
        "tiendanube.html",
        stats=stats,
        has_mapping=has_mapping,
        pending_updates=pending_updates,
        token_configured=bool(token),
    )


@app.route("/tiendanube/export-ids", methods=["POST"])
@optional_auth
def tiendanube_export_ids():
    """Export product IDs from Tienda Nube."""
    flash("Exportando IDs de Tienda Nube...", "info")

    token = request.form.get("token", TN_ACCESS_TOKEN)
    store_id = request.form.get("store_id", TN_STORE_ID)

    try:
        result = proc.tn_export_ids(token, store_id)
        if result["success"]:
            flash(f"IDs exportados: {result['total']} productos", "success")
        else:
            flash(f"Error: {result.get('error', 'Desconocido')}", "error")
            for line in result.get("log", [])[-3:]:
                flash(line, "warning")
    except Exception as e:
        flash(f"Error al exportar IDs: {e}", "error")

    return redirect(url_for("tiendanube"))


@app.route("/tiendanube/sync-prices", methods=["POST"])
@optional_auth
def tiendanube_sync_prices():
    """Sync prices from sync CSV to Tienda Nube."""
    flash("Sincronizando precios con Tienda Nube...", "info")

    token = request.form.get("token", TN_ACCESS_TOKEN)
    store_id = request.form.get("store_id", TN_STORE_ID)
    sync_file = request.form.get("sync_file", "")

    try:
        result = proc.tn_sync_prices(sync_file if sync_file else None, token, store_id)
        if result["success"]:
            flash(
                f"Sincronización completada: {result.get('updates', 0)} actualizados, "
                f"{result.get('errors', 0)} errores",
                "success",
            )
        else:
            flash(f"Error: {result.get('error', 'Desconocido')}", "error")
            for line in result.get("log", [])[-3:]:
                flash(line, "warning")
    except Exception as e:
        flash(f"Error al sincronizar: {e}", "error")

    return redirect(url_for("tiendanube"))


@app.route("/tiendanube/sync-file")
@optional_auth
def tiendanube_sync_file():
    """View or download the sync CSV."""
    sync_path = APP_ROOT / "productos_sync.csv"
    if not sync_path.exists():
        flash("No hay archivo de sincronización. Exportá IDs primero.", "warning")
        return redirect(url_for("tiendanube"))

    # Check if user wants to download
    if request.args.get("download"):
        return send_file(str(sync_path), as_attachment=True, download_name="productos_sync.csv")

    # Read and display
    with open(sync_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    return render_template("sync_edit.html", rows=rows, headers=reader.fieldnames if reader.fieldnames else [])


@app.route("/tiendanube/sync-file/update", methods=["POST"])
@optional_auth
def tiendanube_sync_file_update():
    """Update the sync CSV with new prices/stocks from form."""
    sync_path = APP_ROOT / "productos_sync.csv"
    if not sync_path.exists():
        flash("No hay archivo de sincronización", "error")
        return redirect(url_for("tiendanube"))

    # Read existing
    with open(sync_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Update from form
    for row in rows:
        tn_id = row.get('tn_id', '')
        new_price = request.form.get(f"price_{tn_id}", "").strip()
        new_stock = request.form.get(f"stock_{tn_id}", "").strip()

        if new_price:
            row['precio_nuevo'] = new_price
        if new_stock:
            row['stock_nuevo'] = new_stock

    # Write back
    with open(sync_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    flash("Archivo de sincronización actualizado", "success")
    return redirect(url_for("tiendanube_sync_file"))


@app.route("/tiendanube/sync-file/prefill", methods=["POST"])
@optional_auth
def tiendanube_sync_file_prefill():
    """Prefill the sync file with prices from the latest unified CSV."""
    unified_path = APP_ROOT / "productos_jgo_armeria_unificado.csv"
    sync_path = APP_ROOT / "productos_sync.csv"

    if not unified_path.exists():
        flash("No hay archivo unificado. Ejecutá 'Procesar' primero.", "error")
        return redirect(url_for("tiendanube"))

    # Read unified CSV to get SKU -> price mapping
    sku_prices = {}
    with open(unified_path, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f, delimiter=';'):
            sku = row.get('SKU', '').strip()
            price = row.get('Precio', '').strip()
            if sku and price:
                sku_prices[sku.lower()] = price

    # Update sync file
    if sync_path.exists():
        with open(sync_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        updated = 0
        for row in rows:
            sku = row.get('sku', '').strip().lower()
            if sku in sku_prices:
                unified_price = sku_prices[sku]
                if unified_price != row.get('precio_actual', ''):
                    row['precio_nuevo'] = unified_price
                    updated += 1

        with open(sync_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        flash(f"Prefill completado: {updated} productos con nuevo precio sugerido", "success")
    else:
        flash("No hay archivo sync. Exportá IDs primero.", "warning")

    return redirect(url_for("tiendanube_sync_file"))


# -----------------------------------------------------------
# API routes (for AJAX / programmatic use)
# -----------------------------------------------------------

@app.route("/api/status")
def api_status():
    """Simple health check."""
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "version": "1.0.0",
        "project": "JGO Armeria - Tienda Nube Integration",
    })


@app.route("/api/uploads")
@require_auth
def api_uploads():
    """List uploaded files via API."""
    files = proc.get_upload_summary()
    return jsonify(files)


@app.route("/api/report")
@require_auth
def api_report():
    """Get latest unification report."""
    report = proc.get_last_report()
    if report:
        return jsonify(report)
    return jsonify({"error": "No report found"}), 404


@app.route("/api/process", methods=["POST"])
@require_auth
def api_process():
    """Run unification via API."""
    result = proc.run_unification()
    return jsonify(result)


@app.route("/api/tn/sync", methods=["POST"])
@require_auth
def api_tn_sync():
    """Sync prices via API."""
    data = request.get_json() or {}
    token = data.get("token", TN_ACCESS_TOKEN)
    store_id = data.get("store_id", TN_STORE_ID)
    result = proc.tn_sync_prices(token=token, store_id=store_id)
    return jsonify(result)


@app.route("/api/tn/export-ids", methods=["POST"])
@require_auth
def api_tn_export():
    """Export IDs via API."""
    data = request.get_json() or {}
    token = data.get("token", TN_ACCESS_TOKEN)
    store_id = data.get("store_id", TN_STORE_ID)
    result = proc.tn_export_ids(token, store_id)
    return jsonify(result)


@app.route("/api/tn/stats")
@require_auth
def api_tn_stats():
    """Get TN store stats via API."""
    result = proc.tn_get_stats(TN_ACCESS_TOKEN, TN_STORE_ID)
    return jsonify(result)


# -----------------------------------------------------------
# Error handlers
# -----------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Página no encontrada"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Error interno del servidor"), 500


# -----------------------------------------------------------
# Main
# -----------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = DEBUG or os.getenv("FLASK_ENV") == "development"
    print(f"\n  JGO Armeria Web Interface")
    print(f"  {'=' * 40}")
    print(f"  URL: http://0.0.0.0:{port}")
    print(f"  Auth: Basic / Session")
    print(f"  Debug: {debug}")
    print(f"  TN configured: {bool(TN_ACCESS_TOKEN)}")
    print(f"  TN Store: {TN_STORE_ID}")
    print(f"  {'=' * 40}\n")

    app.run(host="0.0.0.0", port=port, debug=debug)
