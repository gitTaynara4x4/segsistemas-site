FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend ./frontend
RUN cp ./frontend/inicio.html ./index.html

EXPOSE 2932

CMD ["python", "-m", "http.server", "2932", "--bind", "0.0.0.0"]
