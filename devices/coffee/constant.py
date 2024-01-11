SERIAL_CONFIG = {'baudrate': 38400, 'bytesize': 8, 'stopbits': 1, 'timeout': 1}


class MachineStatus:
    idle = "Idle state"
    off = "Off state"
    init = "Initialization state"
    making = "Making coffee"
    operating = "Operating status"


SPEAK_STATUS = {
    MachineStatus.init: 'The coffee machine is initializing',
    MachineStatus.idle: 'The coffee machine is currently in standby',
    MachineStatus.operating:'The coffee machine is currently running',
    MachineStatus.off: 'The coffee machine is currently off',
    MachineStatus.making: 'The coffee machine is making coffee',
    'Brewer cleaning and milk frother cleaning, currently indistinguishable':  'The coffee machine is cleaning the brewer or milk frother',
    'Infuser Cleaning with Tablet': 'The coffee machine is cleaning the brewer with cleaning solution',
    'Milk frother cleaning with tablet': 'The coffee machine is cleaning the milk frother with cleaning solution',
    'Descaling and cleaning': 'Coffee machine is conducting descaling cleaning',
    'Empty the line': 'The coffee machine is emptying the pipeline',
}



COFFEE_STATUS = {
    "system_status": {
        "0": MachineStatus.init,
        "1": MachineStatus.idle,
        "2": MachineStatus.operating,
        "3": MachineStatus.off,
        "8": MachineStatus.making,
        "9": "Brewer cleaning and milk frother cleaning, currently indistinguishable",
        "A": "Infuser Cleaning with Tablet",
        "B": "Milk frother cleaning with tablet",
        "C": "Descaling and cleaning",
        "D": "Empty the line"
    },
    "make_status": {
        "type": {
            "1": "Espresso", "2": "American Coffee", "3": "Warm water", "4": "Cappuccino",
            "5": "Macchiato", "6": "Latte", "7": "Warm milk", "8": "Milk foam"
        },
        "status": {"0": "Making", "1": "Pause", "2": "Cancel", "3": "Done"},
        "progress": {
            "0": "null",
            "1": "Coffee out",
            "2": "Warm water out",
            "3": "Milk out",
            "4": "Milk foam out",
            "5": "Simultaneous out, that is, more than two kinds of water, "
                 "milk, milk foam, and coffee light are out at the same time",
            "6": "Grinding"
        },
    },
    "error_msg": {
        "0": "Water storage tray is not installed",
        "1": "The water tank is short of water",
        "2": "The grinder is abnormal, and there are beans in tray. It may be that there are not enough beans to grind, and the grinder does not turn on",
        "3": "Reservoir full of waste water",
        "4": "Coffee machine full of grounds",
        "5": "System lack of water",
        "6": "Abnormal pressure position of brewer, Brewer failure",
        "7": "Abnormal reset position of brewing unit",
        "8": "The temperature of the electric heating plate of the coffee machine is too high, higher than the set upper limit temperature",
        "9": "The temperature of the coffee machine is is lower than 0 degrees Celsius. It can be used when the temperature rises above 1 degree Celsius",
        "10": "NTC broken, infinite resistance",
        "11": "There are no more beans in the bean storage tray",
        "12": "The fuse of the heating plate is blown, but the heating NTC resistance does not change",
        "13": "Line pressure is too high when making coffee",
        "14": "The system has replenished water three times, but still cannot replenish water",
        "15": "No milk in A&B"
    },
    "assure_msg": {
        "0": "The brewing device needs to be cleaned",
        "1": "The milk frother needs to be cleaned",
        "2": "The coffee machine needs to be descaled,",
        "3": "Needs to be replaced the filter"
    }
}
