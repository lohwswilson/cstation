FROM debian:bullseye-slim

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

# Generate locale C.UTF-8 for postgres and general locale data
ENV LANG C.UTF-8
ENV PERFEECTWORK_VERSION=6.0
ENV PERFECTWORK_RELEASE=latest
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1
ENV DEBIAN_FRONTEND=noninteractivechainl

# Install some deps, lessc and less-plugin-clean-css, and wkhtmltopdf
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        dirmngr \
        fonts-noto-cjk \
        gnupg \
        libssl-dev \
        node-less \
        npm \
        python3-magic \
        python3-num2words \
        python3-pdfminer \
        python3-pip \
        python3-phonenumbers \
        python3-pyldap \
        python3-qrcode \
        python3-renderpm \
        python3-setuptools \
        python3-slugify \
        python3-vobject \
        python3-watchdog \
        python3-xlrd \
        python3-xlwt \
        xz-utils \
        # wkhtmltopdf \
    && curl -o wkhtmltox.deb -sSL https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.5/wkhtmltox_0.12.5-1.buster_amd64.deb \
    && echo 'ea8277df4297afc507c61122f3c349af142f31e5 wkhtmltox.deb' | sha1sum -c - \
    && apt-get install -y --no-install-recommends ./wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/* wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/* 

# install latest postgresql-client
RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ bullseye-pgdg main' > /etc/apt/sources.list.d/pgdg.list \
    && GNUPGHOME="$(mktemp -d)" \
    && export GNUPGHOME \
    && repokey='B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8' \
    && gpg --batch --keyserver keyserver.ubuntu.com --recv-keys "${repokey}" \
    && gpg --batch --armor --export "${repokey}" > /etc/apt/trusted.gpg.d/pgdg.gpg.asc \
    && gpgconf --kill all \
    && rm -rf "$GNUPGHOME" \
    && apt-get update  \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -f /etc/apt/sources.list.d/pgdg.list \
    && rm -rf /var/lib/apt/lists/*

# Install rtlcss (on Debian buster)
RUN npm install -g rtlcss \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

# Install Odoo and remove odoo files at /usr/lib/python3/dist-packages/odoo*
ENV ODOO_VERSION 16.0
ARG ODOO_RELEASE=20230710
ARG ODOO_SHA=faf46a6ddcf6a8d4d30a743c389db0e414071ce4
RUN curl -o odoo.deb -sSL http://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/odoo_${ODOO_VERSION}.${ODOO_RELEASE}_all.deb \
    && echo "${ODOO_SHA} odoo.deb" | sha1sum -c - \
    && apt-get update \
    && apt-get -y install --no-install-recommends ./odoo.deb \
    && rm -rf /var/lib/apt/lists/* odoo.deb \
    && rm -rf /usr/lib/python3/dist-packages/odoo

# Copy entrypoint script and Odoo configuration file
COPY ./entrypoint.sh /
COPY ./wait-for-psql.py /
COPY ./requirements.txt /

# **** Install extra python libraries for PW ****
RUN set -x; \
    pip3 install --no-cache-dir -r /requirements.txt 

# Set permissions and Mount /var/lib/odoo to allow restoring filestore and /mnt/extra-addons for users addons
RUN chown odoo /entrypoint.sh \
    && mkdir -p /mnt \
    && chown -R odoo /mnt

VOLUME ["/var/lib/odoo", "/mnt", "/usr/lib/python3/dist-packages/odoo"]

# Expose Odoo services
EXPOSE 8069 8071 8072

# Set the default config file
ENV ODOO_RC /var/lib/odoo/pw.conf

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py

RUN chmod +x entrypoint.sh \
    && chmod 755 /usr/local/bin/wait-for-psql.py

# Set default user when running the container
USER odoo


ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]