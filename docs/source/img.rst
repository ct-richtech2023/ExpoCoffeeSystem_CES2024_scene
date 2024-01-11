Software Architecture
"""""""""""""""""""""""""""


Soft
++++++++++++++++

.. uml::

    @startuml
    skinparam rectangle<<behavior>> {
        roundCorner 25
    }
    sprite $bProcess jar:archimate/business-process
    sprite $aService jar:archimate/application-service
    sprite $aComponent jar:archimate/application-component

    rectangle "/center /adam /audio /exception /coffee" as Router  #Business
    rectangle Postgres <<$aService>><<behavior>> #Application

    Router  <-down- Postgres

    rectangle "center"  as Center #Business
    rectangle "coffee" as Coffee  #Business
    rectangle "adam" as Adam  #Business
    rectangle "audio" as Audio  #Business
    rectangle "exception" as Exception #Business

    Center  <-up-> Postgres
    Exception  <-up-> Postgres
    Audio  <-up-> Postgres
    Adam  <-up-> Postgres
    Coffee  <-up-> Postgres

    Coffee -up-> Router
    Center -up-> Router
    Exception -up-> Router
    Audio -up-> Router
    Adam -up-> Router

    rectangle "Coffee Machine"  as coffee_machine #Application
    rectangle "Adam Robot" as adam_robot  #Application
    rectangle "Sound Device" as sound_device  #Application

    coffee_machine <-up-> Coffee
    adam_robot <-up-> Adam
    sound_device <-up- Audio
    @enduml


No.1 floor: expose web api, you can see it on http://{adam-pc-ip}:[9000-9005].

No.2 floor: web api implement floor.

No.3 floor: decoupling floor, web api only can query db and use redis publish msg to backend service.

No.4 floor: backend service floor, use supervisor to manage those.

No.5 floor: physical device floor.



Network
++++++++++++++++

.. uml::

    @startuml
    nwdiag {
      internet [ shape = cloud];
      internet -- frp;
      network dmz {
          address = "0.0.0.0/24"
          api [address = "host:9000",  description = "<&person*4.5>\n api"]
          adminer [address = "8080",  description = "<&cog*4>\n adminer"];
          frp;
      }
      network internal {
          address = "127.0.0.1";
          api [address = "host:9000"];
          adminer [address = "8080"];
          postgres [address = "5432",  description = "<&spreadsheet*4>\n postgres"];
          webdis [address = "6379,7379",  description = "<&spreadsheet*4>\n webdis"];
      }
    }
    @enduml

api: Adam business interface.

`frp <https://github.com/fatedier/frp/>`_ `docker <https://registry.hub.docker.com/r/snowdreamtech/frpc>`_:
A fast reverse proxy to help you expose a local server behind a NAT or firewall to the Internet.
As of now, it supports TCP and UDP, as well as HTTP and HTTPS protocols,
where requests can be forwarded to internal services by domain name.

postgres `docker <https://registry.hub.docker.com/_/postgres>`_:
An object-relational database management system (ORDBMS) with an emphasis on extensibility and standards-compliance.

`adminer <https://github.com/vrana/adminer>`_ `docker <https://registry.hub.docker.com/_/adminer>`_:
A full-featured database management tool written in PHP. Conversely to phpMyAdmin, it consist of a single file ready
to deploy to the target server. Adminer is available for MySQL, PostgreSQL,
SQLite, MS SQL, Oracle, Firebird, SimpleDB, Elasticsearch and MongoDB.

`webdis <https://github.com/nicolasff/webdis>`_ `docker <https://registry.hub.docker.com/r/nicolas/webdis>`_:
A very simple web server providing an HTTP interface to Redis. It uses hiredis, jansson, libevent, and http-parser.
