# ExpoCoffeeSystem_CES2024

This Project aim to use Adam robot control coffee machine to make coffee automatically.

## How to Deploy

### Prepare Environment

1. ubuntu x86_64 (16.04/18.04/20.04 all ok)
2. Connect Internet (may download 5G in first time)


### Install Deploy Tools

You need to install the following three tools, please google hwo to install it.

1. git
2. docker
3. docker-compose

#### install docker-compose

    sudo wget -O /usr/bin/docker-compose https://github.com/docker/compose/releases/download/v2.2.3/docker-compose-linux-x86_64
    sudo chmod +x /usr/bin/docker-compose
    sudo chmod 777 /usr/bin/docker-compose

You can use following command to check if install success.

    git --version
    docker --version
    docker-compose --version

### download code

    cd ~ && git clone -b wine https://github.com/richtechsystem/clouffee.git

### download container
    
    cd ~/clouffee && docker-compose pull

After execute above command, you will see the following response, please wait until it pull completed.

    [+] Running 5/5
     ⠿ adam Pulling                                            3.6s
     ⠿ adminer Pulling                                         3.5s
     ⠿ tts Pulling                                             3.5s
     ⠿ db Pulling                                              3.5s
     ⠿ docs Pulling                                            3.5s

### start container

Now let's start container in background.

    cd ~/clouffee && docker-compose up -d

After execute above command, you will see the following response.

    [+] Running 5/5
     ⠿ Container adminer  Started                              1.0s
     ⠿ Container db       Started                              1.0s
     ⠿ Container docs     Started                              0.9s
     ⠿ Container tts      Started                              1.0s
     ⠿ Container adam     Started                              1.8s

If all containers start success, congratulations, you deploy success!

### check container status is Running

Sometimes, undocumented exception will cause the container to exit. We should check container status is really running.
    
    cd ~/clouffee && docker-compose ps -a

After execute above command, you will see the following response.

    NAME                COMMAND                  SERVICE             STATUS              PORTS
    adam                "supervisord"            adam                running             0.0.0.0:9000-9004->9000-9004/tcp, :::9000-9004->9000-9004/tcp
    adminer             "entrypoint.sh docke…"   adminer             running             0.0.0.0:8080->8080/tcp, :::8080->8080/tcp
    db                  "docker-entrypoint.s…"   db                  running             0.0.0.0:5432->5432/tcp, :::5432->5432/tcp
    docs                "sphinx-autobuild /d…"   docs                running             0.0.0.0:9090->8000/tcp, :::9090->8000/tcp
    tts                 "/bin/bash /run.sh"      tts                 running             0.0.0.0:5002->5002/tcp, :::5002->5002/tcp

As you can see, there are 5 containers, they are adam, adminer, db, docs and tts. If all container's status is running, that really deploy success.


### If start container failed

If there is start failed container, please execute following command, then send the newest /tmp/startContainerFailed-*.tar.gz to us.

    cd ~/clouffee
    docker-compose logs [failed_container_name] >> ./share/log/startContainerFailed.log  && echo "---" >> /var/log/richtech/startContainerFailed.log
    tar -zcvf /tmp/startContainerFailed-$(date +%Y%m%d-%H%M).tar.gz ./share/log    

## Goto Docs

For details on using the software, please visit http://localhost:9090 with a browser.
    #cloutea
# cloutea
