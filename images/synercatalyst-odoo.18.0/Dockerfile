# ==========================================
# Stage 1: Build & Compile Python Packages
# ==========================================
FROM python:3.13-slim-bookworm AS builder

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

# Install build-time compilers and development headers
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        make \
        libssl-dev \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        libpq-dev \
        libldap2-dev \
        libsasl2-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install super-fast package installer 'uv'
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY ./requirements.txt /requirements.txt

# Install all dependencies into system site-packages
RUN uv pip install --system --no-cache -r /requirements.txt


# ==========================================
# Stage 2: Final Minimal Runtime Image
# ==========================================
FROM python:3.13-slim-bookworm AS runner

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

ENV LANG=C.UTF-8
ENV ODOO_VERSION=18.0
ENV PYTHONPATH=/usr/lib/python3/dist-packages:/opt/odoo

# 1. Install ONLY runtime system libraries (no compilers/headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fonts-noto-cjk \
        fonts-dejavu-core \
        libpq5 \
        libldap-2.5-0 \
        libsasl2-2 \
        libxml2 \
        libxslt1.1 \
        libjpeg62-turbo \
        wkhtmltopdf \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 2. Copy compiled Python environment from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 3. Setup directories & non-root user
RUN id odoo || adduser --disabled-password --gecos '' odoo \
    && mkdir -p /var/lib/odoo /mnt/extra-addons /opt/odoo /usr/lib/python3/dist-packages \
    && chown -R odoo:odoo /var/lib/odoo /mnt/extra-addons /opt/odoo /usr/lib/python3/dist-packages

# 4. Copy scripts, config & entrypoints
COPY ./odoo /usr/local/bin/odoo
COPY ./entrypoint.sh /entrypoint.sh
COPY ./wait-for-psql.py /usr/local/bin/wait-for-psql.py
COPY ./odoo.conf /var/lib/odoo/odoo.conf

RUN chown odoo:odoo /var/lib/odoo/odoo.conf \
    && chmod 755 /entrypoint.sh /usr/local/bin/odoo /usr/local/bin/wait-for-psql.py

VOLUME ["/var/lib/odoo", "/mnt/extra-addons"]

EXPOSE 8069 8071 8072

ENV ODOO_RC=/var/lib/odoo/odoo.conf
ENV HOST=db
ENV PORT=5432
ENV USER=odoo
ENV PASSWORD=odoo

# Graceful shutdown & healthcheck
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8069/web/health || exit 1

USER odoo
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
