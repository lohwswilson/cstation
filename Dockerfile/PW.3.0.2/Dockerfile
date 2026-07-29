# Based on Odoo's official dockerfile
# github.com/odoo/docker
#
# Image: synercatalyst/odoo.13.0:latest
# Supports: linux/amd64, linux/arm64

FROM ubuntu:jammy
LABEL maintainer="Odoo S.A. <info@odoo.com>"

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
ENV LANG=C.UTF-8
ENV PERFEECTWORK_VERSION=3.2
ENV PERFECTWORK_RELEASE=latest
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1
ARG TARGETARCH

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
            python3-ldap \
            python3-qrcode \
            python3-renderpm \
            python3-setuptools \
            python3-slugify \
            python3-vobject \
            python3-watchdog \
            python3-xlrd \
            python3-xlwt \
            xz-utils \
            equivs \
        && if [ -z "${TARGETARCH}" ]; then TARGETARCH="$(dpkg --print-architecture)"; fi \
        && WKHTMLTOPDF_ARCH="${TARGETARCH}" \
        && case "${TARGETARCH}" in \
            "amd64") WKHTMLTOPDF_ARCH=amd64 WKHTMLTOPDF_SHA=967390a759707337b46d1c02452e2bb6b2dc6d59 ;; \
            "arm64") WKHTMLTOPDF_SHA=90f6e69896d51ef77339d3f3a20f8582bdf496cc ;; \
            "ppc64le" | "ppc64el") WKHTMLTOPDF_ARCH=ppc64el WKHTMLTOPDF_SHA=5312d7d34a25b321282929df82e3574319aed25c ;; \
            *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
        esac \
        && curl -o wkhtmltox.deb -sSL "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_${WKHTMLTOPDF_ARCH}.deb" \
        && echo "${WKHTMLTOPDF_SHA} wkhtmltox.deb" | sha1sum -c - \
        && apt-get install -y --no-install-recommends ./wkhtmltox.deb \
        && rm -rf /var/lib/apt/lists/* wkhtmltox.deb

RUN printf "Section: python\nPriority: optional\nPackage: python3-vatnumber\nVersion: 1.0\nDescription: dummy package for odoo\n" > vatnumber-dummy \
    && equivs-build vatnumber-dummy \
    && dpkg -i python3-vatnumber_1.0_all.deb \
    && rm vatnumber-dummy python3-vatnumber_1.0_all.deb

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
    && npm cache clean --force

ENV ODOO_VERSION=13.0
ARG ODOO_RELEASE=20230601
ARG ODOO_SHA=0696891e5d393a8cad359bbab5542cd23b2edc99
RUN set -x; \
      ODOO_DEB_URL="https://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/odoo_${ODOO_VERSION}.${ODOO_RELEASE}_all.deb" \
      && rm -f odoo.deb.part \
      && for _ in {1..10}; do \
            curl -fL --http1.1 --retry 10 --retry-all-errors --retry-delay 5 --connect-timeout 30 -o odoo.deb.part -C - "${ODOO_DEB_URL}" && break; \
            sleep 5; \
        done \
      && mv odoo.deb.part odoo.deb \
      && echo "${ODOO_SHA} odoo.deb" | sha1sum -c - \
      && dpkg --force-depends -i odoo.deb \
      && apt-get update \
      && apt-get -y install -f --no-install-recommends \
      && rm -rf /var/lib/apt/lists/* odoo.deb \
      && rm -rf /usr/lib/python3/dist-packages/odoo

RUN set -x; \
    mkdir -p /var/lib/odoo \
    && if ! getent group odoo >/dev/null 2>&1; then addgroup --system odoo; fi \
    && if ! id -u odoo >/dev/null 2>&1; then adduser --system --ingroup odoo --home /var/lib/odoo --shell /bin/bash odoo; fi

COPY ./entrypoint.sh /
COPY ./requirements.txt /
COPY ./odoo /usr/local/bin/odoo
COPY ./pw.conf /var/lib/odoo/
COPY ./odoo.conf /var/lib/odoo/
RUN chown odoo /var/lib/odoo/pw.conf \
    && mkdir -p /mnt/extra-addons \
    && chown -R odoo /mnt/extra-addons \
    && chmod 755 /entrypoint.sh \
    && chmod 755 /usr/local/bin/odoo

RUN set -x; \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            python3-paramiko

RUN set -x; \
    pip3 install --no-cache-dir --force-reinstall --ignore-installed 'werkzeug<1.0' \
    && rm -rf /usr/lib/python3/dist-packages/werkzeug* \
    && pip3 install --no-cache-dir wheel \
    && pip3 install --no-cache-dir --upgrade -r /requirements.txt \
    && rm -rf /root/.cache/pip

VOLUME ["/var/lib/odoo", "/mnt/extra-addons", "/usr/lib/python3/dist-packages/odoo"]

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py

EXPOSE 8069 8071 8072

ENV ODOO_RC=/var/lib/odoo/pw.conf
ENV HOST=db
ENV USER=odoo

USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
