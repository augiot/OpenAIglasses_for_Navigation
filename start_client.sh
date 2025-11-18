#!/bin/bash

# 导航眼镜系统客户端启动脚本

echo "========================================"
echo "      导航眼镜系统客户端启动脚本       "
echo "========================================"

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3。请先安装Python 3.7或更高版本。"
    exit 1
fi

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 7 ]); then
    echo "警告: Python版本为 $PYTHON_VERSION，建议使用Python 3.7或更高版本。"
fi

# 检查依赖包
function check_dependency {
    python3 -c "import $1" &> /dev/null
    return $?
}

echo "\n正在检查依赖包..."

# 需要的依赖包
DEPENDENCIES=("websockets" "requests")
MISSING_DEPENDENCIES=()

for dep in "${DEPENDENCIES[@]}"; do
    if ! check_dependency "$dep"; then
        MISSING_DEPENDENCIES+=("$dep")
    else
        echo "✓ $dep 已安装"
    fi
 done

# 安装缺失的依赖包
if [ ${#MISSING_DEPENDENCIES[@]} -ne 0 ]; then
    echo "\n需要安装以下依赖包: ${MISSING_DEPENDENCIES[*]}"
    read -p "是否继续安装? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "\n正在安装依赖包..."
        pip3 install --upgrade pip
        pip3 install "${MISSING_DEPENDENCIES[@]}"
        
        if [ $? -ne 0 ]; then
            echo "\n错误: 安装依赖包失败。请尝试手动安装:"
            echo "pip3 install ${MISSING_DEPENDENCIES[*]}"
            exit 1
        else
            echo "\n✓ 依赖包安装成功"
        fi
    else
        echo "\n取消安装。请手动安装所需依赖包后再运行此脚本。"
        exit 1
    fi
fi

# 检查客户端文件是否存在
if [ ! -f "navigation_client.py" ]; then
    echo "\n错误: 未找到 navigation_client.py 文件。"
    echo "请确保此脚本与客户端文件在同一目录下。"
    exit 1
fi

if [ ! -f "interactive_client.py" ]; then
    echo "\n错误: 未找到 interactive_client.py 文件。"
    echo "请确保此脚本与客户端文件在同一目录下。"
    exit 1
fi

# 使脚本可执行
chmod +x "navigation_client.py"
chmod +x "interactive_client.py"

# 创建frames目录（如果不存在）
mkdir -p frames

echo "\n========================================"
echo "      启动交互式命令行客户端          "
echo "========================================"
echo "按Ctrl+C可以随时退出客户端"
echo "========================================"

# 启动交互式客户端
python3 interactive_client.py

# 清理和结束
echo "\n客户端已退出。"