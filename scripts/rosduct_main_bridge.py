#!/usr/bin/env python3

import rospy
from rosduct.rosduct_bridge import ROSductBridge

if __name__ == '__main__':
    node_handle = rospy.init_node('rosduct')
    r = ROSductBridge(node_handle)
    r.spin()
