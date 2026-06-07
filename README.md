---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: b0c5858beb4860d2a0bd2b5ff2b89813_e3665787621d11f19f62525400d9a7a1
    ReservedCode1: HWD1L6UVoSGMYYeRTZYgBTRMFry+5J48KH+ThqIpLgLU/eWHLo8m7/fyjOLzxE/snx/V5lO/Ujh2JtqFzuQkXOKQg1aFmRwQoworoG4P6JBEnIUjvtKkS0qff84yt8uGrhrJHoU96paEhC+lV0lkNhFQtbjol15UDKAcqt5cVGJ/EX7qcrYDCHhrMp8=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: b0c5858beb4860d2a0bd2b5ff2b89813_e3665787621d11f19f62525400d9a7a1
    ReservedCode2: HWD1L6UVoSGMYYeRTZYgBTRMFry+5J48KH+ThqIpLgLU/eWHLo8m7/fyjOLzxE/snx/V5lO/Ujh2JtqFzuQkXOKQg1aFmRwQoworoG4P6JBEnIUjvtKkS0qff84yt8uGrhrJHoU96paEhC+lV0lkNhFQtbjol15UDKAcqt5cVGJ/EX7qcrYDCHhrMp8=
---

# 乐转站 v5.8.6 — Android APK 构建指南

## 项目结构

```
picksound_android/
├── main.py              # Kivy UI 入口
├── core.py              # 核心逻辑（搜索/下载/转换）
├── buildozer.spec       # Buildozer 构建配置
├── pyproject.toml       # BeeWare briefcase 配置（备用）
└── README.md
```

## 方式一：Buildozer（推荐，Kivy 方案）

### 环境要求
- Linux (Ubuntu 20.04+ 推荐)
- Python 3.8+
- Java JDK 17+

### 构建步骤

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y python3-pip python3-dev \
    git zip unzip openjdk-17-jdk \
    autoconf libtool pkg-config zlib1g-dev \
    libncurses5-dev libncursesw5-dev libtinfo5 \
    cmake libffi-dev libssl-dev

pip install buildozer cython kivy

# 2. 初始化 Buildozer（首次）
buildozer init

# 3. 构建 APK
buildozer android debug

# 产物位于 bin/ 目录: picksound_android-5.8.6-arm64-v8a-debug.apk
```

### 构建 Release 版本

```bash
# 需先配置签名密钥
buildozer android release
```

## 方式二：Google Colab（无需本地 Linux）

在 Colab 中执行：

```python
!pip install buildozer cython
!buildozer init

# 修改 buildozer.spec 后：
!buildozer android debug
```

## 方式三：BeeWare Briefcase（实验性）

```bash
pip install briefcase toga-android
briefcase create android
briefcase build android
briefcase run android
```

## 注意事项

1. **ffmpeg**：Android 版不包含 ffmpeg，格式转换/音频提取功能需要安装 mobile-ffmpeg
2. **首次构建**需下载 Android SDK/NDK（约 2GB），耗时较长
3. **目标架构**：当前配置为 arm64-v8a（支持 2019 年后大部分手机）
4. **签名**：正式发布需 APK 签名
*（内容由AI生成，仅供参考）*
