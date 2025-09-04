# B站视频下载API服务

一个基于Flask的B站视频下载API服务，支持获取视频信息、选择视频质量并下载视频文件。

## 功能特性

- 🎥 获取B站视频详细信息
- 📊 获取视频可用质量选项
- ⬇️ 支持多种质量的视频下载
- 🔄 支持视频音频分离下载和合并
- 📋 任务状态查询和管理
- 🍪 支持Cookie认证访问会员视频
- 🌐 RESTful API接口设计
- ⚡ 异步下载任务处理
- 🎯 支持 `&q=auto` 参数获取全部视频和音频流

## 技术栈

- **后端框架**: Flask
- **跨域支持**: Flask-CORS
- **HTTP请求**: requests
- **视频处理**: FFmpeg (通过subprocess调用)
- **前端**: 支持任何能发送HTTP请求的客户端

## 安装说明

### 环境要求

- Python 3.7+
- FFmpeg (用于视频音频合并)

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/Suxiaoqinx/bilibili.git
   cd bilibili
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置Cookie (可选)**
   
   如需下载会员视频或高质量视频，请在项目根目录创建 `cookies.txt` 文件，并填入B站的Cookie信息。

5. **启动服务**
   ```bash
   python app.py
   ```

   服务将在 `http://localhost:5000` 启动

## API文档

### 基础信息

**基础URL**: `http://localhost:5000`

### 接口列表

#### 1. 获取API信息

**接口**: `GET /`

**描述**: 获取API基本信息和可用接口列表

**响应示例**:
```json
{
  "message": "B站视频下载API服务",
  "version": "1.0.0",
  "endpoints": {
    "GET /": "获取API信息",
    "GET /api/video/info": "获取视频信息 (支持 &q=auto 参数获取全部视频和音频流)",
    "GET /api/video/quality": "获取视频质量选项",
    "GET /api/video/download": "下载视频",
    "GET /api/download/status/<task_id>": "查询下载状态",
    "GET /api/download/file/<task_id>": "下载文件"
  }
}
```

#### 2. 获取视频信息

**接口**: `GET /api/video/info`

**参数**:
- `url` (必需): B站视频URL
- `q` (可选): 设置为 `auto` 时返回所有视频和音频流的完整信息，包括流地址

**请求示例**:
```
GET /api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD
GET /api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD&q=auto
```

**响应示例**:
```json
{
  "success": true,
  "title": "视频标题",
  "cover": "封面图片URL",
  "data": {
    "duration": 300,
    "highest_quality": {
      "video": {
        "quality_id": 80,
        "quality_name": "高清 1080P",
        "width": 1920,
        "height": 1080,
        "bandwidth": 2000000,
        "frame_rate": 30,
        "codecs": "avc1.640028"
      },
      "audio": {
        "quality_id": 30280,
        "quality_name": "320K",
        "bandwidth": 320000,
        "codecs": "mp4a.40.2"
      }
    },
    "video_streams": [
      {
        "quality_id": 80,
        "quality_name": "高清 1080P",
        "width": 1920,
        "height": 1080,
        "bandwidth": 2000000,
        "frame_rate": 30,
        "codecs": "avc1.640028",
        "url": "流地址 (仅在q=auto时返回)"
      }
    ],
    "audio_streams": [
      {
        "quality_id": 30280,
        "quality_name": "320K",
        "bandwidth": 320000,
        "codecs": "mp4a.40.2",
        "url": "流地址 (仅在q=auto时返回)"
      }
    ]
  }
}
```

#### 3. 获取视频质量选项

**接口**: `GET /api/video/quality`

**参数**:
- `url` (必需): B站视频URL

**请求示例**:
```
GET /api/video/quality?url=https://www.bilibili.com/video/BV1xx411c7mD
```

#### 4. 下载视频

**接口**: `GET /api/video/download`

**参数**:
- `url` (必需): B站视频URL
- `merge` (可选): 是否合并视频音频，默认true
- `filename` (可选): 自定义文件名
- `video_quality_index` (可选): 视频质量索引，默认0（最高质量）
- `audio_quality_index` (可选): 音频质量索引，默认0（最高质量）

**请求示例**:
```
GET /api/video/download?url=https://www.bilibili.com/video/BV1xx411c7mD&merge=true&filename=my_video
```

**成功响应**:
```json
{
  "success": true,
  "task_id": "uuid",
  "message": "下载任务已启动"
}
```

**重复请求响应** (HTTP 409):
```json
{
  "success": false,
  "error": "当前解析已经存在，请勿重复请求",
  "existing_task_id": "existing-uuid",
  "existing_status": "downloading"
}
```

#### 5. 查询下载状态

**接口**: `GET /api/download/status/<task_id>`

**响应示例**:
```json
{
  "task_id": "uuid",
  "status": "completed",
  "progress": 100,
  "message": "下载完成",
  "file_path": "/path/to/file.mp4"
}
```

#### 6. 下载文件

**接口**: `GET /api/download/file/<task_id>`

**描述**: 下载已完成的视频文件

## 使用示例

### Python示例

```python
import requests

# 获取视频基本信息
response = requests.get('http://localhost:5000/api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD')
print(response.json())

# 获取视频完整流信息
response = requests.get('http://localhost:5000/api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD&q=auto')
print(response.json())

# 下载视频
response = requests.get('http://localhost:5000/api/video/download?url=https://www.bilibili.com/video/BV1xx411c7mD&merge=true&filename=my_video')
task_id = response.json()['task_id']

# 查询下载状态
status_response = requests.get(f'http://localhost:5000/api/download/status/{task_id}')
print(status_response.json())
```

### JavaScript示例

```javascript
// 获取视频信息
fetch('http://localhost:5000/api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD')
  .then(response => response.json())
  .then(data => console.log(data));

// 获取完整流信息
fetch('http://localhost:5000/api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD&q=auto')
  .then(response => response.json())
  .then(data => console.log(data));

// 下载视频
fetch('http://localhost:5000/api/video/download?url=https://www.bilibili.com/video/BV1xx411c7mD&merge=true&filename=my_video')
  .then(response => response.json())
  .then(data => console.log(data));
```

## 质量映射表

### 视频质量

| quality_id | 质量名称 |
|------------|----------|
| 127 | 超清 8K |
| 126 | 杜比视界 |
| 125 | HDR真彩 |
| 120 | 超清 4K |
| 116 | 高清 1080P60 |
| 112 | 高清 1080P+ |
| 80 | 高清 1080P |
| 74 | 高清 720P60 |
| 64 | 高清 720P |
| 32 | 清晰 480P |
| 16 | 流畅 360P |

### 音频质量

| quality_id | 质量名称 |
|------------|----------|
| 30280 | 320K |
| 30232 | 128K |
| 30216 | 64K |

## 项目结构

```
bilibili/
├── app.py              # Flask应用主文件
├── bilibili.py         # B站视频处理核心模块
├── requirements.txt    # Python依赖包
├── cookies.txt         # Cookie配置文件 (需自行创建)
├── downloads/          # 下载文件存储目录
├── README.md           # 项目说明文档
└── venv/              # Python虚拟环境
```

## 注意事项

1. **Cookie配置**: 如需访问会员视频或高质量视频，请配置有效的B站Cookie
2. **FFmpeg依赖**: 视频音频合并功能需要安装FFmpeg
3. **网络环境**: 确保网络环境可以正常访问B站
4. **使用限制**: 请遵守B站的使用条款，仅用于个人学习和研究
5. **q=auto参数**: 使用此参数可获取完整的流地址信息，但请注意流地址可能有时效性

## 开发环境

- Python 3.13
- Flask 2.x
- Windows 10/11

## 许可证

本项目仅供学习和研究使用，请遵守相关法律法规和平台使用条款。

## 更新日志

### v1.1.0
- 新增 `&q=auto` 参数支持，可获取全部视频和音频流信息
- 优化JSON返回数据结构，确保字段顺序
- 添加质量ID到中文名称的映射
- 改进API文档和使用示例

### v1.0.0
- 基础视频信息获取功能
- 视频下载和合并功能
- 任务状态管理
- RESTful API设计