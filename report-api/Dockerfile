FROM python:3.12.2-bullseye

ARG VCS_REF="missing"
ARG BUILD_DATE="missing"

ENV VCS_REF=${VCS_REF}
ENV BUILD_DATE=${BUILD_DATE}

LABEL org.label-schema.vcs-ref=${VCS_REF} \
    org.label-schema.build-date=${BUILD_DATE}


RUN apt-get -y update && apt-get install -y build-essential python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

RUN apt-get install -y fontforge
RUN apt-get install -y cabextract
RUN wget https://gist.github.com/maxwelleite/10774746/raw/ttf-vista-fonts-installer.sh -q -O - | bash

COPY . /app
WORKDIR /app

RUN python3 -m pip install -r requirements.txt
RUN python3 setup.py install


EXPOSE 5001

ENV NUM_WORKERS=3
ENV TIMEOUT=360

CMD gunicorn --bind 0.0.0.0:5001 --timeout $TIMEOUT --workers $NUM_WORKERS  wsgi:application
