#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导航眼镜系统交互式命令行客户端
提供命令行界面，方便用户测试和使用导航眼镜系统的各种功能
"""

import os
import sys
import json
import asyncio
import time
import datetime
from navigation_client import NavigationClient
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('interactive_client')

# 颜色定义
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# 保存最近的相机帧
last_frame_path = None

async def save_camera_frame(frame_data):
    """保存相机帧到文件"""
    global last_frame_path
    try:
        # 创建frames目录
        frames_dir = 'frames'
        os.makedirs(frames_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        filename = f"{frames_dir}/frame_{timestamp}.jpg"
        
        # 保存文件
        with open(filename, 'wb') as f:
            f.write(frame_data)
        
        last_frame_path = filename
        logger.info(f"已保存相机帧: {filename}")
    except Exception as e:
        logger.error(f"保存相机帧失败: {e}")

async def main():
    # 打印欢迎信息
    print(f"{Colors.HEADER}{Colors.BOLD}\n==== 导航眼镜系统交互式命令行客户端 ====\n{Colors.ENDC}")
    print("此客户端提供命令行界面，方便您测试和使用导航眼镜系统的各种功能。")
    print(f"{Colors.BLUE}提示: 按Enter键执行命令，输入'exit'或'quit'退出客户端。{Colors.ENDC}\n")
    
    # 获取服务器配置
    host = input("请输入服务器主机名 (默认: localhost): ") or "localhost"
    port = input("请输入服务器端口 (默认: 8081): ") or "8081"
    port = int(port)
    
    # 创建客户端实例
    client = NavigationClient(host=host, port=port)
    
    # 设置回调函数
    ui_messages = []
    def on_ui_message(message):
        nonlocal ui_messages
        ui_messages.append(message)
        # 只保留最近20条消息
        ui_messages = ui_messages[-20:]
        print(f"\n{Colors.GREEN}[UI消息] {message}{Colors.ENDC}")
    
    def on_camera_frame(frame_data):
        # 异步保存帧
        asyncio.create_task(save_camera_frame(frame_data))
    
    def on_imu_data(data):
        # 可以在这里处理IMU数据，但为了不干扰命令行界面，不打印所有数据
        pass
    
    client.on_ui_message = on_ui_message
    client.on_camera_frame = on_camera_frame
    client.on_imu_data = on_imu_data
    
    # 启动客户端
    print(f"\n{Colors.BLUE}正在连接到服务器 {host}:{port}...{Colors.ENDC}")
    if await client.start():
        print(f"{Colors.GREEN}连接成功！{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}连接失败！请检查服务器是否正在运行。{Colors.ENDC}")
        return
    
    # 显示主菜单
    def show_menu():
        print(f"\n{Colors.HEADER}{Colors.BOLD}===== 导航眼镜系统主菜单 ====={Colors.ENDC}")
        print(f"{Colors.BOLD}1. {Colors.GREEN}盲道导航模式{Colors.ENDC}")
        print(f"{Colors.BOLD}2. {Colors.GREEN}过马路模式{Colors.ENDC}")
        print(f"{Colors.BOLD}3. {Colors.GREEN}红绿灯检测{Colors.ENDC}")
        print(f"{Colors.BOLD}4. {Colors.GREEN}物品搜索{Colors.ENDC}")
        print(f"{Colors.BOLD}5. {Colors.GREEN}发送自定义命令{Colors.ENDC}")
        print(f"{Colors.BOLD}6. {Colors.GREEN}查看最近UI消息{Colors.ENDC}")
        print(f"{Colors.BOLD}7. {Colors.GREEN}显示系统状态{Colors.ENDC}")
        print(f"{Colors.BOLD}8. {Colors.GREEN}停止所有导航模式{Colors.ENDC}")
        print(f"{Colors.BOLD}exit/quit. {Colors.WARNING}退出客户端{Colors.ENDC}")
        print("-" * 50)
    
    try:
        while True:
            show_menu()
            choice = input(f"\n{Colors.BOLD}请输入您的选择 (1-8): {Colors.ENDC}")
            
            # 处理退出
            if choice.lower() in ['exit', 'quit', 'q']:
                print(f"\n{Colors.BOLD}正在退出客户端...{Colors.ENDC}")
                break
            
            # 处理盲道导航模式
            elif choice == '1':
                print(f"\n{Colors.BLUE}===== 盲道导航模式 ====={Colors.ENDC}")
                response = await client.start_blind_path_navigation()
                print(f"\n{Colors.GREEN}启动盲道导航响应: {response}{Colors.ENDC}")
                print(f"{Colors.BOLD}按Enter键返回主菜单，盲道导航将继续运行...{Colors.ENDC}")
                input()
            
            # 处理过马路模式
            elif choice == '2':
                print(f"\n{Colors.BLUE}===== 过马路模式 ====={Colors.ENDC}")
                response = await client.start_cross_street()
                print(f"\n{Colors.GREEN}启动过马路模式响应: {response}{Colors.ENDC}")
                print(f"{Colors.BOLD}按Enter键结束过马路模式并返回主菜单...{Colors.ENDC}")
                input()
                # 自动结束过马路模式
                response = await client.stop_cross_street()
                print(f"{Colors.GREEN}结束过马路模式响应: {response}{Colors.ENDC}")
            
            # 处理红绿灯检测
            elif choice == '3':
                print(f"\n{Colors.BLUE}===== 红绿灯检测 ====={Colors.ENDC}")
                response = await client.start_traffic_light_detection()
                print(f"\n{Colors.GREEN}启动红绿灯检测响应: {response}{Colors.ENDC}")
                print(f"{Colors.BOLD}按Enter键停止红绿灯检测并返回主菜单...{Colors.ENDC}")
                input()
                # 自动停止红绿灯检测
                response = await client.stop_traffic_light_detection()
                print(f"{Colors.GREEN}停止红绿灯检测响应: {response}{Colors.ENDC}")
            
            # 处理物品搜索
            elif choice == '4':
                print(f"\n{Colors.BLUE}===== 物品搜索 ====={Colors.ENDC}")
                item_name = input("请输入要搜索的物品名称: ")
                if item_name.strip():
                    response = await client.search_item(item_name)
                    print(f"\n{Colors.GREEN}搜索物品响应: {response}{Colors.ENDC}")
                    print(f"{Colors.BOLD}按Enter键表示已找到物品并返回主菜单...{Colors.ENDC}")
                    input()
                    # 自动通知找到物品
                    response = await client.found_item()
                    print(f"{Colors.GREEN}通知找到物品响应: {response}{Colors.ENDC}")
                else:
                    print(f"{Colors.WARNING}物品名称不能为空！{Colors.ENDC}")
            
            # 处理自定义命令
            elif choice == '5':
                print(f"\n{Colors.BLUE}===== 发送自定义命令 ====={Colors.ENDC}")
                print(f"{Colors.BOLD}命令类型: {Colors.ENDC}")
                print(f"  1. {Colors.GREEN}直接文本命令{Colors.ENDC}")
                print(f"  2. {Colors.GREEN}启动语音识别{Colors.ENDC}")
                print(f"  3. {Colors.GREEN}停止语音识别{Colors.ENDC}")
                
                cmd_type = input("请选择命令类型 (1-3): ")
                
                if cmd_type == '1':
                    cmd_text = input("请输入命令文本: ")
                    if cmd_text.strip():
                        response = await client.send_text_prompt(cmd_text)
                        print(f"\n{Colors.GREEN}命令响应: {response}{Colors.ENDC}")
                    else:
                        print(f"{Colors.WARNING}命令文本不能为空！{Colors.ENDC}")
                elif cmd_type == '2':
                    response = await client.start_asr()
                    print(f"\n{Colors.GREEN}启动语音识别响应: {response}{Colors.ENDC}")
                elif cmd_type == '3':
                    response = await client.stop_asr()
                    print(f"\n{Colors.GREEN}停止语音识别响应: {response}{Colors.ENDC}")
                else:
                    print(f"{Colors.WARNING}无效的命令类型！{Colors.ENDC}")
                    
                print(f"{Colors.BOLD}按Enter键返回主菜单...{Colors.ENDC}")
                input()
            
            # 查看最近UI消息
            elif choice == '6':
                print(f"\n{Colors.BLUE}===== 最近UI消息 ====={Colors.ENDC}")
                if not ui_messages:
                    print(f"{Colors.WARNING}没有收到UI消息。{Colors.ENDC}")
                else:
                    print(f"{Colors.BOLD}最近收到的{len(ui_messages)}条UI消息:{Colors.ENDC}")
                    for i, msg in enumerate(ui_messages[-10:], start=max(1, len(ui_messages)-9)):
                        print(f"{Colors.GREEN}{i}. {msg}{Colors.ENDC}")
                print(f"{Colors.BOLD}按Enter键返回主菜单...{Colors.ENDC}")
                input()
            
            # 显示系统状态
            elif choice == '7':
                print(f"\n{Colors.BLUE}===== 系统状态 ====={Colors.ENDC}")
                
                # 检查服务器健康状态
                is_healthy = client.is_healthy()
                health_status = f"{Colors.GREEN}正常{Colors.ENDC}" if is_healthy else f"{Colors.FAIL}异常{Colors.ENDC}"
                print(f"服务器健康状态: {health_status}")
                
                # 显示连接状态
                ui_status = f"{Colors.GREEN}已连接{Colors.ENDC}" if client.ws_ui else f"{Colors.FAIL}未连接{Colors.ENDC}"
                viewer_status = f"{Colors.GREEN}已连接{Colors.ENDC}" if client.ws_viewer else f"{Colors.FAIL}未连接{Colors.ENDC}"
                imu_status = f"{Colors.GREEN}已连接{Colors.ENDC}" if client.ws_imu else f"{Colors.FAIL}未连接{Colors.ENDC}"
                
                print(f"UI WebSocket连接: {ui_status}")
                print(f"相机查看器连接: {viewer_status}")
                print(f"IMU数据连接: {imu_status}")
                
                # 显示最近保存的相机帧
                if last_frame_path:
                    print(f"最近保存的相机帧: {Colors.BLUE}{last_frame_path}{Colors.ENDC}")
                else:
                    print(f"最近保存的相机帧: {Colors.WARNING}暂无{Colors.ENDC}")
                
                print(f"{Colors.BOLD}按Enter键返回主菜单...{Colors.ENDC}")
                input()
            
            # 停止所有导航模式
            elif choice == '8':
                print(f"\n{Colors.BLUE}===== 停止所有导航模式 ====={Colors.ENDC}")
                response = await client.stop_navigation()
                print(f"\n{Colors.GREEN}停止导航响应: {response}{Colors.ENDC}")
                print(f"{Colors.BOLD}按Enter键返回主菜单...{Colors.ENDC}")
                input()
            
            # 处理无效选择
            else:
                print(f"\n{Colors.FAIL}无效的选择！请输入1-8之间的数字。{Colors.ENDC}")
                await asyncio.sleep(1)
                
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}用户中断操作{Colors.ENDC}")
    finally:
        # 停止客户端
        print(f"\n{Colors.BLUE}正在关闭连接...{Colors.ENDC}")
        await client.stop()
        print(f"{Colors.GREEN}\n客户端已成功关闭。{Colors.ENDC}")

if __name__ == "__main__":
    # 运行交互式客户端
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}程序已停止{Colors.ENDC}")