#!/usr/bin/env python3

import rospy
import signal
import sys
from rosduct.rosduct_bridge_autobahn import ROSductBridge

bridge = None

def shutdown():
    global bridge
    bridge.client.stop()

def signal_handler(signal, frame):    
    print('Rosduct: You pressed Ctrl+C!')
    # shutdown()
    rospy.signal_shutdown("User terminated process")

if __name__ == '__main__':
    # signal.signal(signal.SIGINT, signal_handler)
    node_handle = rospy.init_node('rosduct')
    rospy.on_shutdown(shutdown)
    bridge = ROSductBridge(node_handle)
    bridge.spin()
