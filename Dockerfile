# Usa uma imagem leve do Python
FROM python:3.9-slim

# 1. Instala as dependências do sistema para o WeasyPrint (PDF)
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Configura a pasta de trabalho
WORKDIR /app

# 3. Copia os arquivos do projeto para dentro do container
COPY . /app

# 4. Instala as bibliotecas do Python
RUN pip install --no-cache-dir -r requirements.txt

# 5. Comando para iniciar o site (usando Gunicorn para produção)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:10000", "app:app"]