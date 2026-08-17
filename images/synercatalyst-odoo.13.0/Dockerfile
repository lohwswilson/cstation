# Based on Odoo's official dockerfile
# github.com/odoo/docker
#
# Image: synercatalyst/odoo.13.0:latest
# Supports: linux/amd64, linux/arm64

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

ENV LANG=C.UTF-8
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
            python3-babel \
            python3-decorator \
            python3-docutils \
            python3-gevent \
            python3-jinja2 \
            python3-libsass \
            python3-lxml \
            python3-mako \
            python3-mock \
            python3-num2words \
            python3-ofxparse \
            python3-passlib \
            python3-pdfminer \
            python3-phonenumbers \
            python3-pip \
            python3-polib \
            python3-psutil \
            python3-psycopg2 \
            python3-pydot \
            python3-pyparsing \
            python3-pypdf2 \
            python3-pyldap \
            python3-qrcode \
            python3-renderpm \
            python3-requests \
            python3-serial \
            python3-setuptools \
            python3-slugify \
            python3-tz \
            python3-usb \
            python3-vobject \
            python3-watchdog \
            python3-werkzeug \
            python3-xlrd \
            python3-xlwt \
            python3-xlsxwriter \
            python3-zeep \
            python3-paramiko \
            equivs \
            xz-utils \
            wkhtmltopdf \
            postgresql-client \
        && rm -rf /var/lib/apt/lists/*

# install latest postgresql-client
RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ jammy-pgdg main' > /etc/apt/sources.list.d/pgdg.list \
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

RUN npm install -g rtlcss \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

ENV ODOO_VERSION=13.0
ARG ODOO_RELEASE=20230601
ARG ODOO_SHA=0696891e5d393a8cad359bbab5542cd23b2edc99

RUN printf "Section: python\nPriority: optional\nPackage: python3-vatnumber\nVersion: 1.0\nDescription: dummy package for odoo\n" > vatnumber-dummy \
    && equivs-build vatnumber-dummy \
    && dpkg -i python3-vatnumber_1.0_all.deb \
    && rm vatnumber-dummy python3-vatnumber_1.0_all.deb

RUN set -x; \
       curl -o odoo.deb -sSL http://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/odoo_${ODOO_VERSION}.${ODOO_RELEASE}_all.deb \
      && echo "${ODOO_SHA} odoo.deb" | sha1sum -c - \
      && dpkg --force-depends -i odoo.deb \
      && rm -rf /var/lib/apt/lists/* odoo.deb

RUN python3 -c "p='/usr/lib/python3/dist-packages/odoo/service/server.py';c=open(p).read();c=c.replace(\"config['limit_memory_hard']\",\"int(config['limit_memory_hard'])\").replace(\"cpu_time + config['limit_time_cpu']\",\"int(cpu_time + config['limit_time_cpu'])\");open(p,'w').write(c)"

COPY ./entrypoint.sh /
COPY ./requirements.txt /
COPY ./odoo.conf /var/lib/odoo/
RUN mkdir -p /var/lib/odoo /mnt/extra-addons \
    && id odoo || adduser --disabled-password --gecos '' odoo \
    && chown odoo /var/lib/odoo/odoo.conf \
    && chown -R odoo /mnt/extra-addons \
    && chmod 755 /entrypoint.sh

RUN set -x; \
    pip3 install --no-cache-dir wheel \
    && pip3 install --no-cache-dir --force-reinstall --ignore-installed 'werkzeug<1.0' \
    && rm -rf /usr/lib/python3/dist-packages/werkzeug* \
    && pip3 install --no-cache-dir --upgrade -r /requirements.txt \
    && rm -rf /root/.cache/pip

VOLUME ["/var/lib/odoo", "/mnt/extra-addons"]

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py

EXPOSE 8069 8071 8072

ENV ODOO_RC=/var/lib/odoo/odoo.conf
ENV HOST=db
ENV USER=odoo
ENV PASSWORD=odoo

USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]