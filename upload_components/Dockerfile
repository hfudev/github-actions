FROM python:3.9-slim-buster

COPY component-manager/ /component-manager

RUN pip install -e component-manager

COPY upload.sh /upload.sh

ENTRYPOINT  ["/upload.sh"]
