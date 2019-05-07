FROM python:2.7-alpine

ENV APP_EXPOSED_PORT 5000

RUN apk update && apk add --no-cache python-dev gcc git g++ make libffi-dev openssl-dev pcre-dev libxml2 libxml2-dev libxslt libxslt-dev curl

ENV APP_ROOT /usr/src/app

RUN mkdir -p $APP_ROOT
WORKDIR $APP_ROOT

COPY requirements.txt $APP_ROOT
RUN pip install --no-cache-dir -r requirements.txt

COPY . $APP_ROOT

RUN PBR_VERSION=0.0.0 pip install .

EXPOSE $APP_EXPOSED_PORT

HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://localhost:$APP_EXPOSED_PORT/healthcheck
ENTRYPOINT uwsgi --ini uwsgi.ini
