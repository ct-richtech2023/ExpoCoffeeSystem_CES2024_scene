from common.db.database import MySuperContextManager
from common.db.tables import coffee as coffee_table


class DB_Constant:
    @classmethod
    def support_material_name(cls, in_use=None):
        with MySuperContextManager() as db:
            return_data = []
            materials = db.query(coffee_table.MaterialCurrent).all()
            for material in materials:
                return_data.append(material.name)
            return return_data

    @classmethod
    def support_formula_name(cls, in_use=None):
        with MySuperContextManager() as db:
            return_data = []
            conditions = []
            if in_use:
                conditions.append(coffee_table.Formula.in_use == in_use)
            formulas = db.query(coffee_table.Formula).filter(*conditions).all()
            for formula in formulas:
                return_data.append(formula.name)
            return return_data

    @property
    def support_material_config_name(self):
        with MySuperContextManager() as db:
            return_data = []
            configs = db.query(coffee_table.MachineConfig).all()
            for config in configs:
                return_data.append(config.name)
            return Literal[tuple(return_data)]