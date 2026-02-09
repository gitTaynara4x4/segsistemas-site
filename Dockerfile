FROM python:3.12-slim

WORKDIR /app

# instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copia o projeto inteiro (backend + frontend)
COPY . .

# porta do seu app no EasyPanel
EXPOSE 2932

# inicia o FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "2932"]
