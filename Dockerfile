# Usar imagen oficial de Selenium que ya tiene Chrome/ChromeDriver configurados
FROM selenium/standalone-chromium:latest

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar Python y dependencias
RUN mkdir -p /var/lib/apt/lists/partial && apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    --no-install-recommends

# Copiar el archivo de dependencias de Python e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto para Gunicorn
EXPOSE 8000

# CMD para ejecutar la aplicación
CMD ["python3", "-m", "gunicorn", "main:app", "--bind", "0.0.0.0:8000", "--timeout", "1800", "--workers", "1", "--keep-alive", "75"]
