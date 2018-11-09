import sys
import os
import logmsg
import json
import support
import time


fake_bridge = True

support.guess_platform()
if support.is_yun():
    sys.path.insert(0, "/usr/lib/python2.7/bridge/")
    try:
        from bridgeclient import BridgeClient
    except ImportError:
        raise ImportError("Error importing from BridgeClient library.")
    else:
        fake_bridge = False


if fake_bridge and not support.is_yun():
    # if exception = no yun, abstraction to bridge, simplified code inspired by arduino yun
    # abstract bridge client
    class BridgeClient:
        def __init__(self):
            self.bridge_var = {}
            self.fake = True

        def get(self, key):
            if key in self.bridge_var:
                r = self.bridge_var[key]
            else:
                r = None
            return r

        def getall(self):
            return self.bridge_var

        def put(self, key, value):
            self.bridge_var.update({key: value})

    # run httpd server here
    # end of abstraction

bridge_client = BridgeClient()


# required values, if any error in bridge then defaults is used [1]
# format codeword: ["codeword in bridge", default value, literal processing, variable]
cw = {
    "mode": ["mode", "auto", True, "var.mode"],
    # valve position in % to start heating
    "valve": ["valve_switch", 35, True, "setup.valve_switch"],
    # start heating if single valve position in %, no matter how many valves are needed to start to heating
    "svpnmw": ["svpnmw", 75, True, "setup.svpnmw"],
    # how many valves must be in position stated above
    "valves": ["valves", 2, True, "setup.valves"],
    # if in total mode, sum of valves position to start heating
    "total": ["total_switch", 150, True, "setup.total_switch"],
    # preference, "per" = per valve, "total" to total mode
    "pref": ["preference", "per", True, "setup.preference"],
    # interval, seconds to read MAX!Cube
    "int": ["interval", 90, True, "setup.intervals['max'][0]"],
    # ignore opened windows interval
    "ign_op": ["ignore_opened", 15, True, "eq3.ignore_time"],
    # use auto update function?
    "au": ["autoupdate", True, True, "setup.au"],
    # beta features on (yes) or off (no)
    "beta": ["beta", "no", True, "var.beta"],
    # profile type, time or temp, temp profile type means that external temperature (yahoo weather) is used
    "profile": ["profile", "normal", True, "setup.selected_mode"],
    # list of ignored devices
    "ign": ["ignored", {}, True, "eq3.ignored_valves"],
    # no open window warning, if True then no window warning via email
    "no_oww": ["no_oww", 0, True, "setup.no_oww"],
    # heat time dictionary
    "ht": ["heattime", {}, True, "var.ht"],
    "tht": ["total_heattime", float(0), True, "var.tht"],
    "wref": ["weather_reference", "yahoo", True, "setup.weather_reference"],
    # communication errors, how many times failed communication between thermeq3 and MAX!Cube, 0 after sending status
    "errs": ["error", 0, False, ""],
    # same as above, but cumulative number
    "terrs": ["totalerrors", 0, False, ""],
    "cmd": ["command", "", False, ""],
    "msg": ["msg", "", False, ""],
    "uptime": ["uptime", "", False, ""],
    "appuptime": ["app_uptime", 0, False, ""],
    "status": ["status", "defaults", False, ""],
    "status_key": ["status_key", "init", False, ""],
    "sys": ["system_status", {}, False, ""],
    "owl": ["open_window_list", {}, False, ""],
    # local temperature from sensor
    "lt": ["local_temp", 0.0, False, ""],
    # local humidity from sensor
    "lh": ["local_humidity", 0.0, False, ""],
    # devices dictionary dump
    "dump": ["dump", "", False, ""]
    }


def get_pcw():
    global cw
    lcw = {}
    for k, v in cw.iteritems():
        # key : [default, literal]
        lcw.update({v[0]: [v[1], v[2], v[3]]})
    return lcw


pcw = get_pcw()


def save(bridge_file):
    """
    Save bridge to bridge_file, if success return True, else False
    :param bridge_file: string
    :return: boolean
    """
    global bridge_client
    try:
        tmp = bridge_client.getall()
    except ValueError:
        logmsg.update("Value error during reading bridge!", 'E')
    except Exception:
        logmsg.update("Error reading bridge!", 'E')
    else:
        try:
            f = open(bridge_file, "w")
        except IOError:
            logmsg.update("Error writing to bridge file!", 'E')
        else:
            f.write(json.dumps(tmp, sort_keys=True))
            f.close()
            logmsg.update("Bridge file (" + str(bridge_file) + ") saved.", 'D')
            return True
    return False


def load(bridge_file):
    """
    Load data from bridge_file and return dictionary or None
    :param bridge_file: string
    :return: dictionary
    """
    data = {}
    if os.path.exists(bridge_file):
        with open(bridge_file, "r") as f:
            try:
                data = json.load(f)
            except ValueError:
                logmsg.update("Bridge value error during loading bridge!", 'E')
            finally:
                f.close()
        logmsg.update("Bridge file loaded.", 'D')
    else:
        logmsg.update("Error loading bridge file, file not exist!", 'E')
        # load empty dict, not None
        # data = None
        data = {}
    return data


def get_cw(lcw):
    """
    Return codeword from dictionary
    :param lcw: key
    :return: string
    """
    global cw
    if lcw in cw:
        return str(cw[lcw][0])
    else:
        return "wrong_key " + str(lcw)


def get_cw_default(lcw):
    """
    Return codeword and default value from dictionary
    :param lcw: key
    :return: string
    """
    global cw
    if lcw in cw:
        return str(cw[lcw][0]), cw[lcw][1]
    else:
        return "wrong_key " + str(lcw), 0


def try_read(lcw, _save=True):
    """
    try read from bridge, if key not there, save default value
    :param lcw: string, local codeword
    :param _save: boolean, if not in bridge then save
    :return: various
    """
    global bridge_client, cw

    temp_cw, default = get_cw_default(lcw)
    tmp_str = bridge_client.get(temp_cw)

    if support.is_empty(tmp_str):
        tmp = default
        if _save:
            bridge_client.put(temp_cw, str(tmp))
    else:
        if type(default) is int:
            try:
                tmp = int(tmp_str)
            except ValueError:
                tmp = default
        else:
            tmp = tmp_str
    return tmp


def put(key, value):
    """
    Put value to the key in bridge_client
    :param key: key
    :param value: string
    :return: nothing
    """
    global bridge_client
    # update touch
    bridge_client.put("touch", str(time.time()))
    bridge_client.put(get_cw(key), str(value))


def try_put(key, value):
    if not str(bridge_client.get(key)) == str(value):
        bridge_client.put(str(key), str(value))


def put_all(obj):
    """
    Put all bridge_data to bridge, e.g. fill bridge
    :param bridge_data:
    :return:
    """
    global cw
    for k, v in cw.iteritems():
        if v[2]:
            sv = v[3].split('.')
            obj_obj = eval("obj." + sv[0])
            if hasattr(obj_obj, sv[1]):
                a = getattr(obj_obj, sv[1])
                put(k, a)


def get(key):
    """
    Get from bridge_client by key, key is expanded through CW
    :param key: key
    :return:  string
    """
    global bridge_client
    return str(bridge_client.get(get_cw(key)))


def export():
    """
    Export bridge_client.json as JSON
    :return: JSON string
    """
    global bridge_client
    return json.dumps(bridge_client.getall())


def get_cmd():
    local_cmd = get("cmd")
    if local_cmd is None:
        return ""
    elif len(local_cmd) > 0:
        put("cmd", "")
    return local_cmd
