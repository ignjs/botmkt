# Dockerfile optimizado para Cloud Run (Free Tier)
FROM python:3.11-slim

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalación de dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalación de dependencias Python
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copia del código fuente
COPY . .

# Puerto para Cloud Run
ENV PORT=8080
EXPOSE 8080

# Comando de inicio
CMD ["gunicorn", "main:app", "-b", ":8080", "--workers", "1"]
