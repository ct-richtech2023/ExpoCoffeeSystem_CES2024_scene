FROM nicolas/webdis:0.1.19
MAINTAINER author "https://www.richtechrobotics.com"
WORKDIR /richtech
USER root

EXPOSE 6379
EXPOSE 7379

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories
RUN sed -i '2i"websockets":   true,' /etc/webdis.prod.json
# RUN sed -i "s/127.0.0.1/0.0.0.0/g" /etc/webdis.prod.json
RUN sed -i "s/127.0.0.1/0.0.0.0/g" /etc/redis.conf