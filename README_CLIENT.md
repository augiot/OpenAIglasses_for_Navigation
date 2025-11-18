# 导航眼镜系统客户端使用指南

本文档介绍了导航眼镜系统的客户端工具，包括如何使用这些工具与导航眼镜系统进行交互。

## 目录结构

```
/Users/augzhou/Documents/MyCode/02pyhton/OpenAIglasses_for_Navigation/
├── app_main_v0.py          # 导航眼镜系统主服务器程序
├── navigation_client.py    # 核心客户端类
├── interactive_client.py   # 交互式命令行客户端
├── start_client.sh         # 启动脚本（将在下一步创建）
└── frames/                 # 保存相机帧的目录（自动创建）
```

## 客户端功能概述

### 1. 核心客户端类 (`navigation_client.py`)

`NavigationClient` 类实现了与导航眼镜系统的所有连接和交互功能，包括：

- 连接到系统的多个WebSocket端点：UI消息、相机画面、IMU数据
- 发送各种命令：启动/停止语音识别、盲道导航、过马路模式、红绿灯检测、物品搜索等
- 接收和处理系统返回的各种数据

### 2. 交互式命令行客户端 (`interactive_client.py`)

提供用户友好的命令行界面，方便用户测试和使用导航眼镜系统的各种功能，包括：

- 盲道导航模式
- 过马路模式
- 红绿灯检测
- 物品搜索
- 发送自定义命令
- 查看最近UI消息
- 显示系统状态
- 停止所有导航模式

## 使用方法

### 1. 准备工作

确保导航眼镜系统服务器 (`app_main_v0.py`) 已启动并正在运行。

### 2. 运行交互式命令行客户端

最简单的使用方式是直接运行交互式命令行客户端：

```bash
python3 interactive_client.py
```

运行后，客户端会提示您输入服务器的主机名和端口（默认为 `localhost:8081`）。连接成功后，您可以通过菜单选择各种功能。

### 3. 使用核心客户端类

您也可以在自己的Python程序中使用核心客户端类：

```python
from navigation_client import NavigationClient
import asyncio

async def main():
    # 创建客户端实例
    client = NavigationClient(host='localhost', port=8081)
    
    # 设置回调函数
    def on_ui_message(message):
        print(f"收到UI消息: {message}")
    
    client.on_ui_message = on_ui_message
    
    # 启动客户端
    if await client.start():
        # 使用各种功能
        await client.start_blind_path_navigation()
        
        # 等待一段时间
        await asyncio.sleep(5)
        
        # 停止导航
        await client.stop_navigation()
        
        # 停止客户端
        await client.stop()

# 运行
asyncio.run(main())
```

## 客户端功能详解

### 核心功能

#### 盲道导航
- 开始盲道导航：`await client.start_blind_path_navigation()`
- 停止导航：`await client.stop_navigation()`

#### 过马路模式
- 开始过马路：`await client.start_cross_street()`
- 结束过马路：`await client.stop_cross_street()`

#### 红绿灯检测
- 开始红绿灯检测：`await client.start_traffic_light_detection()`
- 停止红绿灯检测：`await client.stop_traffic_light_detection()`

#### 物品搜索
- 搜索物品：`await client.search_item("物品名称")`
- 通知找到物品：`await client.found_item()`

#### 语音识别
- 启动语音识别：`await client.start_asr()`
- 停止语音识别：`await client.stop_asr()`

#### 自定义命令
- 发送文本命令：`await client.send_text_prompt("命令文本")`

### 回调函数

客户端提供了以下回调函数接口，您可以根据需要实现：

```python
# 接收UI消息
client.on_ui_message = lambda message: print(f"UI消息: {message}")

# 接收相机帧（JPEG格式二进制数据）
client.on_camera_frame = lambda frame_data: print(f"收到相机帧，大小: {len(frame_data)} 字节")

# 接收IMU数据（JSON格式）
client.on_imu_data = lambda data: print(f"IMU数据: {data}")
```

## 相机帧保存

交互式客户端会自动保存接收到的相机帧到 `frames` 目录，文件命名格式为 `frame_YYYYMMDD_HHMMSS_mmm.jpg`。

## 注意事项

1. 确保服务器与客户端在同一网络中，且服务器端口已正确配置。
2. 如果遇到连接问题，请检查防火墙设置。
3. 长时间运行可能会占用较多内存，建议定期重启客户端。
4. 相机帧保存功能会占用磁盘空间，请定期清理 `frames` 目录。

## 故障排除

### 连接失败
- 检查服务器是否正在运行
- 确认主机名和端口是否正确
- 检查网络连接和防火墙设置

### 命令无响应
- 确认服务器和客户端连接正常
- 检查命令格式是否正确
- 查看服务器日志以获取更多信息

### 相机帧未保存
- 确认有写入权限到 `frames` 目录
- 检查磁盘空间是否充足

## 示例用例

### 用例1：测试盲道导航

```bash
python3 interactive_client.py
# 选择 1. 盲道导航模式
# 按Enter键启动
# 测试完成后，按Enter键返回主菜单
```

### 用例2：搜索特定物品

```bash
python3 interactive_client.py
# 选择 4. 物品搜索
# 输入物品名称，如 "红牛"
# 测试完成后，按Enter键表示已找到物品
```

### 用例3：查看系统状态

```bash
python3 interactive_client.py
# 选择 7. 显示系统状态
# 查看服务器健康状态、连接状态和最近保存的相机帧
```

## 更新日志

### v1.0
- 初始版本
- 实现核心客户端类和交互式命令行界面
- 支持盲道导航、过马路模式、红绿灯检测和物品搜索
- 自动保存相机帧