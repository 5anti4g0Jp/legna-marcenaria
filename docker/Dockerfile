# syntax=docker/dockerfile:1
# Motor de leitura de projetos de marcenaria. Contêiner de servidor (NÃO serverless): precisa do binário Tesseract.
#   Build:   docker build -f docker/Dockerfile --target runtime -t legna-leitor .
#   Testes:  docker build -f docker/Dockerfile --target test    -t legna-leitor-test . && docker run --rm legna-leitor-test
#   ODA File Converter (DWG), opcional: ponha o .deb (após aceitar a licença da ODA) em docker/oda/ e use
#            --build-arg ODA_DEB=ODAFileConverter_QT6_lnxX64_8.3dll_25.12.deb
#   Rede corporativa com inspeção TLS: ponha o certificado em docker/certs/*.crt (ignorado pelo git) e use
#            --build-arg HTTPS_PROXY=... --build-arg HTTP_PROXY=...  (e --network host se o proxy for local)
FROM python:3.13-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
COPY docker/certs/ /usr/local/share/ca-certificates/extra/
# HTTPS nas fontes do apt (alguns proxies só aceitam CONNECT) e certificado extra instalado ANTES do primeiro apt-get update
RUN update-ca-certificates \
 && sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements/ requirements/
RUN pip install -r requirements/base.txt -c requirements/constraints.txt

# ODA File Converter (opcional, ferramenta externa proprietária)
ARG ODA_DEB=""
COPY docker/oda/ /tmp/oda/
RUN if [ -n "$ODA_DEB" ]; then \
      apt-get update && apt-get install -y --no-install-recommends xvfb "/tmp/oda/$ODA_DEB" && rm -rf /var/lib/apt/lists/*; \
    fi

RUN useradd --create-home --uid 10001 app
COPY ingest/ ingest/

FROM base AS runtime
USER app
ENTRYPOINT ["python", "-m", "ingest.readers"]

FROM base AS test
RUN pip install -r requirements/dev.txt -c requirements/constraints.txt
ENV LEGNA_FIXTURES=/fixtures
COPY evaluation/ evaluation/
COPY tests_py/ tests_py/
COPY .gitignore .env.example ./
USER app
CMD ["python", "-m", "pytest", "tests_py", "-q", "-p", "no:cacheprovider"]
