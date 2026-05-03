# Based on Odoo's official dockerfile
# github.com/odoo/docker
#
# Image: synercatalyst/odoo.13.0:latest
# Supports: linux/amd64, linux/arm64

FROM debian:bookworm-slim

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

ENV LANG C.UTF-8
ENV PERFEECTWORK_VERSION=3.2
ENV PERFECTWORK_RELEASE=latest
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

RUN set -x; \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            ca-certificates \
            curl \
            dirmngr \
            fonts-noto-cjk \
            gnupg \
            libssl-dev \
            node-less \
            npm \
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
            wkhtmltopdf \
            postgresql-client \
        && rm -rf /var/lib/apt/lists/*

RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ bookworm-pgdg main' > /etc/apt/sources.list.d/pgdg.list \
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
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

RUN npm config set unsafe-perm true \
    && npm install -g rtlcss --production=true \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

ENV ODOO_VERSION 13.0
ARG ODOO_RELEASE=20211213
ARG ODOO_SHA=acbb9ee40e8998751d9eb632444c1fc1e105766d
RUN set -x; \
       curl -o odoo.deb -sSL http://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/odoo_${ODOO_VERSION}.${ODOO_RELEASE}_all.deb \
      && echo "${ODOO_SHA} odoo.deb" | sha1sum -c - \
      && dpkg --force-depends -i odoo.deb \
      && apt-get update \
      && apt-get -y install -f --no-install-recommends \
      && rm -rf /var/lib/apt/lists/* odoo.deb \
      && rm -rf /usr/lib/python3/dist-packages/odoo

COPY ./entrypoint.sh /
COPY ./requirements.txt /
COPY ./pw.conf /var/lib/odoo/
RUN chown odoo /var/lib/odoo/pw.conf \
    && mkdir -p /mnt/extra-addons \
    && chown -R odoo /mnt/extra-addons \
    && chmod 755 /entrypoint.sh

RUN set -x; \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            python3-paramiko

RUN set -x; \
    pip3 install --no-cache-dir wheel \
    && pip3 install --no-cache-dir --upgrade -r /requirements.txt \
    && rm -rf /root/.cache/pip

VOLUME ["/var/lib/odoo", "/mnt/extra-addons", "/usr/lib/python3/dist-packages/odoo"]

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py

EXPOSE 8069 8071 8072

ENV ODOO_RC /var/lib/odoo/pw.conf
ENV HOST db
ENV USER odoo
ENV PASSWORD odoo

USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]