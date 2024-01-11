FROM ubuntu:20.04
MAINTAINER author "https://www.richtechrobotics.com/"
WORKDIR /richtech
EXPOSE 9000
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update
RUN apt install wget file curl vim procps lsof inetutils-ping -y
RUN apt install python3 python3-pip -y
RUN apt install ffmpeg alsa-base alsa-utils libasound-dev libportaudio2 libportaudiocpp0 portaudio19-dev usbutils -y --fix-missing
# 安装众为的机械臂驱动
RUN wget -c -t 3 https://gitee.com/supernatural-fork/xArm-Python-SDK/attach_files/943902/download/xArm-Python-SDK-release-1.8.4.tar.gz && \
    tar -zxvf xArm-Python-SDK-release-1.8.4.tar.gz && \
    cd xArm-Python-SDK-release-1.8.4 && \
    python3 setup.py install

COPY requirements.txt .
RUN pip3 install -r requirements.txt --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/

RUN echo "tail -f /var/log/richtech/center.log" > /usr/bin/tail-center && chmod +x /usr/bin/tail-center && \
    echo "tail -f /var/log/richtech/adam.log" > /usr/bin/tail-adam && chmod +x /usr/bin/tail-adam && \
    echo "tail -f /var/log/richtech/coffee.log" > /usr/bin/tail-coffee && chmod +x /usr/bin/tail-coffee && \
    echo "tail -f /var/log/richtech/exception.log" > /usr/bin/tail-exception && chmod +x /usr/bin/tail-exception && \
    echo "tail -f /var/log/richtech/audio.log" > /usr/bin/tail-audio && chmod +x /usr/bin/tail-audio && \
    echo "tail -f /var/log/richtech/wake.log" > /usr/bin/tail-wake && chmod +x /usr/bin/tail-wake && \
    echo "tail -f /var/log/richtech/milktea.log" > /usr/bin/tail-milktea && chmod +x /usr/bin/tail-milktea

# 解决fastapi的docs访问swagger-ui需要联网下载js、css的问题
RUN sed -i 's/https:\/\/fastapi.tiangolo.com\/img/\/static/g' /usr/local/lib/python3.8/dist-packages/fastapi/openapi/docs.py && \
    sed -i 's/https:\/\/cdn.jsdelivr.net\/npm\/swagger-ui-dist@3/\/static/g' /usr/local/lib/python3.8/dist-packages/fastapi/openapi/docs.py