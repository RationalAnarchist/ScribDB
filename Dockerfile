FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create defaults directory and copy config files there for initialization
RUN mkdir -p /app/defaults/config && \
    cp config/alembic.ini /app/defaults/config/alembic.ini && \
    cp config/config.json.example /app/defaults/config/config.json.example

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python", "run.py"]
