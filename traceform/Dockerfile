FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libglib2.0-0 libsm6 libxext6 libxrender1 \
    libreoffice-writer libreoffice-impress fonts-noto-core fonts-noto-cjk fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 traceform && useradd --uid 10001 --gid traceform --create-home traceform
COPY traceform/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=traceform:traceform traceform/ .
COPY --chown=traceform:traceform docs/ /docs/
RUN mkdir -p /app/storage_data && chown traceform:traceform /app/storage_data
USER traceform
EXPOSE 8000
CMD ["/bin/sh", "/app/start.sh"]
