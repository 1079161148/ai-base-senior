FROM python:3.12-slim

LABEL maintainer="study"

ARG APP_VERSION=1.0
ENV APP_ENV=dev

WORKDIR /www

COPY index.html .
COPY app.py .

EXPOSE 8000

RUN useradd -m appuser
USER appuser

CMD ["python", "app.py"]
