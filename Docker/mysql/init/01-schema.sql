USE finanzas;

CREATE TABLE IF NOT EXISTS importaciones (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nombre_archivo VARCHAR(255) NOT NULL,
    hash_archivo CHAR(64) NOT NULL,
    fecha_importacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    filas_importadas INT UNSIGNED NOT NULL DEFAULT 0,
    estado ENUM('PROCESANDO', 'IMPORTADO', 'ERROR', 'DUPLICADO') NOT NULL,
    mensaje_error TEXT NULL,
    UNIQUE KEY uq_importaciones_hash (hash_archivo)
);

CREATE TABLE IF NOT EXISTS movimientos (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    fecha DATE NOT NULL,
    tipo ENUM('Ingreso', 'Gasto') NOT NULL,
    importe DECIMAL(12, 2) NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    producto VARCHAR(255) NOT NULL,
    medio_pago VARCHAR(100) NOT NULL,
    importacion_id BIGINT UNSIGNED NOT NULL,
    fecha_carga DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_movimientos_importacion FOREIGN KEY (importacion_id) REFERENCES importaciones(id),
    INDEX idx_movimientos_fecha (fecha),
    INDEX idx_movimientos_tipo (tipo),
    INDEX idx_movimientos_categoria (categoria)
);
