# BeCard API

API REST desarrollada con FastAPI, PostgreSQL y SQLModel para gestión de tarjetas de presentación.

## Características

- ✅ FastAPI para desarrollo rápido de APIs
- ✅ SQLModel como ORM (basado en Pydantic y SQLAlchemy)
- ✅ PostgreSQL como base de datos
- ✅ Documentación automática con Swagger UI
- ✅ Validación de datos con Pydantic
- ✅ CORS configurado
- ✅ Estructura modular y escalable

## Estructura del Proyecto

```
api-be-card/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py      # Configuración de la aplicación
│   │   └── database.py    # Configuración de la base de datos
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py        # Modelos de SQLModel
│   ├── routers/
│   │   ├── __init__.py
│   │   └── users.py       # Endpoints de usuarios
│   ├── schemas/
│   │   └── __init__.py
│   ├── __init__.py
│   └── main.py            # Aplicación FastAPI
├── .env                   # Variables de entorno
├── .env.example          # Ejemplo de variables de entorno
├── main.py               # Punto de entrada de la aplicación
├── requirements.txt      # Dependencias de Python
└── README.md
```

## Instalación

### Prerrequisitos

- Python 3.8+
- PostgreSQL 12+

### Pasos de instalación

1. **Clonar el repositorio**
   ```bash
   git clone <url-del-repositorio>
   cd api-be-card
   ```

2. **Crear entorno virtual**
   ```bash
   python -m venv venv
   
   # En Windows
   venv\Scripts\activate
   
   # En Linux/Mac
   source venv/bin/activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar base de datos**
   - Crear una base de datos PostgreSQL llamada `becard_db`
   - Actualizar las credenciales en el archivo `.env`

5. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tus configuraciones
   ```

## Configuración

Edita el archivo `.env` con tus configuraciones:

```env
DATABASE_URL=postgresql://beCard:beCard2025.@localhost:5432/becard_db
APP_NAME=BeCard API
DEBUG=true
HOST=0.0.0.0
PORT=8000
SECRET_KEY=your-secret-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Uso con Docker (Recomendado)

### Ejecutar con Docker Compose

```bash
# Construir y ejecutar todos los servicios
docker-compose up --build

# Ejecutar en segundo plano
docker-compose up -d --build

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down

# Detener y eliminar volúmenes
docker-compose down -v
```

### Servicios incluidos

- **API**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **pgAdmin**: http://localhost:5050

### Uso sin Docker

#### Ejecutar la aplicación

```bash
python main.py
```

O usando uvicorn directamente:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Acceder a la documentación

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints disponibles

#### Usuarios

- `POST /api/v1/users/` - Crear usuario
- `GET /api/v1/users/` - Listar usuarios
- `GET /api/v1/users/{user_id}` - Obtener usuario por ID
- `PUT /api/v1/users/{user_id}` - Actualizar usuario
- `DELETE /api/v1/users/{user_id}` - Eliminar usuario

#### Otros

- `GET /` - Información de la API
- `GET /health` - Estado de salud de la API

## Ejemplo de uso

### Crear un usuario

```bash
curl -X POST "http://localhost:8000/api/v1/users/" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Juan Pérez",
       "email": "juan@example.com"
     }'
```

### Obtener todos los usuarios

```bash
curl -X GET "http://localhost:8000/api/v1/users/"
```

## Desarrollo

### Agregar nuevos modelos

1. Crear el modelo en `app/models/`
2. Importar el modelo en `app/models/__init__.py`
3. Crear los endpoints en `app/routers/`
4. Incluir el router en `app/main.py`

### Migraciones de base de datos

Para usar Alembic para migraciones:

```bash
# Inicializar Alembic
alembic init alembic

# Crear migración
alembic revision --autogenerate -m "Descripción del cambio"

# Aplicar migración
alembic upgrade head
```

## Docker

### Comandos útiles de Docker

```bash
# Ver contenedores en ejecución
docker ps

# Ver logs de un servicio específico
docker-compose logs api
docker-compose logs postgres

# Ejecutar comandos dentro del contenedor de la API
docker-compose exec api bash

# Ejecutar comandos en PostgreSQL
docker-compose exec postgres psql -U beCard -d becard_db

# Reconstruir solo la API
docker-compose build api

# Reiniciar un servicio específico
docker-compose restart api
```

### Acceso a la base de datos

**Usando pgAdmin (interfaz web):**
- URL: http://localhost:5050
- Email: admin@becard.com
- Contraseña: beCard2025.

**Para conectar a PostgreSQL desde pgAdmin:**
- Host: postgres
- Puerto: 5432
- Usuario: usuario
- Contraseña: beCard2025.
- Base de datos: becard_db

**Usando psql directamente:**
```bash
docker-compose exec postgres psql -U beCard -d becard_db
```

### Troubleshooting

**Si la API no puede conectar a PostgreSQL:**
```bash
# Verificar que PostgreSQL esté saludable
docker-compose ps

# Reiniciar servicios en orden
docker-compose down
docker-compose up postgres -d
# Esperar unos segundos
docker-compose up api -d
```

**Para desarrollo con hot-reload:**
El docker-compose ya está configurado con volúmenes para hot-reload automático.

## Tecnologías utilizadas

- **FastAPI**: Framework web moderno y rápido
- **SQLModel**: ORM moderno que combina SQLAlchemy y Pydantic
- **PostgreSQL**: Base de datos relacional robusta
- **Uvicorn**: Servidor ASGI de alto rendimiento
- **Pydantic**: Validación de datos usando type hints de Python
- **Docker**: Containerización para desarrollo y despliegue
