FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY config.py .
COPY gunicorn.conf.py .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port
EXPOSE 5000

# Start application
CMD ["gunicorn", "app.main:create_app()", "-c", "gunicorn.conf.py"]
