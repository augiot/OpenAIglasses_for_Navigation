#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32模拟器 - 用于调试AI眼镜导航系统

此脚本模拟ESP32眼镜设备，提供以下功能：
1. 通过WebSocket发送相机帧（JPEG格式）到/ws/camera端点
2. 通过UDP发送IMU数据到端口12345
3. 支持从本地图片或视频文件读取数据
4. 可配置的发送频率和数据生成
"""

import os
import sys
import asyncio
import json
import time
import random
import cv2
import numpy as np
import websockets
import socket
import argparse
import pygame  # 用于音频播放
from typing import Optional, Union, Dict, Any

class ESP32Simulator:
    def __init__(self, 
                 server_ip: str = "localhost",
                 server_port: int = 8081,
                 udp_port: int = 12345,
                 camera_source: Optional[Union[str, int]] = None,
                 frame_rate: int = 15,
                 imu_rate: int = 50,
                 debug: bool = False):
        """
        初始化ESP32模拟器
        
        Args:
            server_ip: 服务器IP地址
            server_port: 服务器端口
            udp_port: UDP端口
            camera_source: 相机源，可以是图片/视频路径或摄像头索引
            frame_rate: 相机帧发送频率(Hz)
            imu_rate: IMU数据发送频率(Hz)
            debug: 是否启用调试日志
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.udp_port = udp_port
        self.camera_source = camera_source
        self.frame_rate = frame_rate
        self.imu_rate = imu_rate
        self.debug = debug
        
        # WebSocket和UDP连接
        self.camera_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.udp_socket: Optional[socket.socket] = None
        
        # 相机相关
        self.cap = None
        self.is_video = False
        self.last_frame_time = 0
        self.frame_interval = 1.0 / frame_rate
        
        # IMU相关
        self.last_imu_time = 0
        self.imu_interval = 1.0 / imu_rate
        self.imu_sequence = 0
        
        # 状态标志
        self.running = False
        self.camera_connected = False
        self.imu_started = False
        
        # 动态障碍物相关
        self.obstacles = []  # 存储障碍物状态的列表
        self.obstacle_types = [
            {"name": "行人", "color": (0, 0, 255), "min_size": 20, "max_size": 40, 
             "min_speed": 1, "max_speed": 3},
            {"name": "自行车", "color": (0, 165, 255), "min_size": 30, "max_size": 50,
             "min_speed": 3, "max_speed": 8},
            {"name": "汽车", "color": (255, 0, 0), "min_size": 40, "max_size": 80,
             "min_speed": 5, "max_speed": 15},
            {"name": "电动车", "color": (255, 165, 0), "min_size": 35, "max_size": 60,
             "min_speed": 4, "max_speed": 10},
            {"name": "障碍物", "color": (0, 255, 0), "min_size": 25, "max_size": 70,
             "min_speed": 0, "max_speed": 0}  # 静态障碍物
        ]
        
        # 画面区域定义
        self.regions = [
            {"name": "左侧", "x_min": 50, "x_max": 200},
            {"name": "中间", "x_min": 210, "x_max": 430},
            {"name": "右侧", "x_min": 440, "x_max": 590}
        ]
        
        # 音频相关初始化
        pygame.mixer.init()
        self.audio_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice")
        self.alert_cooldown = 2.0  # 同类型障碍物提示的冷却时间（秒）
        self.is_playing_audio = False
        
        # 障碍物类型与音频文件的映射
        self.obstacle_audio_map = {
            "行人": {
                "前方": ["前方有人，注意避让。.wav", "前方有人，停一下。.wav"],
                "左侧": ["左侧有人，停一下。.wav"],
                "右侧": ["右侧有人，停一下。.wav"]
            },
            "自行车": {
                "前方": ["前方有自行车，停一下。.wav"],
                "左侧": ["左侧有自行车，停一下。.wav"],
                "右侧": ["右侧有自行车，停一下。.wav"]
            },
            "汽车": {
                "前方": ["前方有车，停一下。.wav", "前方有车，注意避让。.wav"],
                "左侧": ["左侧有车，停一下。.wav"],
                "右侧": ["右侧有车，停一下。.wav"]
            },
            "电动车": {
                "前方": ["前方有电瓶车，停一下。.wav"],
                "左侧": ["左侧有电瓶车，停一下。.wav"],
                "右侧": ["右侧有电瓶车，停一下。.wav"]
            },
            "障碍物": {
                "前方": ["前方有障碍物，注意避让。.wav", "前方有障碍物，停一下。.wav"],
                "左侧": ["左侧有障碍物，停一下。.wav"],
                "右侧": ["右侧有障碍物，停一下。.wav"]
            }
        }
    
    def log(self, message: str):
        """打印日志消息"""
        if self.debug:
            print(f"[ESP32-SIM] {message}")
    
    def _init_camera(self) -> bool:
        """初始化相机源"""
        try:
            # 如果是整数，尝试作为摄像头索引
            if isinstance(self.camera_source, int):
                self.log(f"尝试打开摄像头 #{self.camera_source}")
                self.cap = cv2.VideoCapture(self.camera_source)
                self.is_video = True
            # 如果是字符串且文件存在，尝试作为图片或视频
            elif isinstance(self.camera_source, str) and os.path.exists(self.camera_source):
                if self.camera_source.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    self.log(f"加载静态图片: {self.camera_source}")
                    self.cap = cv2.imread(self.camera_source)
                    if self.cap is None:
                        self.log(f"无法加载图片: {self.camera_source}")
                        return False
                    self.is_video = False
                else:
                    self.log(f"打开视频文件: {self.camera_source}")
                    self.cap = cv2.VideoCapture(self.camera_source)
                    self.is_video = True
            else:
                self.log("未提供有效的相机源，将生成测试图像")
                return True
            
            return True
        except Exception as e:
            self.log(f"初始化相机失败: {e}")
            return False
    
    def _init_udp(self) -> bool:
        """初始化UDP套接字"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.log(f"UDP套接字已初始化，目标: {self.server_ip}:{self.udp_port}")
            return True
        except Exception as e:
            self.log(f"初始化UDP失败: {e}")
            return False
    
    def _generate_test_image(self) -> np.ndarray:
        """生成测试图像"""
        # 创建一个640x480的测试图像
        img = np.ones((480, 640, 3), dtype=np.uint8) * 240  # 浅灰色背景
        
        # 添加当前时间作为水印
        current_time = time.strftime("%H:%M:%S")
        cv2.putText(img, f"ESP32 SIM - {current_time}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # 模拟盲道线
        for i in range(0, 640, 60):
            cv2.rectangle(img, (i, 400), (i+30, 480), (128, 128, 128), -1)
        
        # 如果障碍物列表为空，初始化障碍物
        if len(self.obstacles) == 0:
            self._init_obstacles()
        
        # 更新障碍物位置
            self._update_obstacles()
            
            # 检测障碍物并播放声音提示
            self._check_obstacles_and_play_sound()
        
        # 绘制所有障碍物
        for obstacle in self.obstacles:
            self._draw_obstacle(img, obstacle["type"], obstacle["x"], obstacle["y"], obstacle["size"])
        
        return img
    
    def _init_obstacles(self):
        """初始化障碍物列表"""
        # 确保每个区域至少有一个障碍物
        for region in self.regions:
            self._create_obstacle_in_region(region, y_min=200, y_max=400)
        
        # 添加额外的障碍物增加场景复杂度
        for _ in range(3):
            region = random.choice(self.regions)
            self._create_obstacle_in_region(region, y_min=150, y_max=400)
    
    def _create_obstacle_in_region(self, region, y_min=200, y_max=400):
        """在指定区域内创建一个障碍物"""
        # 随机选择障碍物类型
        obstacle_type = random.choice(self.obstacle_types)
        
        # 随机生成大小
        size = random.randint(obstacle_type["min_size"], obstacle_type["max_size"])
        
        # 随机生成初始位置
        x = random.randint(region["x_min"], region["x_max"] - size)
        y = random.randint(y_min, y_max - size)
        
        # 随机生成移动方向（-1表示向左，1表示向右）
        direction = random.choice([-1, 1])
        
        # 随机生成速度（基于障碍物类型的速度范围）
        speed = random.uniform(obstacle_type["min_speed"], obstacle_type["max_speed"])
        
        # 添加到障碍物列表
        self.obstacles.append({
            "type": obstacle_type,
            "x": x,
            "y": y,
            "size": size,
            "direction": direction,
            "speed": speed,
            "last_alert_time": 0  # 上次发出警报的时间，用于避免频繁提示
        })
    
    def _update_obstacles(self):
        """
        更新所有障碍物的位置
        """
        for obstacle in self.obstacles:
            # 只有当速度大于0时才移动
            if obstacle["speed"] > 0:
                # 更新x坐标位置
                obstacle["x"] += obstacle["direction"] * obstacle["speed"]
                
                # 检查是否超出边界，如果超出则反向
                if obstacle["x"] < 50 or obstacle["x"] + obstacle["size"] > 590:
                    obstacle["direction"] *= -1
                    # 调整位置，防止卡在边界外
                    if obstacle["x"] < 50:
                        obstacle["x"] = 50
                    elif obstacle["x"] + obstacle["size"] > 590:
                        obstacle["x"] = 590 - obstacle["size"]
                
                # 小概率改变方向（模拟真实移动中的变向）
                if random.random() < 0.02:  # 2%的概率改变方向
                    obstacle["direction"] *= -1
                
                # 小概率改变速度（模拟加速或减速）
                if random.random() < 0.03:  # 3%的概率改变速度
                    speed_factor = random.uniform(0.8, 1.2)  # 速度变化因子
                    new_speed = obstacle["speed"] * speed_factor
                    # 确保速度在障碍物类型的速度范围内
                    new_speed = max(obstacle["type"]["min_speed"], 
                                   min(obstacle["type"]["max_speed"], new_speed))
                    obstacle["speed"] = new_speed
    
    def _check_obstacles_and_play_sound(self):
        """
        检测障碍物位置并播放相应的音频提示
        """
        current_time = time.time()
        danger_zone_y = 300  # 危险区域的Y坐标（越靠近底部越危险）
        center_x = 320  # 屏幕中心X坐标
        
        # 检查当前是否有音频在播放
        if pygame.mixer.music.get_busy():
            self.is_playing_audio = True
            return  # 如果有音频正在播放，则暂时不播放新的音频
        else:
            self.is_playing_audio = False
        
        # 对每个障碍物进行检查
        for obstacle in self.obstacles:
            # 检查障碍物是否在危险区域内
            if obstacle["y"] > danger_zone_y:
                # 计算障碍物中心
                obstacle_center_x = obstacle["x"] + obstacle["size"] // 2
                obstacle_center_y = obstacle["y"] + obstacle["size"] // 2
                
                # 计算距离危险程度（Y坐标越大越危险）
                danger_level = (obstacle_center_y - danger_zone_y) / (480 - danger_zone_y)
                
                # 确定障碍物位置相对于中心的方向
                if abs(obstacle_center_x - center_x) < 100:  # 中心区域
                    position = "前方"
                elif obstacle_center_x < center_x:  # 左侧
                    position = "左侧"
                else:  # 右侧
                    position = "右侧"
                
                # 检查是否需要发出警报（基于危险程度和冷却时间）
                if danger_level > 0.6:  # 足够接近时才发出警报
                    if current_time - obstacle["last_alert_time"] > self.alert_cooldown:
                        # 播放相应的音频
                        self._play_obstacle_sound(obstacle["type"]["name"], position)
                        obstacle["last_alert_time"] = current_time
                        break  # 一次只提示一个最紧急的障碍物
    
    def _play_obstacle_sound(self, obstacle_type: str, position: str):
        """
        根据障碍物类型和位置播放相应的音频
        
        Args:
            obstacle_type: 障碍物类型
            position: 障碍物位置（前方、左侧、右侧）
        """
        try:
            # 获取对应的音频文件列表
            if obstacle_type in self.obstacle_audio_map and position in self.obstacle_audio_map[obstacle_type]:
                audio_files = self.obstacle_audio_map[obstacle_type][position]
                if audio_files:
                    # 随机选择一个音频文件
                    audio_file = random.choice(audio_files)
                    audio_path = os.path.join(self.audio_folder, audio_file)
                    
                    # 检查文件是否存在
                    if os.path.exists(audio_path):
                        self.log(f"播放音频: {audio_file}")
                        pygame.mixer.music.load(audio_path)
                        pygame.mixer.music.play()
                    else:
                        self.log(f"音频文件不存在: {audio_path}")
        except Exception as e:
            self.log(f"播放音频失败: {e}")
    
    def __del__(self):
        """
        清理资源
        """
        self.stop()
        # 关闭pygame音频系统
        pygame.mixer.quit()
    
    def _draw_obstacle(self, img: np.ndarray, obstacle: dict, x: int, y: int, size: int):
        """根据障碍物类型绘制不同形状的障碍物，优化视觉辨识度"""
        # 边框颜色（比填充色深一些）
        border_color = tuple(max(0, int(c * 0.7)) for c in obstacle["color"])
        
        if obstacle["name"] == "行人":
            # 行人：圆形头部 + 矩形身体 + 细节
            head_radius = size // 4
            # 绘制头部（带边框）
            cv2.circle(img, (x + size//2, y + head_radius), head_radius, obstacle["color"], -1)
            cv2.circle(img, (x + size//2, y + head_radius), head_radius, border_color, 2)
            # 绘制眼睛
            eye_offset = head_radius // 3
            cv2.circle(img, (x + size//2 - eye_offset, y + head_radius - eye_offset//2), 2, (0, 0, 0), -1)
            cv2.circle(img, (x + size//2 + eye_offset, y + head_radius - eye_offset//2), 2, (0, 0, 0), -1)
            # 绘制身体（带边框）
            cv2.rectangle(img, (x + size//3, y + head_radius*2), 
                         (x + size*2//3, y + size), obstacle["color"], -1)
            cv2.rectangle(img, (x + size//3, y + head_radius*2), 
                         (x + size*2//3, y + size), border_color, 2)
            # 绘制手臂
            arm_y = y + head_radius*2 + size//4
            cv2.line(img, (x + size//3, arm_y), (x, arm_y - size//6), border_color, 2)
            cv2.line(img, (x + size*2//3, arm_y), (x + size, arm_y - size//6), border_color, 2)
            # 绘制腿部
            leg_y = y + size
            cv2.line(img, (x + size//3 + size//10, leg_y), (x + size//3 - size//8, leg_y + size//5), border_color, 2)
            cv2.line(img, (x + size*2//3 - size//10, leg_y), (x + size*2//3 + size//8, leg_y + size//5), border_color, 2)
            
        elif obstacle["name"] == "自行车":
            # 自行车：更详细的绘制
            # 绘制车身
            cv2.rectangle(img, (x, y + size//3), (x + size, y + size*2//3), obstacle["color"], -1)
            cv2.rectangle(img, (x, y + size//3), (x + size, y + size*2//3), border_color, 2)
            # 绘制车轮（带轮毂）
            wheel_radius = size//5
            # 左车轮
            cv2.circle(img, (x + size//4, y + size), wheel_radius, (0, 0, 0), -1)
            cv2.circle(img, (x + size//4, y + size), wheel_radius//3, (255, 255, 255), -1)
            # 右车轮
            cv2.circle(img, (x + size*3//4, y + size), wheel_radius, (0, 0, 0), -1)
            cv2.circle(img, (x + size*3//4, y + size), wheel_radius//3, (255, 255, 255), -1)
            # 绘制车把
            cv2.line(img, (x + size//2, y + size//3), (x + size//2, y), border_color, 2)
            cv2.line(img, (x + size//2 - size//4, y), (x + size//2 + size//4, y), border_color, 2)
            # 绘制座椅
            cv2.rectangle(img, (x + size*3//5, y + size//6), (x + size*4//5, y + size//3), (128, 64, 0), -1)
            
        elif obstacle["name"] == "汽车":
            # 汽车：更详细的绘制
            # 绘制车身（带边框）
            cv2.rectangle(img, (x, y + size//3), (x + size, y + size), obstacle["color"], -1)
            cv2.rectangle(img, (x, y + size//3), (x + size, y + size), border_color, 2)
            # 绘制车顶（带边框）
            cv2.rectangle(img, (x + size//4, y), (x + size*3//4, y + size//3), obstacle["color"], -1)
            cv2.rectangle(img, (x + size//4, y), (x + size*3//4, y + size//3), border_color, 2)
            # 绘制车窗
            cv2.rectangle(img, (x + size//3, y + size//12), (x + size*2//3, y + size//3), (200, 200, 255), -1)
            # 绘制车轮
            wheel_radius = size//6
            # 左前轮
            cv2.circle(img, (x + size//4, y + size), wheel_radius, (0, 0, 0), -1)
            cv2.circle(img, (x + size//4, y + size), wheel_radius//3, (255, 255, 255), -1)
            # 右后轮
            cv2.circle(img, (x + size*3//4, y + size), wheel_radius, (0, 0, 0), -1)
            cv2.circle(img, (x + size*3//4, y + size), wheel_radius//3, (255, 255, 255), -1)
            # 绘制车灯
            cv2.circle(img, (x + size, y + size*2//3), wheel_radius//2, (255, 255, 0), -1)
            cv2.circle(img, (x, y + size*2//3), wheel_radius//2, (255, 0, 0), -1)
            
        elif obstacle["name"] == "电动车":
            # 电动车：更详细的绘制
            # 绘制车身（带边框）
            cv2.rectangle(img, (x, y + size//4), (x + size, y + size), obstacle["color"], -1)
            cv2.rectangle(img, (x, y + size//4), (x + size, y + size), border_color, 2)
            # 绘制座位
            cv2.rectangle(img, (x + size//3, y), (x + size*2//3, y + size//4), (128, 64, 0), -1)
            # 绘制车把
            cv2.line(img, (x + size//4, y + size//4), (x + size//4, y - size//6), border_color, 2)
            cv2.line(img, (x + size//4 - size//6, y - size//6), (x + size//4 + size//6, y - size//6), border_color, 2)
            # 绘制车轮
            wheel_radius = size//6
            # 左车轮
            cv2.circle(img, (x + size//3, y + size), wheel_radius, (0, 0, 0), -1)
            cv2.circle(img, (x + size//3, y + size), wheel_radius//3, (255, 255, 255), -1)
            # 右车轮
            cv2.circle(img, (x + size*2//3, y + size), wheel_radius, (0, 0, 0), -1)
            cv2.circle(img, (x + size*2//3, y + size), wheel_radius//3, (255, 255, 255), -1)
            # 绘制后视镜
            cv2.circle(img, (x + size*3//4, y), 3, (128, 128, 128), -1)
            
        else:
            # 普通障碍物：矩形（带边框）
            cv2.rectangle(img, (x, y), (x + size, y + size), obstacle["color"], -1)
            cv2.rectangle(img, (x, y), (x + size, y + size), border_color, 2)
            # 添加对角线以提高辨识度
            cv2.line(img, (x, y), (x + size, y + size), border_color, 2)
            cv2.line(img, (x + size, y), (x, y + size), border_color, 2)
        
        # 为所有障碍物添加标签（类型名称）
        font_scale = max(0.3, size / 100)  # 根据障碍物大小调整字体
        text_thickness = 1 if size < 50 else 2
        text_color = (0, 0, 0)  # 黑色文字更易读
        text_size = cv2.getTextSize(obstacle["name"], cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_thickness)[0]
        text_x = x + (size - text_size[0]) // 2
        text_y = y - 5 if y > 10 else y + size + 15  # 确保文字不超出画面
        
        # 绘制文字背景，提高可读性
        cv2.rectangle(img, 
                     (text_x - 2, text_y - text_size[1] - 2), 
                     (text_x + text_size[0] + 2, text_y + 2), 
                     (255, 255, 255), -1)
        # 绘制文字
        cv2.putText(img, obstacle["name"], (text_x, text_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, text_thickness)
    
    def _generate_imu_data(self) -> Dict[str, Any]:
        """生成模拟的IMU数据"""
        # 生成时间戳
        current_time = time.time()
        ts_ms = int(current_time * 1000)
        
        # 生成带一些随机噪声的加速度数据
        # 主要是重力加速度，加上一些小的变化
        ax = random.uniform(-0.5, 0.5)  # x轴加速度
        ay = random.uniform(-0.5, 0.5)  # y轴加速度
        az = 9.8 + random.uniform(-0.3, 0.3)  # z轴加速度（主要是重力）
        
        # 生成陀螺仪数据（带有轻微的旋转）
        wx = random.uniform(-0.1, 0.1)  # x轴角速度
        wy = random.uniform(-0.1, 0.1)  # y轴角速度
        wz = random.uniform(-0.1, 0.1)  # z轴角速度
        
        # 构建IMU数据字典
        imu_data = {
            "ts": ts_ms,
            "accel": {
                "x": ax,
                "y": ay,
                "z": az
            },
            "gyro": {
                "x": wx,
                "y": wy,
                "z": wz
            },
            "seq": self.imu_sequence
        }
        
        # 递增序列
        self.imu_sequence += 1
        
        return imu_data
    
    async def _send_camera_frame(self):
        """发送相机帧到WebSocket服务器"""
        current_time = time.time()
        
        # 控制发送频率
        if current_time - self.last_frame_time < self.frame_interval:
            return
        
        self.last_frame_time = current_time
        
        try:
            # 获取图像数据
            if self.cap is None:
                # 生成测试图像
                frame = self._generate_test_image()
            elif not self.is_video and isinstance(self.cap, np.ndarray):
                # 使用加载的静态图像
                frame = self.cap.copy()
                # 添加时间戳
                current_time_str = time.strftime("%H:%M:%S")
                cv2.putText(frame, current_time_str, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                # 从视频或摄像头读取
                ret, frame = self.cap.read()
                if not ret:
                    # 视频播放完毕，重新开始
                    if self.is_video:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.cap.read()
                    if not ret:
                        self.log("无法获取视频帧，使用测试图像")
                        frame = self._generate_test_image()
            
            # 压缩为JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ret:
                self.log("无法编码JPEG")
                return
            
            # 转换为字节
            jpeg_bytes = buffer.tobytes()
            
            # 通过WebSocket发送
            if self.camera_ws and self.camera_ws.open:
                await self.camera_ws.send_bytes(jpeg_bytes)
                self.log(f"发送相机帧，大小: {len(jpeg_bytes)} 字节")
        except Exception as e:
            self.log(f"发送相机帧失败: {e}")
    
    def _send_imu_data(self):
        """发送IMU数据到UDP服务器"""
        current_time = time.time()
        
        # 控制发送频率
        if current_time - self.last_imu_time < self.imu_interval:
            return
        
        self.last_imu_time = current_time
        
        try:
            # 生成IMU数据
            imu_data = self._generate_imu_data()
            
            # 转换为JSON字符串
            json_data = json.dumps(imu_data)
            
            # 通过UDP发送
            if self.udp_socket:
                self.udp_socket.sendto(json_data.encode('utf-8'), (self.server_ip, self.udp_port))
                if self.debug and self.imu_sequence % 100 == 0:  # 每100帧打印一次以避免日志过多
                    self.log(f"发送IMU数据: {json_data[:50]}...")
        except Exception as e:
            self.log(f"发送IMU数据失败: {e}")
    
    async def connect_camera_websocket(self):
        """连接到相机WebSocket服务器"""
        ws_url = f"ws://{self.server_ip}:{self.server_port}/ws/camera"
        self.log(f"尝试连接到相机WebSocket: {ws_url}")
        
        try:
            self.camera_ws = await websockets.connect(ws_url)
            self.camera_connected = True
            self.log("相机WebSocket连接成功")
        except Exception as e:
            self.log(f"相机WebSocket连接失败: {e}")
            self.camera_connected = False
    
    async def disconnect_camera_websocket(self):
        """断开相机WebSocket连接"""
        if self.camera_ws:
            try:
                await self.camera_ws.close()
                self.log("相机WebSocket已断开")
            except Exception as e:
                self.log(f"断开相机WebSocket时出错: {e}")
            finally:
                self.camera_ws = None
                self.camera_connected = False
    
    async def run(self):
        """运行模拟器主循环"""
        self.running = True
        self.log("ESP32模拟器启动")
        
        # 初始化资源
        self._init_camera()
        self._init_udp()
        
        try:
            # 连接WebSocket
            await self.connect_camera_websocket()
            
            # 主循环
            while self.running:
                # 发送相机帧
                if self.camera_connected:
                    await self._send_camera_frame()
                else:
                    # 尝试重新连接
                    await self.connect_camera_websocket()
                    await asyncio.sleep(1)
                
                # 发送IMU数据
                self._send_imu_data()
                
                # 小延迟以减少CPU使用率
                await asyncio.sleep(0.01)
        
        except KeyboardInterrupt:
            self.log("收到中断信号，正在停止...")
        except Exception as e:
            self.log(f"运行时错误: {e}")
        finally:
            # 清理资源
            self.running = False
            await self.disconnect_camera_websocket()
            
            if self.udp_socket:
                self.udp_socket.close()
                self.log("UDP套接字已关闭")
            
            if self.cap and self.is_video:
                self.cap.release()
                self.log("相机资源已释放")
            
            self.log("ESP32模拟器已停止")
    
    def stop(self):
        """停止模拟器"""
        self.running = False

async def main():
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='ESP32模拟器 - 用于调试AI眼镜导航系统')
    parser.add_argument('--server-ip', type=str, default='localhost', help='服务器IP地址')
    parser.add_argument('--server-port', type=int, default=8081, help='服务器端口')
    parser.add_argument('--udp-port', type=int, default=12345, help='UDP端口')
    parser.add_argument('--camera', type=str, help='相机源（图片/视频路径或摄像头索引）')
    parser.add_argument('--frame-rate', type=int, default=15, help='相机帧发送频率(Hz)')
    parser.add_argument('--imu-rate', type=int, default=50, help='IMU数据发送频率(Hz)')
    parser.add_argument('--debug', action='store_true', help='启用调试日志')
    
    args = parser.parse_args()
    
    # 处理相机源参数
    camera_source = None
    if args.camera:
        # 尝试作为整数处理（摄像头索引）
        if args.camera.isdigit():
            camera_source = int(args.camera)
        else:
            camera_source = args.camera
    
    # 创建并运行模拟器
    simulator = ESP32Simulator(
        server_ip=args.server_ip,
        server_port=args.server_port,
        udp_port=args.udp_port,
        camera_source=camera_source,
        frame_rate=args.frame_rate,
        imu_rate=args.imu_rate,
        debug=args.debug
    )
    
    await simulator.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nESP32模拟器已手动停止")
    except Exception as e:
        print(f"运行错误: {e}")