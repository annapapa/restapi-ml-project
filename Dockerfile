# Use Python 3.11 for better performance and modern features
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY feddit_api/ feddit_api/

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8082

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8082/healthz || exit 1

# Run the application
CMD ["uvicorn", "feddit_api.main:app", "--host", "0.0.0.0", "--port", "8082"] 