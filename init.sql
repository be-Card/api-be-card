-- Archivo de inicialización para PostgreSQL
-- Se ejecuta automáticamente cuando se crea el contenedor

-- Crear extensiones útiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Configurar zona horaria
SET timezone = 'UTC-3';

-- Mensaje de confirmación
SELECT 'Base de datos BeCard inicializada correctamente' AS status;