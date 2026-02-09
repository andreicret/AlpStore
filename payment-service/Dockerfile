FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY payment-service.py .

EXPOSE 7001
CMD ["python", "payment-service.py"]
