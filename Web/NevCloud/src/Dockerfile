FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd -m ctfuser && chown -R ctfuser:ctfuser /app
COPY flag.txt /flag.txt
RUN chmod 644 /flag.txt

USER ctfuser

EXPOSE 5000
CMD ["python", "app.py"]
