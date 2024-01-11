import json
import time
import requests
from fastapi import APIRouter, Depends
from loguru import logger

from common import conf
from common.schemas import center as center_schema


class MatradeeRobot:
    Instance = None

    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._base_url = "https://www.jqz.com/saas/wxos/matradeeRobot"
        self._sid = None
        self._robot_uuid_corp_map_dict = None
        self._sid_update_time = 0

    def login_in(self) -> dict:
        url = self._base_url + "/user/appLogin"
        logger.debug(url)
        res = requests.post(url=url, data=dict(username=self._username, password=self._password))
        assert res.status_code / 100 == 2, "login in failed, status_code={}".format(res.status_code)
        result = res.json()
        assert result.get('_sid'), 'login in failed, get sid={}'.format(result.get('_sid'))
        return result

    @property
    def sid(self):
        if not self._sid or time.perf_counter() - self._sid_update_time > 1000 * 60 * 60:
            self._sid = self.login_in()['_sid']
            self._sid_update_time = time.perf_counter()
            logger.info('sid={}'.format(self._sid))
        return self._sid

    @property
    def corp_list(self) -> dict:
        url = self._base_url + "/robotAccessToken/queryCorpList"
        logger.debug(url)
        res = requests.get(url=url, params=dict(sid=self.sid, pageNo=1, pageSize=99))
        assert res.status_code / 100 == 2, "get corp list failed, status_code={}".format(res.status_code)
        result = res.json()
        logger.info('corp_list={}'.format(json.dumps(result, indent=4)))
        return result

    @property
    def robot_list(self) -> dict:
        url = self._base_url + "/robotAccessToken/queryRobotList"
        logger.debug(url)
        res = requests.get(url=url, params=dict(sid=self.sid, pageNo=1, pageSize=99))
        assert res.status_code / 100 == 2, "get robot list failed, status_code={}".format(res.status_code)
        result = res.json()
        logger.info('robot_list={}'.format(json.dumps(result, indent=4)))
        return result

    @property
    def robot_uuid_corp_map_dict(self) -> dict:
        if not self._robot_uuid_corp_map_dict:
            self._robot_uuid_corp_map_dict = {value['robotUuid']: value['corpId'] for value in self.robot_list['data']}
            logger.info('robot_uuid_corp_map_dict={}'.format(self._robot_uuid_corp_map_dict))
        return self._robot_uuid_corp_map_dict

    def get_robot_position_list(self, robot_uuid) -> dict:
        url = self._base_url + "/robotAccessToken/queryPositionList"
        logger.debug(url)
        res = requests.get(url=url, params=dict(sid=self.sid, pageNo=1, pageSize=99, robotUuId=robot_uuid))
        assert res.status_code / 100 == 2, "get position list failed, status_code={}".format(res.status_code)
        result = res.json()
        logger.info('position_list={}'.format(json.dumps(result, indent=4)))
        return result

    def get_robot_info(self, robot_uuid):
        url = self._base_url + "/robotAccessToken/getRobotInfo"
        logger.debug(url)
        res = requests.get(url=url, params=dict(sid=self.sid, robotUuId=robot_uuid))
        assert res.status_code / 100 == 2, "get {} robot info failed, status_code={}".format(
            robot_uuid, res.status_code)
        result = res.json()
        logger.info('{} robot_info={}'.format(robot_uuid, json.dumps(result, indent=4)))
        return result

    @property
    def robot_uuid_list(self):
        result = self.robot_list
        uuid_list = [data['robotUuid'] for data in result['data']]
        logger.info('robot uuid_list={}'.format(uuid_list))
        return uuid_list

    def current_pos_name(self, robot_uuid):
        result = self.get_robot_info(robot_uuid)
        return result['data']['robot_report_status']['location']['pos_all_name']['en_US']

    def robot_task(self, robot_uuid, position_name):
        if robot_uuid not in self.robot_uuid_corp_map_dict:
            raise Exception('unknown robot_uuid={}'.format(robot_uuid))
        corp_id = self.robot_uuid_corp_map_dict[robot_uuid]
        url = self._base_url + "/robotAccessToken/handleMRobotTask"
        logger.debug(url)
        data = dict(corpId=corp_id, robotUuId=robot_uuid, posName=position_name)
        res = requests.post(url=url, params=dict(sid=self.sid), data=data)
        assert res.status_code / 100 == 2, "{} robot task failed, status_code={}".format(robot_uuid, res.status_code)
        result = res.json()
        logger.info('{} robot task result={}'.format(robot_uuid, json.dumps(result, indent=4)))
        return result


def get_obj():
    if not MatradeeRobot.Instance:
        account = center_schema.WakeDemoConfig(**conf.get_wake_demo_config()).robot.account
        MatradeeRobot.Instance = MatradeeRobot(account.username, account.password)
    return MatradeeRobot.Instance


matradee_router = APIRouter(
    prefix="/{}".format('matradee'),
    tags=['matradee'],
    # dependencies=[Depends(get_admin_token)],
    responses={404: {"description": "Not found"}},
)


@matradee_router.get("/robot/info")
def robot_info(uuid, robot: MatradeeRobot = Depends(get_obj)):
    return robot.get_robot_info(uuid)


@matradee_router.post("/robot/task")
def create_robot_task(uuid: str, position_name: str, robot: MatradeeRobot = Depends(get_obj)):
    return robot.robot_task(uuid, position_name)


@matradee_router.get("/robot/uuid")
def get_robot_uuids(robot: MatradeeRobot = Depends(get_obj)):
    uuids = [value['robotUuid'] for value in robot.robot_list.get('data', []) if "robotUuid" in value]
    logger.info('robot_uuids={}'.format(uuids))
    return uuids


@matradee_router.get("/robot/pos")
def get_current_robot_pos(uuid: str, robot: MatradeeRobot = Depends(get_obj)):
    return robot.current_pos_name(uuid)


if __name__ == '__main__':
    obj = MatradeeRobot("Wangc", "richtech321")
    # position obj.position_list,
    uuid_list = obj.robot_uuid_list
    # m = obj.robot_list, obj.corp_list, obj.position_list
    obj.get_robot_position_list(uuid_list[0])
    obj.get_robot_info(uuid_list[0])

    corpId = "L93Y9Lgux3F4XvefD-etgA"
    obj.robot_task(uuid_list[0], 'table2')
