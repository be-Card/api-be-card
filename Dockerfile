# Usar imagen base de Python
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv \
    && chmod 0755 /usr/local/bin/uv
ENV PATH="/usr/local/bin:$PATH"

# Copiar archivos de configuración del proyecto
COPY pyproject.toml uv.lock ./

# Instalar dependencias usando uv
RUN uv sync --frozen --no-dev

# Copiar código de la aplicación
COPY . .

# Crear usuario no-root para seguridad
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Exponer puerto
EXPOSE 8000

# Comando por defecto
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
