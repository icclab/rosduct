#!/usr/bin/env python3
import rospy
import signal
import sys
from rosapi.srv import GetParam
from ast import literal_eval


class RosDuctParamSync:

    def __init__(self, node_handle):
        # Parameters
        self.rate_hz = rospy.get_param('~parameter_polling_hz', 1)
        self.parameters = rospy.get_param('~parameters', [])
        rospy.loginfo("Parameters: " + str(self.parameters))
        self.last_params = {}

        # Get all params and store them for further updates
        for param in self.parameters:
            if type(param) == list:
                # remote param name is the first one
                param = param[0]                
            self.last_params[param] = self.get_param(param)
            rospy.set_param(param, self.last_params[param])

    def sync_params(self):
        """
        Sync parameter server in between
        external and local roscore (local changes
        are not forwarded).
        """
        for param in self.parameters:
            if type(param) == list:
                local_param = param[1]
                param = param[0]
            else:
                local_param = param
            # Get remote param
            remote_param = self.get_param(param)
            if remote_param != self.last_params[param]:
                rospy.set_param(local_param, remote_param)
                self.last_params[param] = remote_param

    def get_param(self, param_name, default_value=None):
        """Get the value of a parameter with the given name, like using `rosparam get`.

        Args:
            param_name (str): The name of the parameter.

        Returns:
            The value of the parameter if exist, None otherwise.
        """
        rospy.logdebug("Syncing Parameter: %s", param_name)
        # then we just invoke it
        rospy.wait_for_service('/rosapi/get_param')
        try:
            svc_proxy = rospy.ServiceProxy('/rosapi/get_param', GetParam)
            rospy.logdebug(
                "Performing service call for get_param %s ", param_name)
            resp = svc_proxy(param_name, default_value)
            # rospy.logdebug("Service call for get_param response %s ", resp)

            param_value = str(resp.value)
            if param_value == 'null':
                return default_value
            # JSON returns true and false in lower case starting letter...
            if param_value == 'false' or param_value == 'true':
                param_value = param_value[0].upper() + param_value[1:]
            return literal_eval(param_value)
            return 
        except rospy.ServiceException as e:
            rospy.logwarn(
                "Service call failed for get_param %s with error: %s", param_name, e)

    def spin(self):
        """
        Run the node, needed to update the parameter server.
        """
        r = rospy.Rate(self.rate_hz)
        rospy.logdebug("Param Sync Spinning")
        while not rospy.is_shutdown():
            self.sync_params()
            r.sleep()


def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    node_handle = rospy.init_node('rosduct_param_sync')

    r = RosDuctParamSync(node_handle)
    r.spin()
