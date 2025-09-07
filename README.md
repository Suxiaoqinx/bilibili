# B站视频下载API服务

一个基于FastAPI的B站视频下载API服务，支持获取视频信息、选择视频质量并下载视频文件。

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
- 📝 **纯文本响应格式**，易于阅读和处理

### 💡 使用建议

- **推荐安装FFmpeg**: 获得最佳的合并质量和性能
- **查看合并状态**: 通过API响应了解当前使用的合并方法

## 技术栈

- **后端框架**: FastAPI
- **跨域支持**: FastAPI内置CORS
- **HTTP请求**: requests
- **视频处理**: FFmpeg
- **前端**: 支持任何能发送HTTP请求的客户端

## 安装说明

### 环境要求

- Python 3.7+
- FFmpeg

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
   
   请执行bililogin.py 然后扫码登录账号 会自动将生成的cookie提取到cookies.txt文件内
   注意：cookies.txt文件需要与项目根目录在同一级目录下
   登录后即可下载会员视频和高质量视频

5. **启动服务**
   ```bash
   uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
   ```

   服务将在 `http://localhost:8000` 启动

### API调试

**工具**: 推荐使用Postman、curl或浏览器直接访问API

**注意**: 所有接口均返回纯文本格式，便于直接查看和处理。

或者使用浏览器直接访问 `http://localhost:8000/api` 直接调用API接口测试。

### 基础信息

**基础URL**: `http://localhost:8000`

**响应格式**: 所有API接口均返回纯文本格式 (`text/plain; charset=utf-8`)，便于浏览器直接查看和命令行工具处理。

### 接口列表

#### 1. 获取API信息

**接口**: `GET /`

**描述**: 获取API基本信息和可用接口列表

**响应示例**:
```
=== B站视频下载API服务 ===
版本: 2.1.0

🎯 核心特性:
• 状态反馈 - 实时显示当前使用的合并方法

可用接口:
• GET / - 获取API信息
• GET /api/video/info - 获取视频信息 (支持 &q=auto 参数获取全部视频和音频流)
• GET /api/video/quality - 获取视频质量选项
• GET /api/video/download - 智能下载视频 (自动选择最佳合并方案)
• GET /api/download/status/<task_id> - 查询下载状态 (包含合并方法信息)
• GET /api/download/file/<task_id> - 下载文件
• GET /api/tasks - 查看所有任务列表

使用说明:
- 所有接口返回纯文本格式，便于阅读
- 支持跨域访问
- 部分功能需要配置Cookie
- 智能合并：推荐安装FFmpeg以获得最佳效果，但不安装也能正常工作
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

**响应示例** (基本信息):
```
=== 视频信息 ===
标题: 【标题】视频标题
封面: https://i0.hdslb.com/bfs/archive/cover.jpg
时长: 5分00秒

=== 最高质量 ===
视频: 高清 1080P (1920x1080, 30fps)
音频: 320K

=== 可用视频流 ===
1. 高清 1080P (1920x1080, 30fps) - 2000000 bps
2. 高清 720P (1280x720, 30fps) - 1500000 bps

=== 可用音频流 ===
1. 320K - 320000 bps
2. 128K - 128000 bps
```

**响应示例** (q=auto时包含完整流地址):
```
=== 视频信息 ===
标题: 【标题】视频标题
封面: https://i0.hdslb.com/bfs/archive/cover.jpg
时长: 5分00秒

=== 视频流详情 ===
1. 高清 1080P (1920x1080, 30fps)
   带宽: 2000000 bps
   编码: avc1.640028
   流地址: https://upos-sz-mirror08c.bilivideo.com/...

=== 音频流详情 ===
1. 320K
   带宽: 320000 bps
   编码: mp4a.40.2
   流地址: https://upos-sz-mirror08c.bilivideo.com/...
```
```

#### 3. 获取视频质量选项

**接口**: `GET /api/video/quality`

**参数**:
- `url` (必需): B站视频URL

**请求示例**:
```
GET /api/video/quality?url=https://www.bilibili.com/video/BV1xx411c7mD
```

#### 4. 智能下载视频

**接口**: `GET /api/video/download`

**描述**: 使用智能合并策略下载视频，自动检测FFmpeg并选择最佳合并方案

**智能合并特性**:
- 🔍 **自动检测**: 系统自动检测FFmpeg是否可用
- ⚡ **优先选择**: FFmpeg可用时优先使用，获得最佳合并效果
- 🛡️ **智能降级**: FFmpeg不可用时自动切换到原生Python合并
- 📊 **状态反馈**: 通过API响应了解当前使用的合并方法

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
```
✅ 下载任务已启动
任务ID: 12345678-1234-1234-1234-123456789abc
状态: 已启动

您可以通过以下链接查看下载状态:
/api/download/status/12345678-1234-1234-1234-123456789abc
```

**重复请求响应** (HTTP 409):
```
⚠️ 下载任务冲突
错误: 当前解析已经存在，请勿重复请求
现有任务ID: existing-12345678-1234-1234-1234-123456789abc
现有任务状态: 下载中

请查看现有任务状态:
/api/download/status/existing-12345678-1234-1234-1234-123456789abc
```

#### 5. 查询下载状态

**接口**: `GET /api/download/status/<task_id>`

**描述**: 查询下载任务状态，包含智能合并方法的实时反馈

**状态信息包含**:
- 📊 **任务进度**: 实时下载进度百分比
- 🔧 **合并方法**: 显示当前使用的合并方案（FFmpeg/原生方法）
- 📁 **文件信息**: 完成后提供文件路径和下载链接
- ⚠️ **错误信息**: 失败时提供详细错误描述

**响应示例** (下载完成):
```
📋 下载任务状态
任务ID: 12345678-1234-1234-1234-123456789abc
状态: ✅ 已完成
进度: 100%
消息: 视频下载和合并完成
文件路径: /downloads/视频标题.mp4

下载文件链接:
/api/download/file/12345678-1234-1234-1234-123456789abc
```

**响应示例** (下载中):
```
📋 下载任务状态
任务ID: 12345678-1234-1234-1234-123456789abc
状态: ⏳ 下载中
进度: 65%
消息: 正在下载视频流...
```

**响应示例** (下载失败):
```
📋 下载任务状态
任务ID: 12345678-1234-1234-1234-123456789abc
状态: ❌ 失败
进度: 0%
消息: 网络连接超时
```

#### 6. 查看任务列表

**接口**: `GET /api/tasks`

**描述**: 查看所有下载任务的状态列表，包含智能合并方法信息

**列表功能**:
- 📋 **任务概览**: 显示所有任务的当前状态
- 🔧 **合并信息**: 已完成任务显示使用的合并方法
- 📊 **统计数据**: 提供任务总数和各状态统计
- 🔗 **快速访问**: 直接链接到任务详情和文件下载

**响应示例**:
```
📋 下载任务列表

🔄 进行中的任务:
1. [⏳ 下载中] 视频标题1 (65%)
   任务ID: 12345678-1234-1234-1234-123456789abc
   
🎯 已完成的任务:
2. [✅ 已完成] 视频标题2
   任务ID: 87654321-4321-4321-4321-cba987654321
   文件: /downloads/视频标题2.mp4
   
3. [✅ 已完成] 视频标题3
   任务ID: fedcba98-7654-3210-fedc-ba9876543210
   文件: /downloads/视频标题3.mp4
   
❌ 失败的任务:
4. [❌ 失败] 视频标题4
   任务ID: abcdef12-3456-7890-abcd-ef1234567890
   错误: 网络连接超时

使用说明:
- 点击任务ID可查看详细状态
- 已完成的任务可直接下载文件
- 合并方法信息帮助了解使用的技术方案
- 总计: 4个任务 (1个进行中, 2个已完成, 1个失败)
```

#### 7. 下载文件

**接口**: `GET /api/download/file/<task_id>`

**描述**: 下载已完成的视频文件

## 使用示例

### Python示例

```python
import requests
import re

# 获取API信息
response = requests.get('http://localhost:8000/')
print(response.text)

# 获取视频基本信息
response = requests.get('http://localhost:8000/api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD')
print(response.text)

# 获取视频完整流信息
response = requests.get('http://localhost:8000/api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD&q=auto')
print(response.text)

# 智能下载视频 (自动选择最佳合并方案)
response = requests.get('http://localhost:8000/api/video/download?url=https://www.bilibili.com/video/BV1xx411c7mD&merge=true&filename=my_video')
print(response.text)

# 从响应文本中提取任务ID
task_id_match = re.search(r'任务ID: ([a-f0-9-]+)', response.text)
if task_id_match:
    task_id = task_id_match.group(1)
    
    # 查询下载状态 (包含合并方法信息)
    status_response = requests.get(f'http://localhost:8000/api/download/status/{task_id}')
    print(status_response.text)
    
    # 查看所有任务
    tasks_response = requests.get('http://localhost:8000/api/tasks')
    print(tasks_response.text)
```

### JavaScript示例

```javascript
// 获取API信息
fetch('http://localhost:8000/')
  .then(response => response.text())
  .then(data => console.log(data));

// 获取视频信息
fetch('http://localhost:8000/api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD')
  .then(response => response.text())
  .then(data => console.log(data));

// 智能下载视频 (自动检测FFmpeg并选择最佳合并方案)
fetch('http://localhost:8000/api/video/download?url=https://www.bilibili.com/video/BV1xx411c7mD&merge=true')
  .then(response => response.text())
  .then(data => {
    console.log(data);
    // 响应包含任务ID和智能合并状态信息
  });

// 获取完整流信息
fetch('http://localhost:8000/api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mD&q=auto')
  .then(response => response.text())
  .then(data => console.log(data));

// 下载视频
fetch('http://localhost:8000/api/video/download?url=https://www.bilibili.com/video/BV1xx411c7mD&merge=true&filename=my_video')
  .then(response => response.text())
  .then(data => {
    console.log(data);
    
    // 从响应文本中提取任务ID
    const taskIdMatch = data.match(/任务ID: ([a-f0-9-]+)/);
    if (taskIdMatch) {
      const taskId = taskIdMatch[1];
      
      // 查询下载状态
      fetch(`http://localhost:8000/api/download/status/${taskId}`)
        .then(response => response.text())
        .then(statusData => console.log(statusData));
        
      // 查看所有任务
      fetch('http://localhost:8000/api/tasks')
        .then(response => response.text())
        .then(tasksData => console.log(tasksData));
    }
  });
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
├── fastapi_app.py      # FastAPI应用主文件
├── bilibili.py         # B站视频处理核心模块
├── requirements.txt    # Python依赖包
├── cookies.txt         # Cookie配置文件 (需自行创建)
├── downloads/          # 下载文件存储目录
├── README.md           # 项目说明文档
└── venv/              # Python虚拟环境
```

## 注意事项

1. **Cookie配置**: 如需访问会员视频或高质量视频，请配置有效的B站Cookie
2. **智能合并**: 系统会自动检测FFmpeg，推荐安装以获得最佳合并效果，但不安装也能正常工作
3. **网络环境**: 确保网络环境可以正常访问B站
4. **使用限制**: 请遵守B站的使用条款，仅用于个人学习和研究
5. **q=auto参数**: 使用此参数可获取完整的流地址信息，但请注意流地址可能有时效性
6. **合并状态**: 可通过API响应消息了解当前使用的合并方法（FFmpeg/原生）

## 开发环境

- Python 3.13
- FastAPI 0.104.1
- Windows 10/11
- Linux

## 许可证

本项目仅供学习和研究使用，请遵守相关法律法规和平台使用条款。

## 更新日志

### v2.1.0
- 🧠 **新增智能合并功能**：自动检测FFmpeg可用性
- 🔄 **智能切换策略**：FFmpeg不可用时自动使用原生合并方法
- 🛡️ **增强兼容性**：无需手动安装FFmpeg也能正常合并视频
- 📊 **合并状态反馈**：显示当前使用的合并方法（FFmpeg/原生）
- 🔧 优化所有下载函数，统一使用智能合并策略

### v2.0.0
- 🔄 **重大变更**: 所有API接口响应格式从JSON改为纯文本格式
- 📝 优化文本输出格式，添加状态图标和分类展示
- 🌐 改进浏览器直接访问体验，无需JSON解析
- 🛠️ 保持所有功能逻辑不变，仅改变输出格式
- 📋 新增任务列表接口 `/api/tasks`
- 🔧 优化错误处理器，提供更友好的文本错误信息
- 🔒 修复封面URL协议转换，确保HTTPS安全访问

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
