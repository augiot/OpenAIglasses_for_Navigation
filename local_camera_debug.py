# local_camera_debug.py
# -*- coding: utf-8 -*-
"""
本地摄像头调试模块
用于在不连接ESP32眼镜的情况下，使用本地摄像头进行PC端调试
"""
import os
import sys
import threading
import time
import cv2
import numpy as np
import bridge_io

# 本地摄像头参数
CAMERA_INDEX = 0  # 默认使用第一个摄像头
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
FPS_LIMIT = 15  # 限制帧率以节省资源

# 调试模式标志
_debug_mode = False
_camera_thread = None
_stop_event = threading.Event()

def start_local_camera_mode():
    """
    启动本地摄像头调试模式
    此函数会启动一个线程，从本地摄像头读取视频帧并推送到bridge_io中
    """
    global _debug_mode, _camera_thread, _stop_event
    
    if _debug_mode:
        print("[DEBUG] 本地摄像头模式已经启动")
        return True
    
    print("[DEBUG] 启动本地摄像头调试模式...")
    
    # 重置停止事件
    _stop_event.clear()
    
    # 创建并启动摄像头线程
    _camera_thread = threading.Thread(target=_camera_worker, daemon=True)
    _camera_thread.start()
    
    _debug_mode = True
    print(f"[DEBUG] 本地摄像头调试模式已启动，使用摄像头索引: {CAMERA_INDEX}")
    print(f"[DEBUG] 分辨率: {CAMERA_WIDTH}x{CAMERA_HEIGHT}, 帧率限制: {FPS_LIMIT}")
    print("[DEBUG] 按Ctrl+C或调用stop_local_camera_mode()停止")
    
    return True

def stop_local_camera_mode():
    """
    停止本地摄像头调试模式
    """
    global _debug_mode
    
    if not _debug_mode:
        print("[DEBUG] 本地摄像头模式未启动")
        return True
    
    print("[DEBUG] 停止本地摄像头调试模式...")
    
    # 设置停止事件
    _stop_event.set()
    
    # 等待线程结束
    if _camera_thread and _camera_thread.is_alive():
        _camera_thread.join(timeout=5.0)
    
    _debug_mode = False
    print("[DEBUG] 本地摄像头调试模式已停止")
    
    return True

def _camera_worker():
    """
    摄像头工作线程函数
    从本地摄像头读取帧并推送到bridge_io
    """
    cap = None
    try:
        # 打开摄像头
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print(f"[DEBUG ERROR] 无法打开摄像头 {CAMERA_INDEX}")
            return
        
        # 设置摄像头分辨率
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        
        print(f"[DEBUG] 摄像头已打开，实际分辨率: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
        
        # 帧率控制
        frame_interval = 1.0 / FPS_LIMIT
        last_frame_time = 0
        
        while not _stop_event.is_set():
            # 帧率控制
            current_time = time.time()
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.005)  # 短暂睡眠以减少CPU占用
                continue
            last_frame_time = current_time
            
            # 读取一帧
            ret, frame = cap.read()
            if not ret:
                print("[DEBUG ERROR] 无法读取摄像头帧")
                break
            
            # 可选：镜像翻转（如果需要）
            # frame = cv2.flip(frame, 1)
            
            # 将BGR帧编码为JPEG
            ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ret:
                print("[DEBUG ERROR] JPEG编码失败")
                continue
            
            # 将JPEG数据推送到bridge_io
            jpeg_bytes = jpeg.tobytes()
            bridge_io.push_raw_jpeg(jpeg_bytes)
            
    except Exception as e:
        print(f"[DEBUG ERROR] 摄像头工作线程异常: {e}")
    finally:
        # 确保释放摄像头
        if cap is not None:
            cap.release()
        print("[DEBUG] 摄像头已释放")

def is_debug_mode():
    """
    检查是否处于调试模式
    """
    return _debug_mode

# 如果作为脚本直接运行
if __name__ == "__main__":
    try:
        print("本地摄像头调试工具")
        print("此工具将启动本地摄像头并将视频流推送到bridge_io")
        print("用于在不连接ESP32眼镜的情况下进行PC端调试")
        print("\n按Ctrl+C退出")
        
        # 启动本地摄像头模式
        start_local_camera_mode()
        
        # 主线程保持运行
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n接收到中断信号")
    finally:
        # 确保停止摄像头
        stop_local_camera_mode()
        print("程序已退出")