Service
""""""""""""""""

container
####################################

This command will show all containers that clouffee project have.

.. code-block:: shell

    cd /richtech/clouffee && docker-compose ps -a

    # if deploy success will show
    NAME        COMMAND                  SERVICE     STATUS     PORTS
    adam        "supervisord"            adam        running    0.0.0.0:9000-9004->9000-9004/tcp, :::9000-9004->9000-9004/tcp
    adminer     "entrypoint.sh docke…"   adminer     running    0.0.0.0:8080->8080/tcp, :::8080->8080/tcp
    db          "docker-entrypoint.s…"   db          running    0.0.0.0:5432->5432/tcp, :::5432->5432/tcp
    docs        "sphinx-autobuild /d…"   docs        running    0.0.0.0:9090->8000/tcp, :::9090->8000/tcp
    tts         "/bin/bash /run.sh"      tts         running    0.0.0.0:5002->5002/tcp, :::5002->5002/tcp

The meaning of all containers is:


..  csv-table::
    :header: "name", "description"
    :widths: 20, 80

    "adam", "core code, control adam, control coffee machine etc.."
    "tts", "text to speech service"
    "db", "postgres db, save clouffee data"
    "docs", "how to use clouffee docs"
    "adminer", "a web to access postgres db"



services
####################################

In adam container, we have 5 services.

.. code-block:: shell

    docker exec -it adam supervisorctl status

    # if no error will show
    adam          RUNNING   pid 9, uptime 0:28:49
    audio         RUNNING   pid 9, uptime 0:28:49
    center        RUNNING   pid 9, uptime 0:28:49
    coffee        RUNNING   pid 9, uptime 0:28:49
    exception     RUNNING   pid 9, uptime 0:28:49

Every service meaning is:

..  csv-table::
    :header: "name", "log path", "description"
    :widths: 20, 30, 80

    "adam", "/var/log/richtech/adam.log", "core code, control adam, control coffee machine etc.."
    "audio", "/var/log/richtech/audio.log", "play sound, music or tts"
    "center","/var/log/richtech/center.log", "new order, control process"
    "coffee","/var/log/richtech/coffee.log", "control coffee machine"
    "exception","/var/log/richtech/exception.log", "set or reset all critical errors"
    "wake","/var/log/richtech/wake.log", "use picovoice to wakeup and identify voice intent"

If service status is not RUNNING, just like following, adam, center, coffee and exception all exception! Please watch service path.

.. code-block:: shell

    adam          STARTING
    audio         RUNNING   pid 9, uptime 0:28:49
    center        FATAL     Exited too quickly (process log may have details)
    coffee        FATAL     Exited too quickly (process log may have details)
    exception     FATAL     Exited too quickly (process log may have details)





