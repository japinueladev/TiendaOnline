# Solución — Etapa 4: Docker Compose con importación automatizada

## 1. Decisiones técnicas

La solución utiliza MySQL 8.4, MongoDB 8, Python 3.14 y Jupyter. El importador se conecta directamente con `PyMySQL` y `pymongo`. No se utiliza SQLAlchemy.

La dependencia `cryptography` se instala expresamente porque PyMySQL la necesita para autenticar usuarios de MySQL que utilizan `caching_sha2_password` o `sha256_password`.

## 2. Arranque

```bash
docker compose up -d --build
```

Comprobar servicios:

```bash
docker compose ps
docker compose logs -f importer
```

El fichero incluido en `data/entrada` se detecta automáticamente. Si la carga termina correctamente, se mueve a `data/procesados`.

## 3. Flujo automatizado

```text
CSV en entrada
   ↓
validación de cabecera, fechas, tipos e importes
   ↓
hash SHA-256 y control de duplicados
   ↓
MySQL: movimientos estructurados e historial
   ↓
MongoDB: documentos enriquecidos
   ↓
procesados o errores
```

## 4. DBeaver

```text
Host: localhost
Puerto: 3308
Base de datos: finanzas
Usuario: alumno
Contraseña: alumno123
```

Consultas:

```sql
SELECT * FROM importaciones ORDER BY fecha_importacion DESC;
SELECT COUNT(*) AS movimientos FROM movimientos;

SELECT
    DATE_FORMAT(fecha, '%Y-%m') AS anio_mes,
    SUM(CASE WHEN tipo='Ingreso' THEN importe ELSE 0 END) AS ingresos,
    SUM(CASE WHEN tipo='Gasto' THEN importe ELSE 0 END) AS gastos,
    SUM(CASE WHEN tipo='Ingreso' THEN importe ELSE -importe END) AS balance,
    COUNT(*) AS movimientos
FROM movimientos
GROUP BY DATE_FORMAT(fecha, '%Y-%m')
ORDER BY anio_mes;
```

## 5. MongoDB Compass

```text
mongodb://admin:admin123@localhost:27017/?authSource=admin
```

Base de datos: `finanzas_nosql`  
Colección: `movimientos`

```javascript
db.movimientos.countDocuments({})
db.movimientos.findOne()
db.movimientos.find({ etiquetas: "importe-alto" })

db.movimientos.aggregate([
  {
    $group: {
      _id: "$tipo",
      total: { $sum: "$importe" },
      operaciones: { $sum: 1 }
    }
  }
])
```

## 6. Jupyter

```text
URL: http://localhost:8888
Token: bigdata
```

Abra `analisis_integrado.ipynb`.

## 7. Prueba de duplicado

Vuelva a copiar el mismo CSV en `data/entrada`. El importador calculará el mismo hash y lo moverá como duplicado sin volver a insertar movimientos.

## 8. Prueba de error

Copie `data/ejemplo_error_importe.csv` dentro de `data/entrada`. El importador detectará el importe no numérico, registrará el error en MySQL y moverá el fichero a `data/errores`.

## 9. Persistencia

Detener conservando los datos:

```bash
docker compose down
```

Eliminar también los volúmenes:

```bash
docker compose down -v
```

## 10. Reconstrucción del importador

Después de modificar `importer.py` o `requirements.txt`:

```bash
docker compose up -d --build importer
```

Reconstrucción completa sin caché:

```bash
docker compose build --no-cache importer
docker compose up -d
```

## 11. Dependencias Python

```text
PyMySQL==1.1.1
cryptography>=46.0.0
pymongo>=4.10.0
```

No se emplea SQLAlchemy. Las operaciones MySQL utilizan cursores, consultas parametrizadas y transacciones de PyMySQL.
