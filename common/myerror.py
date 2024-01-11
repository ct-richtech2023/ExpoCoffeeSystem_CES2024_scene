class MoveError(Exception):
    pass


class StopError(Exception):
    pass


class AdamError(Exception):
    pass


class DBError(Exception):
    pass


class CoffeeError(AdamError):
    pass


class MilkTeaError(Exception):
    pass


class MaterialError(MilkTeaError):
    pass


class FormulaError(MilkTeaError):
    pass


class PrinterError(Exception):
    pass
