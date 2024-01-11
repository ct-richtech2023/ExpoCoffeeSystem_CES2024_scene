import copy
import json
import threading
import time
import traceback

from loguru import logger
from requests import ConnectionError

from common import conf
from common import define
from common.api import AdamInterface, AudioInterface, CenterInterface
from common.db.crud import coffee as coffee_crud
from common.db.database import MySuperContextManager
from common.db.tables import coffee as coffee_table
from common.myerror import AdamError, MaterialError, FormulaError, StopError
from common.schemas import coffee as coffee_schema
from common.schemas import total as total_schema

from report import ReportThread
from cleaning_history import CleaningHistoryThread

coffee_table_name = coffee_table.Coffee.__tablename__


def get_coffee_obj():
    # 确保coffee对象只创建一次
    if not Business.Instance:
        Business.Instance = Business()
    return Business.Instance

class MakeThread(threading.Thread):
    def __init__(self, desc):
        super().__init__()
        logger.info('start make coffee thread, desc={}'.format(desc))
        self._current_task_uuid = ''
        self._current_formula_lack = []
        self.last_completed = {'task_uuid': '', 'formula': ''}
        self.test_run_flag = True
        self._run_flag = True  # 运行标志，急停时设为False
        self._pause = False
        self.wait_adam_time = 0
        self.cold_drink = []
        self.hot_drink = []
        self.init_drink_type()

    def pause(self):
        self._pause = True
        return 'ok'

    def proceed(self):
        self._pause = False
        return 'ok'

    def stop(self):
        self._run_flag = False

    @property
    def current_task_status(self):
        return {
            'task_uuid': self._current_task_uuid,
            'all_lack': get_coffee_obj().get_material_conditions().get('display', []),
            'current_lack': self._current_formula_lack,
            'last_completed': self.last_completed
        }

    def init_drink_type(self):
        with MySuperContextManager() as db_session:
            formula_objs = coffee_crud.get_formula(db=db_session, cup='Medium Cup', in_use=1)
            cold_list = []
            hot_list = []
            for formula_obj in formula_objs:
                if formula_obj.type == 'cold':
                    cold_list.append(formula_obj.name)
                elif formula_obj.type == 'hot':
                    hot_list.append(formula_obj.name)
            self.cold_drink = cold_list
            self.hot_drink = hot_list

    def make_coffee_by_type(self, record: coffee_schema.CoffeeRecord):
        with MySuperContextManager() as db_session:
            CenterInterface.restart_service('audio')
            AudioInterface.gtts(coffee_crud.choose_one_speech_text(db_session, define.AudioConstant.TextCode.start_makine))
            # 1. set status is processing
            update_dict = dict(status=define.TaskStatus.processing)
            coffee_crud.update_coffee_by_task_uuid(db_session, record.task_uuid, update_dict)
            CenterInterface.update_task_status(record.task_uuid, define.TaskStatus.processing)
            self.init_drink_type()
            try:
                # 2. call adam to make coffee
                if record.formula in self.cold_drink:
                    logger.info('formula={}, make_cold_drink'.format(record.formula))
                    AdamInterface.make_cold_drink(record.formula, record.sweetness, record.ice, record.milk, record.beans, record.receipt_number, record.task_uuid)
                elif record.formula in self.hot_drink:
                    logger.info('formula={}, make_hot_drink'.format(record.formula))
                    AdamInterface.make_hot_drink(record.formula, record.sweetness, record.ice, record.milk, record.beans, record.receipt_number, record.task_uuid)
                else:
                    raise Exception('not support formula:{}'.format(record.formula))

                # 3. set status is complete
                update_dict = dict(status=define.TaskStatus.completed)
                coffee_crud.update_coffee_by_task_uuid(db_session, record.task_uuid, update_dict)
                CenterInterface.update_task_status(record.task_uuid, define.TaskStatus.completed)
                self.last_completed['task_uuid'] = str(record.task_uuid)
                self.last_completed['formula'] = record.formula
                record.status = define.TaskStatus.completed
            except (AdamError, StopError) as e:
                # 4. adam error, set status is failed
                update_dict = dict(status=define.TaskStatus.failed, failed_msg='AdamError {}'.format(e))
                coffee_crud.update_coffee_by_task_uuid(db_session, record.task_uuid, update_dict)
                CenterInterface.update_task_status(record.task_uuid, define.TaskStatus.failed)
                record.status = define.TaskStatus.failed
            finally:
                coffee_crud.add_report(db_session, record.task_uuid)
                # pass
                # CenterInterface.restart_service('audio')

    def run(self) -> None:
        # 2. while cycle
        new_flag = True
        random_dance_count = 0  # 随机跳舞次数
        release_ice_count = 0  # 释放冰块次数
        start_time = time.perf_counter()
        idle_time = 0
        while self._run_flag:
            if self._pause:
                time.sleep(1)
            else:
                with MySuperContextManager() as db_session:
                    coffee_record = coffee_crud.get_one_waiting_record()
                    if coffee_record :
                        if not self._run_flag:  # 急停时，run_flag为False，退出线程
                            break
                        if not new_flag:
                            new_flag = True
                            start_time = time.perf_counter()
                            logger.info('comes new task, not idle at {}'.format(start_time))
                        logger.info('{} exist not completed record={}'.format(coffee_table_name, coffee_record.dict()))
                        try:
                            self._current_task_uuid = coffee_record.task_uuid
                            formula_composition = list(get_coffee_obj().get_composition_by_name_and_cup(coffee_record.formula,
                                                                                                        coffee_record.cup,
                                                                                                        coffee_record.sweetness,
                                                                                                        coffee_record.milk).keys())

                            material_conditions = get_coffee_obj().get_material_conditions()
                            current_all_lack = material_conditions.get('replace', [])
                            current_all_lack_list = list(set(formula_composition) & set(current_all_lack))
                            self._current_formula_lack = [material_conditions.get('material_name_map', {})[lack_name] for lack_name in current_all_lack_list]
                            if self._current_formula_lack:
                                tts_words = material_conditions.get('speak')
                                logger.warning(tts_words)
                                AudioInterface.gtts(tts_words)
                                time.sleep(5)
                                self.wait_adam_time += 5
                            else:
                                if self.wait_adam_time >= 1800:
                                    # have waited adam for half hour all tasks set failed
                                    update_dict = dict(status=define.TaskStatus.failed,
                                                       failed_msg='wait adam for {} seconds'.format(self.wait_adam_time))
                                    coffee_crud.update_coffee_by_task_uuid(db_session, coffee_record.task_uuid,
                                                                           update_dict)
                                    CenterInterface.update_task_status(coffee_record.task_uuid, define.TaskStatus.failed)
                                    time.sleep(10)
                                    continue
                                # zero_dict = AdamInterface.zero()
                                AdamInterface.stop_followCountdownTimer()
                                zero_dict = AdamInterface.stop_CountdownTime()
                                if zero_dict.get('msg') == 'not ok':
                                    time.sleep(10)
                                    self.wait_adam_time += 10
                                else:
                                    self.wait_adam_time = 0
                                    self.make_coffee_by_type(coffee_record)
                                time.sleep(0.5)
                        except ConnectionError as e:
                            logger.warning('connect error, wait for 2 seconds : {}'.format(e))
                            time.sleep(2)
                            self.wait_adam_time += 2
                            if self.wait_adam_time >= 1800:
                                # have waited adam for half hour all tasks set failed
                                raise Exception('connect error, wait adam for {} seconds'.format(self.wait_adam_time))
                        except Exception as e:
                            # raise(e)
                            logger.error(traceback.format_exc())
                            update_dict = {'status': define.TaskStatus.failed, 'failed_msg': str(e)}
                            coffee_crud.update_coffee_by_task_uuid(db_session, coffee_record.task_uuid, update_dict)
                            CenterInterface.update_task_status(coffee_record.task_uuid, define.TaskStatus.failed)
                            logger.warning("task_uuid={} make {} failed, adam goto work zero".format(
                                coffee_record.task_uuid, coffee_record.formula))
                            AudioInterface.gtts("make {} failed, Botbar stopped.".format(coffee_record.formula))
                            time.sleep(10)
                            # AdamInterface.zero()
                    else:
                        if new_flag:
                            new_flag = False
                            self._current_task_uuid = ''
                            use_time = int(time.perf_counter() - start_time)
                            logger.info('normal exist! no record in table={}, use_time={}'.format(coffee_table_name, use_time))
                            try:
                                AdamInterface.standby_pose()
                            except Exception:
                                pass
                            idle_time = time.time()
                        if time.time() - idle_time > 30 * 60 * (release_ice_count + 1):
                            logger.info('idle more than 30 min, release ice')
                            #AdamInterface.release_ice()
                            release_ice_count += 1
                            random_dance_count += 1
                        elif time.time() - idle_time > 10 * 60 * (random_dance_count + 1):
                            logger.info('idle more than 10 min, call dance')
                            # AdamInterface.random_dance()
                            random_dance_count += 1
                    time.sleep(1)


class Business:
    Instance = None
    """
    第一次程序启动将会删除所有未完成的排序，所有任务需要重新扫描后发送
    """

    def __init__(self):
        self.init_db_from_sql()
        self.init_detect()

        self.make_coffee_thread: MakeThread = None  # noqa
        self.machine_config = total_schema.MachineConfig(**conf.get_machine_config())

        self.start_make_coffee_thread('start service')

        # self.report_thread = ReportThread()
        # self.report_thread.setDaemon(True)
        # self.report_thread.start()
        #
        # self.cleaning_history_thread = CleaningHistoryThread()
        # self.cleaning_history_thread.setDaemon(True)
        # self.cleaning_history_thread.start()


    def get_composition_by_name_and_cup(self, formula, cup, sweetness, milk):
        with MySuperContextManager() as db_session:
            compositions = db_session.query(coffee_table.Composition).filter_by(formula=formula, cup=cup).all()
            if not compositions:
                # 校验方案是否支持
                msg = 'there are no formula named {} with cup = {} in use, please check again'.format(formula, cup)
                AudioInterface.gtts(msg)
                logger.error(msg)
                raise FormulaError(msg)
            normal_composition = {}
            foam_composition = {}
            for composition in compositions:
                if composition.material == 'foam':
                    #  奶泡原料要详细分析奶泡组成
                    foam_composition = json.loads(composition.extra).get('foam_composition')
                materials = coffee_crud.get_material(db_session, composition.material, in_use=1)
                if materials:
                    material = materials[0]
                    normal_composition[material.name] = material.count
                else:
                    msg = 'material {} is not in use, please check again'.format(composition.material)
                    AudioInterface.gtts(msg)
                    logger.error(msg)

            result = copy.deepcopy(normal_composition)
            for name, quantity in foam_composition.items():
                result[name] = result.get(name, 0) + quantity
            logger.debug('composition is {}, foam_composition is {}, result is {}'.format(normal_composition, foam_composition, result))
            return result

    def start_make_coffee_thread(self, desc):
        def start_thread():
            self.make_coffee_thread = MakeThread(desc=desc)
            self.make_coffee_thread.setDaemon(True)
            self.make_coffee_thread.start()

        if self.make_coffee_thread is None:
            start_thread()
            logger.info('first start make coffee thread')
        elif self.make_coffee_thread and not self.make_coffee_thread.is_alive():
            start_thread()
            logger.info('restart start make coffee thread')

    def init_db_from_sql(self):
        with MySuperContextManager() as db_session:
            coffee_crud.init_data(db_session, '../common/db/init.sql')

    def init_detect(self):
        with MySuperContextManager() as db_session:
            coffee_crud.init_detect(db_session)

    def get_material_conditions(self):
        with MySuperContextManager() as db_session:
            materials = coffee_crud.get_material(db_session, in_use=define.Constant.InUse.in_use)
            material_name_map = {}
            data = []
            replace = []  # list of  material.name
            alarm = []
            display = []  # list of material.display
            speak = ''  # material.display
            for material in materials:
                material_name_map[material.name] = material.display
                data.append(material.to_dict())
                if material.left <= material.alarm:
                    alarm.append(material.to_dict())
                    speak += '{}, '.format(material.display)
                    replace.append(material.name)
                    display.append(material.display)
            if speak:
                speak = 'please replace ' + speak.strip()
                speak = speak[:-1] + '.'
            else:
                speak = ''
            return {'replace': replace, 'display': display, 'speak': speak,
                    'data': data, 'alarm': alarm, 'material_name_map': material_name_map}

    def set_task_uuid_failed(self, task_uuid):
        with MySuperContextManager() as db_session:
            update_dict = {'status': define.TaskStatus.failed, 'failed_msg': 'user set no material'}
            coffee_crud.update_coffee_by_task_uuid(db_session, task_uuid, update_dict)
            logger.warning('user set task_uuid={} failed, err=no material'.format(task_uuid))

    def stop(self):
        self.make_coffee_thread.stop()
        AdamInterface.stop()

    def resume(self):
        """恢复工作，重启一个MakeThread"""
        AdamInterface.resume()
        self.start_make_coffee_thread('resume thread')

