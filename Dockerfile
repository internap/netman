FROM python:2.7-alpine

RUN apk update && apk add --no-cache python-dev gcc git g++ make libffi-dev openssl-dev libxml2 libxml2-dev libxslt libxslt-dev

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

RUN PBR_VERSION=0.0.0 pip install .

EXPOSE 5000
ENTRYPOINT [ "python" ]

CMD [ "netman/main.py", "--host=0.0.0.0"]