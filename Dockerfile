FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libmagic1 \
    libpq-dev \
    gcc \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libfontconfig1 \
    libfreetype6 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY pflegeos/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pflegeos/ .

RUN chmod +x /app/start.sh

EXPOSE 5000

CMD ["/app/start.sh"]
