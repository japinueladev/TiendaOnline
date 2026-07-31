from __future__ import annotations

import csv
import hashlib
import logging
import os
import shutil
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pymysql
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger("importer")

INPUT_DIR = Path("/app/data/entrada")
PROCESSED_DIR = Path("/app/data/procesados")
ERROR_DIR = Path("/app/data/errores")

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "mysql"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "alumno"),
    "password": os.getenv("MYSQL_PASSWORD", "alumno123"),
    "database": os.getenv("MYSQL_DATABASE", "finanzas"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
    "connect_timeout": 10,
}
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:admin123@mongodb:27017/?authSource=admin")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "finanzas_nosql")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "movimientos")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "5"))
REQUIRED_COLUMNS = {"Fecha", "Tipo", "Importe", "Categoria", "Producto", "Medio_pago"}
COUNTRIES = ("España", "Portugal", "Francia", "Italia")
SEGMENTS = ("Particular", "Empresa", "Autónomo")
CAMPAIGNS = ("ORGANICO", "FIDELIZACION", "PROMOCION-MENSUAL")
SOURCES = ("web", "tienda", "app", "marketplace")


def ensure_directories() -> None:
    for directory in (INPUT_DIR, PROCESSED_DIR, ERROR_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def wait_for_services() -> None:
    last_error: Exception | None = None
    for attempt in range(1, 61):
        try:
            mysql = pymysql.connect(**MYSQL_CONFIG)
            mysql.ping(reconnect=True)
            mysql.close()
            mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            mongo.admin.command("ping")
            mongo.close()
            LOGGER.info("MySQL y MongoDB están disponibles.")
            return
        except Exception as exc:
            last_error = exc
            LOGGER.warning("Servicios no disponibles. Intento %s/60: %s", attempt, exc)
            time.sleep(3)
    raise RuntimeError(f"No se pudo conectar con las bases de datos: {last_error}")


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_and_validate_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("El CSV no contiene cabecera.")
        reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError("Faltan columnas obligatorias: " + ", ".join(sorted(missing)))

        for line_number, raw in enumerate(reader, start=2):
            cleaned = {key: value.strip() if isinstance(value, str) else value for key, value in raw.items()}
            if not any(cleaned.values()):
                continue
            try:
                date_value = datetime.strptime(cleaned["Fecha"], "%Y-%m-%d").date()
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Línea {line_number}: Fecha no válida.") from exc

            movement_type = cleaned["Tipo"].capitalize()
            if movement_type not in {"Ingreso", "Gasto"}:
                raise ValueError(f"Línea {line_number}: Tipo debe ser Ingreso o Gasto.")

            try:
                amount = Decimal(cleaned["Importe"])
            except (InvalidOperation, TypeError) as exc:
                raise ValueError(f"Línea {line_number}: Importe no numérico.") from exc
            if amount < 0:
                raise ValueError(f"Línea {line_number}: Importe no puede ser negativo.")

            for field in ("Categoria", "Producto", "Medio_pago"):
                if not cleaned[field]:
                    raise ValueError(f"Línea {line_number}: {field} está vacío.")

            rows.append({
                "fecha": date_value,
                "tipo": movement_type,
                "importe": amount,
                "categoria": cleaned["Categoria"],
                "producto": cleaned["Producto"],
                "medio_pago": cleaned["Medio_pago"],
            })
    if not rows:
        raise ValueError("El CSV no contiene movimientos.")
    return rows


def existing_import(file_hash: str) -> dict[str, Any] | None:
    connection = pymysql.connect(**MYSQL_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, estado, filas_importadas FROM importaciones WHERE hash_archivo=%s", (file_hash,))
            return cursor.fetchone()
    finally:
        connection.close()


def build_mongo_document(row: dict[str, Any], import_id: int, file_hash: str, position: int) -> dict[str, Any]:
    amount = float(row["importe"])
    tags = ["movimiento", row["tipo"].lower()]
    tags.append("importe-alto" if amount >= 500 else "importe-medio" if amount >= 100 else "importe-bajo")
    document: dict[str, Any] = {
        "movimiento_origen": {"importacion_id": import_id, "posicion_csv": position, "hash_archivo": file_hash},
        "fecha": datetime.combine(row["fecha"], datetime.min.time()),
        "tipo": row["tipo"],
        "importe": amount,
        "categoria": row["categoria"],
        "producto": row["producto"],
        "medio_pago": row["medio_pago"],
        "etiquetas": tags,
        "metadatos": {"origen": SOURCES[(position - 1) % len(SOURCES)], "cargado_por": "importer-python"},
    }
    if row["tipo"] == "Ingreso":
        document["cliente"] = {
            "id": f"CLI-{1000 + position}",
            "pais": COUNTRIES[(position - 1) % len(COUNTRIES)],
            "segmento": SEGMENTS[(position - 1) % len(SEGMENTS)],
        }
        document["detalles"] = {
            "unidades": 1 if amount >= 300 else 2,
            "descuento_porcentaje": (position % 4) * 5,
            "campania": CAMPAIGNS[(position - 1) % len(CAMPAIGNS)],
        }
    else:
        document["proveedor"] = {"id": f"PRO-{500 + position}", "nombre": row["producto"], "tipo": row["categoria"]}
        document["detalles"] = {"urgente": position % 3 == 0, "zona": ("Nacional", "Local", "Internacional")[(position - 1) % 3]}
    return document


def register_error(path: Path, file_hash: str, message: str) -> None:
    connection = pymysql.connect(**MYSQL_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO importaciones (nombre_archivo, hash_archivo, estado, mensaje_error)
                VALUES (%s, %s, 'ERROR', %s)
                ON DUPLICATE KEY UPDATE estado='ERROR', mensaje_error=VALUES(mensaje_error), fecha_importacion=CURRENT_TIMESTAMP
                """,
                (path.name, file_hash, message[:4000]),
            )
        connection.commit()
    finally:
        connection.close()


def move_file(path: Path, destination: Path, status: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = destination / f"{timestamp}_{status}_{path.name}"
    shutil.move(str(path), str(target))
    return target


def import_file(path: Path) -> None:
    LOGGER.info("Procesando %s", path.name)
    file_hash = calculate_sha256(path)
    previous = existing_import(file_hash)
    if previous is not None:
        LOGGER.warning("Fichero duplicado. Estado anterior: %s", previous["estado"])
        move_file(path, PROCESSED_DIR, "duplicado")
        return

    mysql = None
    mongo = None
    mongo_collection = None
    try:
        rows = read_and_validate_csv(path)
        mysql = pymysql.connect(**MYSQL_CONFIG)
        mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_collection = mongo[MONGO_DATABASE][MONGO_COLLECTION]

        with mysql.cursor() as cursor:
            cursor.execute(
                "INSERT INTO importaciones (nombre_archivo, hash_archivo, estado) VALUES (%s, %s, 'PROCESANDO')",
                (path.name, file_hash),
            )
            import_id = cursor.lastrowid
            cursor.executemany(
                """
                INSERT INTO movimientos (fecha,tipo,importe,categoria,producto,medio_pago,importacion_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                [(r["fecha"], r["tipo"], r["importe"], r["categoria"], r["producto"], r["medio_pago"], import_id) for r in rows],
            )

        documents = [build_mongo_document(row, import_id, file_hash, pos) for pos, row in enumerate(rows, start=1)]
        mongo_collection.insert_many(documents, ordered=True)

        with mysql.cursor() as cursor:
            cursor.execute(
                "UPDATE importaciones SET estado='IMPORTADO', filas_importadas=%s, mensaje_error=NULL WHERE id=%s",
                (len(rows), import_id),
            )
        mysql.commit()
        target = move_file(path, PROCESSED_DIR, "importado")
        LOGGER.info("Importación correcta: %s filas. Movido a %s", len(rows), target)

    except Exception as exc:
        LOGGER.exception("Error importando %s", path.name)
        if mysql is not None:
            mysql.rollback()
        if mongo_collection is not None:
            try:
                mongo_collection.delete_many({"movimiento_origen.hash_archivo": file_hash})
            except PyMongoError:
                LOGGER.exception("No se pudieron retirar documentos parciales de MongoDB.")
        register_error(path, file_hash, str(exc))
        LOGGER.error("Fichero movido a %s", move_file(path, ERROR_DIR, "error"))
    finally:
        if mysql is not None:
            mysql.close()
        if mongo is not None:
            mongo.close()


def main() -> None:
    ensure_directories()
    wait_for_services()
    LOGGER.info("Vigilando %s cada %s segundos.", INPUT_DIR, SCAN_INTERVAL)
    while True:
        for path in sorted(INPUT_DIR.glob("*.csv")):
            if time.time() - path.stat().st_mtime >= 2:
                import_file(path)
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
