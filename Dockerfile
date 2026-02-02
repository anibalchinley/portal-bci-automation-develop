# 1. Usar una imagen base de Python ligera y oficial.
FROM python:3.11-slim

# 2. Establecer el directorio de trabajo dentro del contenedor.
WORKDIR /app

# 3. Instalar dependencias del sistema (curl para descargar y unzip para extraer).
RUN apt-get update && apt-get install -y curl unzip --no-install-recommends

# 4. Instalar Google Chrome desde Chrome for Testing (misma fuente que ChromeDriver)
# Esto asegura que Chrome y ChromeDriver tengan versiones compatibles
RUN CHROME_URL=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | python3 -c "import json, sys; data = json.load(sys.stdin); print([item['url'] for item in data['channels']['Stable']['downloads']['chrome'] if item['platform'] == 'linux64'][0])") && \
    wget -q $CHROME_URL -O /tmp/chrome.zip && \
    unzip -q /tmp/chrome.zip -d /tmp && \
    mv /tmp/chrome-linux64/chrome /usr/bin/google-chrome && \
    chmod +x /usr/bin/google-chrome && \
    rm -rf /tmp/chrome.zip /tmp/chrome-linux64

# 5. Instalar ChromeDriver correspondiente a la versión de Chrome.
# Este comando busca la URL de la última versión estable de ChromeDriver y la instala.
RUN LATEST_CHROMEDRIVER_URL=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | python3 -c "import json, sys; data = json.load(sys.stdin); print([item['url'] for item in data['channels']['Stable']['downloads']['chromedriver'] if item['platform'] == 'linux64'][0])") &&     wget -q $LATEST_CHROMEDRIVER_URL -O /tmp/chromedriver.zip &&     unzip /tmp/chromedriver.zip -d /usr/local/bin/ &&     mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver &&     rm -rf /usr/local/bin/chromedriver-linux64 /tmp/chromedriver.zip &&     chmod +x /usr/local/bin/chromedriver

# 6. Copiar el archivo de dependencias de Python e instalarlas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copiar el resto del código de la aplicación.
COPY . .

# 8. Exponer el puerto para Gunicorn.
EXPOSE 8000

# 9. Comando para ejecutar la aplicación en producción con Gunicorn.
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8000", "--timeout", "1800", "--workers", "1", "--keep-alive", "75"]
