#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导航眼镜系统客户端
用于连接OpenAIglasses_for_Navigation服务，提供控制和监控功能
"""

import os
import sys
import json
import asyncio
import websockets
import requests
from typing import Optional, Dict, Any, Callable
import logging
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('navigation_client')

class NavigationClient:
    """导航眼镜系统客户端"""
    
    def __init__(self, host='localhost', port=8081):
        """初始化客户端
        
        Args:
            host: 服务器主机名
            port: 服务器端口
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.ws_base_url = f"ws://{host}:{port}"
        
        # WebSocket连接
        self.ws_ui: Optional[websockets.WebSocketClientProtocol] = None
        self.ws_viewer: Optional[websockets.WebSocketClientProtocol] = None
        self.ws_imu: Optional[websockets.WebSocketClientProtocol] = None
        
        # 回调函数
        self.on_ui_message: Optional[Callable[[str], None]] = None
        self.on_camera_frame: Optional[Callable[[bytes], None]] = None
        self.on_imu_data: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # 运行状态
        self.running = False
        self.tasks = []
    
    async def connect_ui(self):
        """连接到UI WebSocket端点"""
        ws_url = f"{self.ws_base_url}/ws_ui"
        try:
            self.ws_ui = await websockets.connect(ws_url)
            logger.info(f"已连接到UI WebSocket: {ws_url}")
            
            # 启动消息接收任务
            task = asyncio.create_task(self._receive_ui_messages())
            self.tasks.append(task)
            return True
        except Exception as e:
            logger.error(f"连接UI WebSocket失败: {e}")
            return False
    
    async def _receive_ui_messages(self):
        """接收UI消息的任务"""
        if not self.ws_ui:
            return
        
        try:
            while self.running:
                message = await self.ws_ui.recv()
                logger.debug(f"收到UI消息: {message}")
                if self.on_ui_message:
                    self.on_ui_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("UI WebSocket连接已关闭")
        except Exception as e:
            logger.error(f"接收UI消息时出错: {e}")
    
    async def connect_viewer(self):
        """连接到相机查看器WebSocket端点"""
        ws_url = f"{self.ws_base_url}/ws/viewer"
        try:
            self.ws_viewer = await websockets.connect(ws_url)
            logger.info(f"已连接到相机查看器WebSocket: {ws_url}")
            
            # 启动视频帧接收任务
            task = asyncio.create_task(self._receive_camera_frames())
            self.tasks.append(task)
            return True
        except Exception as e:
            logger.error(f"连接相机查看器WebSocket失败: {e}")
            return False
    
    async def _receive_camera_frames(self):
        """接收相机帧的任务"""
        if not self.ws_viewer:
            return
        
        try:
            while self.running:
                # 接收二进制数据（JPEG图像）
                frame_data = await self.ws_viewer.recv()
                logger.debug(f"收到相机帧，大小: {len(frame_data)} 字节")
                if self.on_camera_frame:
                    self.on_camera_frame(frame_data)
        except websockets.exceptions.ConnectionClosed:
            logger.info("相机查看器WebSocket连接已关闭")
        except Exception as e:
            logger.error(f"接收相机帧时出错: {e}")
    
    async def connect_imu(self):
        """连接到IMU WebSocket端点"""
        ws_url = f"{self.ws_base_url}/ws"
        try:
            self.ws_imu = await websockets.connect(ws_url)
            logger.info(f"已连接到IMU WebSocket: {ws_url}")
            
            # 启动IMU数据接收任务
            task = asyncio.create_task(self._receive_imu_data())
            self.tasks.append(task)
            return True
        except Exception as e:
            logger.error(f"连接IMU WebSocket失败: {e}")
            return False
    
    async def _receive_imu_data(self):
        """接收IMU数据的任务"""
        if not self.ws_imu:
            return
        
        try:
            while self.running:
                # 接收文本数据（JSON格式）
                data_str = await self.ws_imu.recv()
                try:
                    data = json.loads(data_str)
                    logger.debug(f"收到IMU数据: {data}")
                    if self.on_imu_data:
                        self.on_imu_data(data)
                except json.JSONDecodeError as e:
                    logger.error(f"解析IMU数据失败: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("IMU WebSocket连接已关闭")
        except Exception as e:
            logger.error(f"接收IMU数据时出错: {e}")
    
    async def send_audio_command(self, command: str):
        """发送音频命令
        
        Args:
            command: 要发送的命令（START/STOP/PROMPT:文本）
        """
        ws_url = f"{self.ws_base_url}/ws_audio"
        try:
            async with websockets.connect(ws_url) as ws:
                logger.info(f"连接到音频WebSocket并发送命令: {command}")
                await ws.send(command)
                # 等待响应
                response = await ws.recv()
                logger.info(f"音频命令响应: {response}")
                return response
        except Exception as e:
            logger.error(f"发送音频命令失败: {e}")
            return None
    
    async def start_asr(self):
        """启动语音识别"""
        return await self.send_audio_command("START")
    
    async def stop_asr(self):
        """停止语音识别"""
        return await self.send_audio_command("STOP")
    
    async def send_text_prompt(self, text: str):
        """发送文本提示
        
        Args:
            text: 要发送的文本
        """
        return await self.send_audio_command(f"PROMPT:{text}")
    
    async def start_blind_path_navigation(self):
        """启动盲道导航"""
        return await self.send_text_prompt("开始盲道导航")
    
    async def stop_navigation(self):
        """停止导航"""
        return await self.send_text_prompt("停止导航")
    
    async def start_cross_street(self):
        """开始过马路模式"""
        return await self.send_text_prompt("开始过马路")
    
    async def stop_cross_street(self):
        """结束过马路模式"""
        return await self.send_text_prompt("结束过马路")
    
    async def start_traffic_light_detection(self):
        """开始红绿灯检测"""
        return await self.send_text_prompt("检测红绿灯")
    
    async def stop_traffic_light_detection(self):
        """停止红绿灯检测"""
        return await self.send_text_prompt("停止检测")
    
    async def search_item(self, item_name: str):
        """搜索物品
        
        Args:
            item_name: 要搜索的物品名称
        """
        return await self.send_text_prompt(f"帮我找{item_name}")
    
    async def found_item(self):
        """通知系统已找到物品"""
        return await self.send_text_prompt("找到了")
    
    def is_healthy(self):
        """检查服务器健康状态"""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            return response.status_code == 200 and response.text.strip() == "OK"
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False
    
    async def start(self):
        """启动客户端，连接所有WebSocket端点"""
        self.running = True
        
        # 检查服务器健康状态
        if not self.is_healthy():
            logger.error(f"服务器{self.base_url}不健康，无法启动客户端")
            self.running = False
            return False
        
        # 连接所有端点
        await asyncio.gather(
            self.connect_ui(),
            self.connect_viewer(),
            self.connect_imu(),
            return_exceptions=True
        )
        
        logger.info("客户端已启动")
        return True
    
    async def stop(self):
        """停止客户端，关闭所有连接"""
        self.running = False
        
        # 取消所有任务
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        
        # 关闭WebSocket连接
        if self.ws_ui:
            await self.ws_ui.close()
            self.ws_ui = None
        
        if self.ws_viewer:
            await self.ws_viewer.close()
            self.ws_viewer = None
        
        if self.ws_imu:
            await self.ws_imu.close()
            self.ws_imu = None
        
        logger.info("客户端已停止")

# 示例用法
async def main():
    # 创建客户端实例
    client = NavigationClient(host='localhost', port=8081)
    
    # 设置回调函数
    def on_ui_message(message):
        print(f"收到UI消息: {message}")
    
    def on_camera_frame(frame_data):
        print(f"收到相机帧，大小: {len(frame_data)} 字节")
        # 这里可以保存帧到文件或显示
    
    def on_imu_data(data):
        print(f"收到IMU数据: {json.dumps(data, indent=2)}")
    
    client.on_ui_message = on_ui_message
    client.on_camera_frame = on_camera_frame
    client.on_imu_data = on_imu_data
    
    # 启动客户端
    if await client.start():
        try:
            # 示例：启动盲道导航
            print("\n===== 测试盲道导航 =====")
            response = await client.start_blind_path_navigation()
            print(f"启动盲道导航响应: {response}")
            
            # 等待10秒
            await asyncio.sleep(10)
            
            # 示例：停止导航
            print("\n===== 停止导航 =====")
            response = await client.stop_navigation()
            print(f"停止导航响应: {response}")
            
            # 等待5秒
            await asyncio.sleep(5)
            
            # 示例：搜索物品
            print("\n===== 测试搜索物品 =====")
            response = await client.search_item("红牛")
            print(f"搜索物品响应: {response}")
            
            # 等待10秒
            await asyncio.sleep(10)
            
            # 示例：通知找到物品
            print("\n===== 测试找到物品 =====")
            response = await client.found_item()
            print(f"找到物品响应: {response}")
            
            # 等待5秒
            await asyncio.sleep(5)
            
        except KeyboardInterrupt:
            print("\n用户中断")
        finally:
            # 停止客户端
            await client.stop()

if __name__ == "__main__":
    # 运行示例
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("程序已停止")