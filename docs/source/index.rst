.. 双臂机器人SDK documentation master file, created by
   sphinx-quickstart on Thu Dec  2 11:44:55 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive. Richtech

Contents
=========================================

.. toctree::
   :maxdepth: 2

   get_start
   config
   service
   img
   gpio
   coffee


Interface Url
##############################

You can replace localhost to <adam pc device ip>, and open url in other device.

..  csv-table::
    :header: "name", "url", "description"
    :widths: 15, 30, 50

    "exception", "http://localhost:9002", "provides interface for collect exception"
    "adam", "http://localhost:9003", "provides interface for control adam"
    "center", "http://localhost:9000", "provides interface for create order"
    "audio", "http://localhost:9004", "provides interface for playing music and speaking"
    "coffee", "http://localhost:9001", "provides interface for make coffee formula"
