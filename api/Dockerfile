FROM python:3.12-slim

WORKDIR /app

# Evita criação de .pyc e usa stdout sem buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dependências Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# Código da API
COPY app/ ./app/

# Variáveis padrão do Flask
ENV FLASK_APP=app.app:app
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8000

EXPOSE 8000

CMD ["flask", "run"]