'''
01. Analisist datos movimientos_financieros
Pasos:
1. Visual Studio Code siepre con Open Folder
2. Crear un entorno virtual con venv para fijar las dependencias del proyecto y versión de Python
3. Crear un archivo requirements.txt con las dependencias del proyecto
pip freeze > requirements.txt
4. Instalar las dependencias del proyecto con 
pip install -r requirements.txt
'''

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Nombre esperado del fichero CSV
RUTA_CSV = Path("movimientos_financieros.csv")

# Si el fichero tiene el nombre usado al descargarlo, se utiliza como alternativa
if not RUTA_CSV.exists():
    alternativa = Path("movimientos_financieros(1).csv")
    if alternativa.exists():
        RUTA_CSV = alternativa
    else:
        raise FileNotFoundError(
            "No se ha encontrado movimientos_financieros.csv "
            "ni movimientos_financieros(1).csv en la carpeta actual."
        )


# ============================================================
# 5.1. CARGA E INSPECCIÓN INICIAL
# ============================================================

df_original = pd.read_csv(RUTA_CSV)
df = df_original.copy()

print("\nPRIMERAS FILAS")
print(df.head())

print("\nÚLTIMAS FILAS")
print(df.tail())

filas, columnas = df.shape
print(f"\nNúmero de filas: {filas}")
print(f"Número de columnas: {columnas}")

print("\nNombres de las columnas:")
print(df.columns.tolist())

print("\nTipos de datos:")
print(df.dtypes)

print("\nValores nulos por columna:")
print(df.isnull().sum())

numero_duplicados = df.duplicated().sum()
print(f"\nNúmero de filas duplicadas: {numero_duplicados}")

print("\nResumen estadístico inicial de los importes:")
print(df["Importe"].describe())


# ============================================================
# 5.2. PREPARACIÓN Y TRANSFORMACIÓN
# ============================================================

# Conversión de Fecha a datetime
df["Fecha"] = pd.to_datetime(
    df["Fecha"],
    errors="coerce",
    dayfirst=True
)

# Conversión de Importe a numérico
df["Importe"] = pd.to_numeric(
    df["Importe"],
    errors="coerce"
)

# Normalización de columnas de texto
columnas_texto = ["Tipo", "Categoria", "Producto", "Medio_pago"]

for columna in columnas_texto:
    if columna in df.columns:
        df[columna] = (
            df[columna]
            .astype("string")
            .str.strip()
        )

df["Tipo"] = df["Tipo"].str.capitalize()
df["Categoria"] = df["Categoria"].str.capitalize()
df["Medio_pago"] = df["Medio_pago"].str.capitalize()

# Correcciones concretas de escritura
df["Medio_pago"] = df["Medio_pago"].replace({
    "Paypal": "PayPal"
})

print("\nFechas no válidas tras la conversión:")
print(df["Fecha"].isnull().sum())

print("\nImportes no válidos tras la conversión:")
print(df["Importe"].isnull().sum())

# Eliminación opcional de registros que no pueden analizarse
df = df.dropna(subset=["Fecha", "Importe"]).copy()

# Creación de columnas temporales
df["Año"] = df["Fecha"].dt.year
df["Mes"] = df["Fecha"].dt.month
df["AñoMes"] = df["Fecha"].dt.to_period("M").astype(str)

# Creación del importe firmado
df["Importe_firmado"] = df["Importe"]

df.loc[
    df["Tipo"].eq("Gasto"),
    "Importe_firmado"
] = -df.loc[
    df["Tipo"].eq("Gasto"),
    "Importe"
]

print("\nDataFrame transformado:")
print(df.head())


# ============================================================
# 5.3. ANÁLISIS ECONÓMICO
# ============================================================

total_ingresos = df.loc[
    df["Tipo"].eq("Ingreso"),
    "Importe"
].sum()

total_gastos = df.loc[
    df["Tipo"].eq("Gasto"),
    "Importe"
].sum()

balance_neto = total_ingresos - total_gastos

print("\nRESULTADOS GENERALES")
print(f"Total de ingresos: {total_ingresos:.2f} €")
print(f"Total de gastos: {total_gastos:.2f} €")
print(f"Balance neto: {balance_neto:.2f} €")


# Resumen mensual
ingresos_mensuales = (
    df[df["Tipo"].eq("Ingreso")]
    .groupby("AñoMes")["Importe"]
    .sum()
)

gastos_mensuales = (
    df[df["Tipo"].eq("Gasto")]
    .groupby("AñoMes")["Importe"]
    .sum()
)

numero_movimientos = (
    df.groupby("AñoMes")
    .size()
)

resumen_mensual = pd.DataFrame({
    "Ingresos": ingresos_mensuales,
    "Gastos": gastos_mensuales,
    "Numero_movimientos": numero_movimientos
}).fillna(0)

resumen_mensual["Balance"] = (
    resumen_mensual["Ingresos"]
    - resumen_mensual["Gastos"]
)

resumen_mensual = resumen_mensual.sort_index()

print("\nRESUMEN MENSUAL")
print(resumen_mensual)


# Gastos por categoría
gastos_por_categoria = (
    df[df["Tipo"].eq("Gasto")]
    .groupby("Categoria")["Importe"]
    .sum()
    .sort_values(ascending=False)
)

print("\nGASTOS POR CATEGORÍA")
print(gastos_por_categoria)


# Productos que generan más ingresos
ingresos_por_producto = (
    df[df["Tipo"].eq("Ingreso")]
    .groupby("Producto")["Importe"]
    .sum()
    .sort_values(ascending=False)
)

print("\nINGRESOS POR PRODUCTO")
print(ingresos_por_producto)


# Medio de pago más utilizado
uso_medios_pago = df["Medio_pago"].value_counts()

print("\nUSO DE LOS MEDIOS DE PAGO")
print(uso_medios_pago)

if not uso_medios_pago.empty:
    medio_mas_utilizado = uso_medios_pago.idxmax()
    numero_usos = uso_medios_pago.max()

    print(
        f"\nEl medio de pago más utilizado es "
        f"{medio_mas_utilizado}, con {numero_usos} movimientos."
    )


# Mes con mayor beneficio y mes con mayores gastos
if not resumen_mensual.empty:
    mes_mayor_beneficio = resumen_mensual["Balance"].idxmax()
    mayor_beneficio = resumen_mensual["Balance"].max()

    mes_mayores_gastos = resumen_mensual["Gastos"].idxmax()
    mayores_gastos = resumen_mensual["Gastos"].max()

    print(
        f"\nMes con mayor beneficio: {mes_mayor_beneficio} "
        f"({mayor_beneficio:.2f} €)"
    )

    print(
        f"Mes con mayores gastos: {mes_mayores_gastos} "
        f"({mayores_gastos:.2f} €)"
    )


# ============================================================
# 5.4. VISUALIZACIONES
# ============================================================

# Gráfico 1: ingresos y gastos mensuales
plt.figure(figsize=(10, 5))

plt.plot(
    resumen_mensual.index,
    resumen_mensual["Ingresos"],
    marker="o",
    label="Ingresos"
)

plt.plot(
    resumen_mensual.index,
    resumen_mensual["Gastos"],
    marker="o",
    label="Gastos"
)

plt.title("Ingresos y gastos mensuales")
plt.xlabel("Mes")
plt.ylabel("Importe (€)")
plt.xticks(rotation=45)
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()


# Gráfico 2: balance mensual
plt.figure(figsize=(10, 5))

resumen_mensual["Balance"].plot(kind="bar")

plt.title("Balance neto mensual")
plt.xlabel("Mes")
plt.ylabel("Balance (€)")
plt.axhline(0, linewidth=1)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# Gráfico 3: gastos por categoría
plt.figure(figsize=(9, 5))

gastos_por_categoria.sort_values().plot(kind="barh")

plt.title("Gastos por categoría")
plt.xlabel("Gasto total (€)")
plt.ylabel("Categoría")
plt.tight_layout()
plt.show()


# Gráfico 4: productos con mayores ingresos
plt.figure(figsize=(10, 6))

ingresos_por_producto.head(10).sort_values().plot(kind="barh")

plt.title("Productos con mayores ingresos")
plt.xlabel("Ingresos (€)")
plt.ylabel("Producto")
plt.tight_layout()
plt.show()


# Gráfico 5: uso de medios de pago
plt.figure(figsize=(8, 5))

uso_medios_pago.plot(kind="bar")

plt.title("Uso de los medios de pago")
plt.xlabel("Medio de pago")
plt.ylabel("Número de movimientos")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# Gráfico 6 opcional: donut de medios de pago
plt.figure(figsize=(7, 7))

plt.pie(
    uso_medios_pago.values,
    labels=uso_medios_pago.index,
    autopct="%1.1f%%",
    startangle=90,
    wedgeprops={"width": 0.4}
)

plt.title("Distribución de los medios de pago")
plt.tight_layout()
plt.show()


# ============================================================
# EXPORTACIÓN DEL RESULTADO
# ============================================================

df.to_csv(
    "movimientos_financieros_transformados.csv",
    index=False
)

resumen_mensual.to_csv(
    "resumen_mensual.csv"
)

print("\nFicheros generados correctamente:")
print("- movimientos_financieros_transformados.csv")
print("- resumen_mensual.csv")
