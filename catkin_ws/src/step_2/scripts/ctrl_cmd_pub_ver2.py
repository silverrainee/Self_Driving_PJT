#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 라이브러리 임포트
import rospy
import numpy as np
from math import cos, sin, atan2, sqrt, pow
from tf.transformations import euler_from_quaternion
from std_msgs.msg import Float32
from geometry_msgs.msg import Point, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry, Path
from morai_msgs.msg import CtrlCmd, EgoVehicleStatus

# Ctrl Cmd Publish class
class ctrl_cmd_pub:
    # 초기화 함수
    def __init__(self):
        # ROS 노드 초기화
        rospy.init_node('ctrl_cmd', anonymous=True)

        # Subscriber 설정
        rospy.Subscriber("/local_path", Path, self.path_callback)
        rospy.Subscriber('/velocity1', Float32, self.velocity1_callback)
        rospy.Subscriber('/velocity2', Float32, self.velocity2_callback)
        rospy.Subscriber("/odom", Odometry, self.odom_callback)
        rospy.Subscriber("/Ego_topic", EgoVehicleStatus, self.status_callback)

        # Publisher 설정
        self.ctrl_cmd_pub = rospy.Publisher('/ctrl_cmd', CtrlCmd, queue_size=1)

        # 초기화
        self.is_path = False
        self.is_velocity = False
        self.is_odom = False
        self.is_status = False
        self.is_target_point = False

        self.ctrl_cmd_msg = CtrlCmd()
        self.ctrl_cmd_msg.longlCmdType = 1

        self.vehicle_length = 2.984
        self.lad = 15.0
        self.lad_min = 3
        self.lad_max = 20
        self.lad_gain = 0.6

        self.velocity_pid = pidControl(0.30, 0.00, 0.03)
        self.steering_pid = pidControl(1.30, 0.00, 0.00)

        self.target_steering = 0.0
        self.target_velocity = 100 / 3.6
        self.velocity1 = 100 / 3.6
        self.velocity2 = 100 / 3.6
        self.velocity3 = 100 / 3.6

        # 주기 설정
        rate = rospy.Rate(30)
        while not rospy.is_shutdown():
            if self.is_path and self.is_odom and self.is_status and self.is_velocity:
                self.target_velocity = min(self.velocity1, min(self.velocity2, self.velocity3))
                self.target_steering = self.find_target_steering()

                velocity_output = self.velocity_pid.output(self.target_velocity, self.status_msg.velocity.x)
                steering_output = self.steering_pid.output(self.target_steering, 0.0)

                if velocity_output > 0.0:
                    self.ctrl_cmd_msg.accel = velocity_output
                    self.ctrl_cmd_msg.brake = 0.0
                else:
                    self.ctrl_cmd_msg.accel = 0.0
                    self.ctrl_cmd_msg.brake = -velocity_output

                self.ctrl_cmd_msg.steering = steering_output

                self.ctrl_cmd_pub.publish(self.ctrl_cmd_msg)

            rate.sleep()

    # Path Callback 함수
    def path_callback(self, msg):
        self.path = msg
        self.is_path = True

    # Velocity Callback 함수
    def velocity1_callback(self, msg):
        self.velocity1 = msg.data
        self.is_velocity = True
    
    def velocity2_callback(self, msg):
        self.velocity2 = msg.data
    
    def velocity3_callback(self, msg):
        self.velocity3 = msg.data

    # Odometry Callback 함수
    def odom_callback(self, msg):
        self.current_position = msg.pose.pose.position
        odom_quaternion=(msg.pose.pose.orientation.x,msg.pose.pose.orientation.y,msg.pose.pose.orientation.z,msg.pose.pose.orientation.w)
        _,_,self.vehicle_yaw=euler_from_quaternion(odom_quaternion)
        self.is_odom = True

    # Egovehicle Status Callback 함수
    def status_callback(self, msg):
        self.status_msg = msg
        self.is_status = True

    # Target Steering 찾기
    def find_target_steering(self):
        self.lad = (self.status_msg.velocity.x)*self.lad_gain
        self.lad = max(self.lad, self.lad_min)
        self.lad = min(self.lad, self.lad_max)
        translation = [self.current_position.x, self.current_position.y]
        trans_matrix = np.array([
            [cos(self.vehicle_yaw), -sin(self.vehicle_yaw), translation[0]],
            [sin(self.vehicle_yaw), cos(self.vehicle_yaw), translation[1]],
            [0, 0, 1]])
        det_trans_matrix = np.linalg.inv(trans_matrix)
        dis = 0

        for i, pose in enumerate(self.path.poses):
            path_point = pose.pose.position
            global_path_point = [path_point.x, path_point.y, 1]
            local_path_point = det_trans_matrix.dot(global_path_point)

            if local_path_point[0] > 0:
                dis = sqrt(pow(local_path_point[0], 2) + pow(local_path_point[1], 2))
                if dis >= self.lad:
                    break

        theta = atan2(local_path_point[1] + 0.024*dis,local_path_point[0])
        steering = atan2(2*self.vehicle_length*sin(theta), dis)

        return steering

# pidControl class
class pidControl:
    # 초기화 함수
    def __init__(self, p_gain, i_gain, d_gain):
        self.p_gain = p_gain
        self.i_gain = i_gain
        self.d_gain = d_gain
        self.prev_error = 0
        self.i_control = 0
        self.controlTime = 0.02

    # output 계산 함수
    def output(self, target_value, current_value):
        error = target_value - current_value

        p_control = self.p_gain * error
        self.i_control += self.i_gain * error * self.controlTime
        d_control = self.d_gain * (error - self.prev_error) / self.controlTime

        output = p_control + self.i_control + d_control
        self.prev_error = error

        return output

if __name__ == '__main__':
    try:
        ctrl_cmd = ctrl_cmd_pub()
    except rospy.ROSInterruptException:
        pass