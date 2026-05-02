#Partially from Odoo's dockerfile
#github.com/odoo/docker

FROM debian:buster-slim

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

# Generate locale C.UTF-8 for postgres and general locale data
ENV LANG C.UTF-8
ENV PERFEECTWORK_VERSION=3.1
ENV PERFECTWORK_RELEASE=latest
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

# Install some deps, lessc and less-plugin-clean-css, and wkhtmltopdf
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
        # && curl -o wkhtmltox.deb -sSL https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.5/wkhtmltox_0.12.5-1.stretch_amd64.deb \
        # && echo '7e35a63f9db14f93ec7feeb0fce76b30c08f2057 wkhtmltox.deb' | sha1sum -c - \
        # && apt-get install -y --no-install-recommends ./wkhtmltox.deb \
        # && rm -rf /var/lib/apt/lists/* wkhtmltox.deb
        && rm -rf /var/lib/apt/lists/* 

# install latest postgresql-client
RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ buster-pgdg main' > /etc/apt/sources.list.d/pgdg.list \
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

# Install rtlcss (on Debian buster)
# To handle 'not get uid/gid'
RUN npm config set unsafe-perm true \
    && npm install -g rtlcss --production=true \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

# Move PW files into Container and move to the right directories
# ADD ./PW /PW
# RUN adduser --disabled-password --gecos '' odoo

# Install Odoo
ENV ODOO_VERSION 13.0
ARG ODOO_RELEASE=20211213
ARG ODOO_SHA=acbb9ee40e8998751d9eb632444c1fc1e105766d
RUN set -x; \
       curl -o odoo.deb -sSL http://nightly.odoo.com/${ODOO_VERSION}/nightly/deb/odoo_${ODOO_VERSION}.${ODOO_RELEASE}_all.deb \
      && echo "${ODOO_SHA} odoo.deb" | sha1sum -c - \
      && dpkg --force-depends -i odoo.deb \
      && apt-get update \
      && apt-get -y install -f --no-install-recommends \
      # PW Customization
      # && /PW/pw_customize \
      && rm -rf /var/lib/apt/lists/* odoo.deb \
      && rm -rf /usr/lib/python3/dist-packages/odoo

# Odoo container will use the shared volume for application code
# /usr/lib/python3/dist-packages/odoo

# Copy entrypoint script and Odoo configuration file
COPY ./entrypoint.sh /
COPY ./requirements.txt /
# COPY ./odoo.conf /etc/odoo/
# Mount /var/lib/odoo to allow restoring filestore and /mnt/extra-addons for users addons
COPY ./pw.conf /var/lib/odoo/
RUN chown odoo /var/lib/odoo/pw.conf \
    &&  mkdir -p /mnt/extra-addons \
    && chown -R odoo /mnt/extra-addons \
    && chmod 755 ./entrypoint.sh

RUN set -x; \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            python3-paramiko 

# **** Install extra python libraries for PW ****
RUN set -x; \
    pip3 install --no-cache-dir wheel \
    && pip3 install --no-cache-dir --upgrade -r /requirements.txt 

# Mount /var/lib/odoo to allow restoring filestore and /mnt/extra-addons for users addons

VOLUME ["/var/lib/odoo", "/mnt/extra-addons", "/usr/lib/python3/dist-packages/odoo"]

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py

# Expose Odoo services
EXPOSE 8069 8071 8072

# Set the default config file
ENV ODOO_RC /var/lib/odoo/pw.conf
ENV HOST SG03_DB
ENV USER pw_db_admin
ENV PASSWORD wai39kua

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py

# Set default user when running the containerpwd
USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
