Coffee
"""""""""""""""""""""""""""""

Formula
+++++++++++++++++++++++

define as FORMULA in common/define.py

::

    FORMULA = {
        "hot water": {
            "drinkType": 3, "volume": 0, "coffeeTemperature": 0, "concentration": 0, "hotWater": 1.00,
            "waterTemperature": 2, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
            "coffeeMilkTogether": 0, "adjustOrder": 0},
        "espresso": {
            "drinkType": 1, "volume": 0.1956, "coffeeTemperature": 2, "concentration": 0, "hotWater": 0,
            "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 1, "moreEspresso": 0,
            "coffeeMilkTogether": 0, "adjustOrder": 0},
        "americano": {
            "drinkType": 2, "volume": 0.3478, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0.6522,
            "waterTemperature": 2, "hotMilk": 0, "foamTime": 0, "precook": 1, "moreEspresso": 0,
            "coffeeMilkTogether": 0, "adjustOrder": 0},
        "cappuccino": {
            "drinkType": 4, "volume": 0.1739, "coffeeTemperature": 2, "concentration": 0, "hotWater": 0,
            "waterTemperature": 0, "hotMilk": 0.0304, "foamTime": 0.1087, "precook": 1, "moreEspresso": 0,
            "coffeeMilkTogether": 1, "adjustOrder": 0},
        "latte": {
            "drinkType": 6, "volume": 0.1304, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0,
            "waterTemperature": 0, "hotMilk": 0.034, "foamTime": 0.0870, "precook": 1, "moreEspresso": 0,
            "coffeeMilkTogether": 1, "adjustOrder": 0},
        "flat white": {
            "drinkType": 5, "volume": 0.3043, "coffeeTemperature": 2, "concentration": 0, "hotWater": 0,
            "waterTemperature": 0, "hotMilk": 0.0652, "foamTime": 0.0435, "precook": 1, "moreEspresso": 0,
            "coffeeMilkTogether": 1, "adjustOrder": 0},
        "hot milk": {
            "drinkType": 7, "volume": 0, "coffeeTemperature": 0, "concentration": 0, "hotWater": 0,
            "waterTemperature": 0, "hotMilk": 0.1740, "foamTime": 0, "precook": 0, "moreEspresso": 0,
            "coffeeMilkTogether": 0, "adjustOrder": 0},
        "italian espresso": {
            "drinkType": 1, "volume": 0.5217, "coffeeTemperature": 2, "concentration": 2, "hotWater": 0,
            "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
            "coffeeMilkTogether": 0, "adjustOrder": 0},
        "italian-style macchiato": {
            "drinkType": 1, "volume": 0.1957, "coffeeTemperature": 2, "concentration": 0, "hotWater": 0,
            "waterTemperature": 0, "hotMilk": 0.2173, "foamTime": 0.0435, "precook": 0, "moreEspresso": 0,
            "coffeeMilkTogether": 0, "adjustOrder": 0},
    }


::

    drinkType: do not change
    volume: Coffee as a percentage of total capacity
    coffeeTemperature: 0/1/2 => Low Medium High
    concentration: 0/1/2 => light moderate full-bodied
    hotWater: hot water as a percentage of total capacity
    waterTemperature: 0/1/2 => Low Medium High
    hotMilk: hot milk as a percentage of total capacity
    foamTime: milk froth as a percentage of total capacity
    precook: 0/1 => false/true
    moreEspresso: 0/1 => false/true
    coffeeMilkTogether: 0/1 => false/true
    adjustOrder: 0: Milk before coffee  1: Coffee first and milk later


example
---------

    Make a medium cup of espresso, and the amount of water in a medium cup of coffee is 230 ml,
    because the volume is 0.1956, so the amount of coffee is 230*0.1956=44.988=50 ml.


hot coffee
----------------

.. uml::

    @startuml
    actor       User
    participant "coffee\napi" as coffee
    participant "adam\napi" as adam
    participant "audio\napi" as audio
    database    db
    participant "Adam\nRobot" as robot #99FF99
    participant "Coffee\nMachine" as cof #99FF99
    User -> coffee : /make

    coffee -> db : create new record to drink table
    User <-- coffee : create task success
    coffee -> adam : /adam/take_cup
    adam -> robot: goto hot cup position and take it
    coffee -> adam : /adam/take_ingredients
    adam -> robot: goto hot ingredients position
    adam -> robot: control adam gpio and wait sometime
    coffee -> adam : /adam/take_hot_coffee
    adam -> robot: goto hot coffee position
    coffee -> cof: make hot coffee
    coffee -> db: change task status is starting
    coffee <- cof: check coffee status == processing
    coffee -> db: change task status is processing
    coffee <- cof: check coffee status == idle
    coffee -> db: change task status is completed

    coffee -> adam: /adam/put_cup
    adam -> robot: left arm goto middle position put cup
    adam -> robot: right arm goto middle position take cup
    adam -> robot: right arm put cup
    coffee -> audio: tts: hot coffee is completed
    @enduml

