"""
Importa movimientos_financieros.csv en una tabla MySQL.

Compatible con Python 3.13.5.

Instalación:
    python -m pip install mysql-connector-python

Ejecución:
    python importar_datos.py
"""

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import mysql.connector
from mysql.connector import Error


# ============================================================
# CONFIGURACIÓN
# ============================================================

CONFIG_BD = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "root1234",
    "database": "finanzas",
}

# El CSV debe estar en la misma carpeta que este programa.
RUTA_CSV = Path(__file__).with_name("movimientos_financieros.csv")

COLUMNAS_ESPERADAS = {
    "Fecha",
    "Tipo",
    "Importe",
    "Categoria",
    "Producto",
    "Medio_pago",
}

SQL_INSERTAR = """
    INSERT INTO movimientos_financieros
        (fecha, tipo, importe, categoria, producto, medio_pago)
    VALUES
        (%s, %s, %s, %s, %s, %s)
"""


# ============================================================
# FUNCIONES
# ============================================================

def limpiar_texto(valor: str) -> str:
    """Elimina espacios innecesarios al principio y al final."""
    return valor.strip()


def convertir_fila(numero_fila: int, fila: dict) -> tuple:
    """
    Valida y transforma una fila del CSV en una tupla preparada
    para su inserción en MySQL.
    """
    try:
        fecha = datetime.strptime(
            limpiar_texto(fila["Fecha"]),
            "%Y-%m-%d",
        ).date()

        tipo = limpiar_texto(fila["Tipo"]).capitalize()
        if tipo not in {"Ingreso", "Gasto"}:
            raise ValueError(
                f"Tipo no válido: {tipo!r}. Debe ser 'Ingreso' o 'Gasto'."
            )

        importe_texto = limpiar_texto(fila["Importe"]).replace(",", ".")
        importe = Decimal(importe_texto)

        if importe < 0:
            raise ValueError("El importe no puede ser negativo.")

        categoria = limpiar_texto(fila["Categoria"])
        producto = limpiar_texto(fila["Producto"])
        medio_pago = limpiar_texto(fila["Medio_pago"])

        if not categoria:
            raise ValueError("La categoría está vacía.")

        if not producto:
            raise ValueError("El producto está vacío.")

        if not medio_pago:
            raise ValueError("El medio de pago está vacío.")

        return (
            fecha,
            tipo,
            importe,
            categoria,
            producto,
            medio_pago,
        )

    except KeyError as error:
        raise ValueError(
            f"Falta la columna {error.args[0]!r}."
        ) from error

    except (ValueError, InvalidOperation) as error:
        raise ValueError(
            f"Error en la fila {numero_fila}: {error}"
        ) from error


def leer_csv(ruta_csv: Path) -> list[tuple]:
    """Lee, valida y transforma todos los registros del CSV."""
    if not ruta_csv.exists():
        raise FileNotFoundError(
            f"No se encuentra el fichero CSV: {ruta_csv}"
        )

    registros = []

    with ruta_csv.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as fichero:
        lector = csv.DictReader(fichero, delimiter=",")

        if lector.fieldnames is None:
            raise ValueError("El CSV no contiene una fila de cabecera.")

        columnas_encontradas = {
            columna.strip() for columna in lector.fieldnames
        }

        columnas_faltantes = COLUMNAS_ESPERADAS - columnas_encontradas

        if columnas_faltantes:
            raise ValueError(
                "Faltan las siguientes columnas en el CSV: "
                + ", ".join(sorted(columnas_faltantes))
            )

        for numero_fila, fila in enumerate(lector, start=2):
            registros.append(convertir_fila(numero_fila, fila))

    return registros


def importar_registros(registros: list[tuple]) -> int:
    """Inserta todos los registros mediante una única transacción."""
    conexion = None
    cursor = None

    try:
        conexion = mysql.connector.connect(**CONFIG_BD)
        cursor = conexion.cursor()

        cursor.executemany(SQL_INSERTAR, registros)
        conexion.commit()

        return cursor.rowcount

    except Error:
        if conexion is not None:
            conexion.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        if conexion is not None and conexion.is_connected():
            conexion.close()


def main() -> None:
    """Punto de entrada del programa."""
    print(f"Leyendo CSV: {RUTA_CSV}")

    try:
        registros = leer_csv(RUTA_CSV)

        if not registros:
            print("El CSV no contiene registros para importar.")
            return

        print(f"Registros válidos encontrados: {len(registros)}")
        print("Conectando con MySQL...")

        total_insertados = importar_registros(registros)

        print("Importación completada correctamente.")
        print(f"Registros insertados: {total_insertados}")

    except FileNotFoundError as error:
        print(f"ERROR: {error}")

    except ValueError as error:
        print(f"ERROR DE DATOS: {error}")

    except Error as error:
        print(f"ERROR DE MYSQL: {error}")

    except Exception as error:
        print(f"ERROR INESPERADO: {error}")


if __name__ == "__main__":
    main()
