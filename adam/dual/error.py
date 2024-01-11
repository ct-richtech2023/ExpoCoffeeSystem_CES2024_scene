class RegisterException(Exception):
    pass


API_RETURN_CODE_DESC = """
- -12: run blockly app exception
- -11: convert blockly app to pythen exception
- -9: emergency stop
- -8: out of range
- -7: joint angle limit
- -6: cartesian pos limit
- -5: revesed, no use
- -4: command is not exist
- -3: revesed, no use
- -2: xArm is not ready, may be the motion is not enable or not set state
- -1: xArm is disconnect or not connect
- 0: success
- 1: there are errors that have not been cleared
- 2: there are warnings that have not been cleared
- 3: get response timeout
- 4: tcp reply length error
- 5: tcp reply number error
- 6: tcp protocol flag error
- 7: tcp reply command and send command do not match
- 8: send command error, may be network exception
- 9: state is not ready to move
- 10: the result is invalid
- 11: other error
- 12: parameter error
- 20: host id error
- 21: modbus baudrate not supported
- 22: modbus baudrate not correct
- 23: modbus reply length error
- 31: trajectory read/write failed
- 32: trajectory read/write timeout
- 33: playback trajectory timeout
- 41: wait to set suction cup timeout
- 80: linear track has error
- 81: linear track sci is low
- 82: linear track is not init
- 100: wait finish timeout
- 101: too many consecutive failed tests
- 102: end effector has error
- 103: end effector is not enabled
"""


def get_return_code_dict():
    err_code_list = API_RETURN_CODE_DESC.split('\n')
    err_code_list = [i[1:].strip() for i in err_code_list if i]
    # print(err_code_list)
    return {
        int(i.split(':')[0]): 'return_code={}'.format(i).strip()
        for i in err_code_list
    }


API_RETURN_CODE_DICT = get_return_code_dict()


def get_return_code_desc(number):
    return API_RETURN_CODE_DICT.get(number, 'return_code={}: unknown error code'.format(number))


if __name__ == '__main__':
    err = get_return_code_desc(9)
    print(err)
