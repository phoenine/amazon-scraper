FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 scraper && chown -R scraper:scraper /app
USER scraper

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "run.py"]