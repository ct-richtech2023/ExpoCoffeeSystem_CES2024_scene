import traceback
from typing import Literal

from loguru import logger
from fastapi import APIRouter
from starlette.responses import JSONResponse

from common.define import Channel
from common import utils
from common.schemas import adam as adam_schema
from common import conf, define

kinematics_router = APIRouter(
    prefix="/{}".format(Channel.kinematics),
    tags=[Channel.kinematics],
    # dependencies=[Depends(get_admin_token)],
    responses={404: {"description": "Not found"}},
)
# settings/adam.yml中的配置
ADAM_CONFIG = adam_schema.AdamConfig(**conf.get_adam_config())
# 默认预制解为众为的零点，因为从众为的零点去目标点可能会选择错误的路径，导致扭转，所以才需要自己提供预制解
DEFAULT_Q_PRE = dict(zip(define.ANGLE_PARAM, [0] * 6))


def get_tcp_offset(which) -> adam_schema.Pose:
    return ADAM_CONFIG.gripper_config[getattr(ADAM_CONFIG.different_config, which).gripper].tcp_offset


def get_world_offset(which) -> adam_schema.Pose:
    return getattr(ADAM_CONFIG.different_config, which).world_offset


def list_to_pose_dict(input_list) -> dict:
    return dict(zip(['x', 'y', 'z', 'roll', 'pitch', 'yaw'], [float(i) for i in input_list]))


def list_to_angle_dict(input_list) -> dict:
    return dict(zip(['j1', 'j2', 'j3', 'j4', 'j5', 'j6'], [float(i) for i in input_list]))


@kinematics_router.post("/forward", summary='forward')
def forward_kinematics(which: define.SUPPORT_ARM_TYPE, angles: adam_schema.Angles):
    """
    运动学正解：
    cmd：fk 关节角度值 夹爪工具坐标系偏移 世界坐标系偏移
    输出：位姿（位置和姿态）
    """
    try:
        angle_list = [str(i) for i in angles.dict().values()]
        tcp_list = [str(i) for i in get_tcp_offset(which).dict().values()]
        world_list = [str(i) for i in get_world_offset(which).dict().values()]
        param_str = "{} {} {}".format(' '.join(angle_list), ' '.join(tcp_list), ' '.join(world_list))
        cmd = '{}/fk {}'.format(define.BIN_PATH, param_str)
        ret = utils.get_execute_cmd_result(cmd)
        logger.debug('forward {} input: angles={}, result: {}'.format(which, angle_list, ret))
        pose_list = ret.strip().split(' ')
        logger.info('cmd={}, ret={}'.format(cmd, pose_list))
        return {'angles': angles, 'forward': list_to_pose_dict(pose_list)}
    except Exception as e:
        return JSONResponse(status_code=400, content={'err_msg': str(e)})


@logger.exception
@kinematics_router.post("/inverse", summary='inverse')
def inverse_kinematics(which: define.SUPPORT_ARM_TYPE,
                       pose: adam_schema.Pose,
                       q_pre: adam_schema.Angles = DEFAULT_Q_PRE):  # noqa
    """
    运动学逆解：
    cmd：ik 需要到达的迪卡尔位置 夹爪工具坐标系偏移 世界坐标系偏移 预制解
    输出：逆解的关节角度值
    （运动学逆解有8个，预制解用来告诉ik到底哪个一个解是最合适的，这里的预制解是真实解附近的一个位姿）
    """
    try:
        pose_list = [str(i) for i in pose.dict().values()]
        tcp_list = [str(i) for i in get_tcp_offset(which).dict().values()]
        world_list = [str(i) for i in get_world_offset(which).dict().values()]
        q_pre_list = [str(i) for i in q_pre.dict().values()]
        param_str = "{} {} {} {}".format(
            ' '.join(pose_list), ' '.join(tcp_list), ' '.join(world_list), ' '.join(q_pre_list))
        cmd = '{}/ik {} '.format(define.BIN_PATH, param_str)
        ret = utils.get_execute_cmd_result(cmd)
        logger.debug('inverse {} input: pose={}, q_pre={}, result: {}'.format(which, pose_list, q_pre_list, ret))
        angle_list = ret.strip().split(' ')
        logger.info('cmd={}, ret={}'.format(cmd, angle_list))
        return {'pose': pose, 'q_pre': q_pre, 'inverse': list_to_angle_dict(angle_list)}
    except Exception as e:
        logger.error('err={}, traceback={}'.format(str(e), traceback.format_exc()))
        return JSONResponse(status_code=400, content={'err_msg': str(e)})
