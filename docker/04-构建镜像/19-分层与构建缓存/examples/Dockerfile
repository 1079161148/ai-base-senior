FROM alpine:3.20

WORKDIR /app

COPY step1.txt .

RUN echo "layer-2 built" >> /app/build.log

COPY step2.txt .

RUN echo "layer-4 built" >> /app/build.log

CMD ["cat", "/app/build.log"]
