from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import tempfile
import threading
import uuid
from datetime import datetime
import time
import subprocess
from collections import OrderedDict
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import asyncio
import threading
from bilibili import (
    get_playinfo_from_bilibili,
    extract_video_info,
    download_only_bilibili_video,
    download_and_merge_bilibili_video,
    load_cookies_from_file,
    get_video_quality_options,
    select_quality_and_download,
    get_video_title_and_cover,
    get_quality_name,
    get_audio_quality_name,
    check_ffmpeg_available
)

app = FastAPI(
    title="哔哩哔哩视频下载API",
    description="""## 🎬 哔哩哔哩视频下载服务
    
### 📖 功能介绍
- 🔍 获取B站视频详细信息
- 📊 查看可用的视频质量选项
- ⬇️ 下载视频和音频文件
- 🔄 支持视频音频合并
- 📋 任务状态实时查询
- 📁 文件管理和下载

### 🚀 快速开始
1. 使用 `/api/video/info` 获取视频信息
2. 通过 `/api/video/quality` 查看可用质量
3. 调用 `/api/video/download` 开始下载
4. 使用 `/api/download/status/{task_id}` 查询进度

### 💡 提示
- 所有接口均返回纯文本格式，便于阅读
- 支持自动合并视频音频文件
- 下载的文件保存在 `downloads` 目录
    """,
    version="2.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_tags=[
        {
            "name": "视频信息",
            "description": "获取B站视频的详细信息和质量选项"
        },
        {
            "name": "下载管理",
            "description": "视频下载、状态查询和文件管理"
        },
        {
            "name": "任务管理",
            "description": "查看和管理所有下载任务"
        }
    ]
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API控制台页面
@app.get("/api", response_class=FileResponse, include_in_schema=False)
async def api_console():
    """返回API控制台HTML页面"""
    return FileResponse("api_console.html", media_type="text/html")

# 全局变量存储下载任务状态
download_tasks = {}

# 配置
DOWNLOAD_DIR = "downloads"
COOKIE_FILE = "cookies.txt"

# 线程池配置
MAX_CONCURRENT_DOWNLOADS = 5  # 最大并发下载数
thread_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS, thread_name_prefix="download")

# 线程安全锁
task_lock = threading.Lock()

# 确保下载目录存在
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 检查FFmpeg是否可用
def check_ffmpeg_on_startup():
    """在应用启动时检查FFmpeg是否可用"""
    if not check_ffmpeg_available():
        print("\n❌ 错误：未检测到FFmpeg！")
        print("📋 FFmpeg是视频合并的必需工具，请按以下步骤安装：")
        print("\n🔧 Windows安装方法：")
        print("   1. 访问 https://ffmpeg.org/download.html")
        print("   2. 下载Windows版本的FFmpeg")
        print("   3. 解压到任意目录（如 C:\\ffmpeg）")
        print("   4. 将FFmpeg的bin目录添加到系统PATH环境变量中")
        print("   5. 重启命令行或IDE，重新运行程序")
        print("\n🔧 Windows包管理器安装：")
        print("   - 使用Chocolatey: choco install ffmpeg")
        print("   - 使用Scoop: scoop install ffmpeg")
        print("\n🐧 Linux安装方法：")
        print("   - Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg")
        print("   - CentOS/RHEL: sudo yum install ffmpeg 或 sudo dnf install ffmpeg")
        print("   - Arch Linux: sudo pacman -S ffmpeg")
        print("   - Fedora: sudo dnf install ffmpeg")
        print("\n🍎 macOS安装方法：")
        print("   - 使用Homebrew: brew install ffmpeg")
        print("   - 使用MacPorts: sudo port install ffmpeg")
        print("\n⚠️  应用将停止运行，请安装FFmpeg后重试。")
        sys.exit(1)
    else:
        print("✅ FFmpeg检测成功，应用正常启动")

# 在应用启动时检查FFmpeg
check_ffmpeg_on_startup()

def safe_delete_file(file_path, max_retries=3, delay=1):
    """安全删除文件，包含重试机制"""
    for attempt in range(max_retries):
        try:
            if os.path.exists(file_path):
                # 添加延迟，等待文件句柄释放
                time.sleep(delay)
                os.remove(file_path)
                print(f"成功删除文件: {file_path}", flush=True)
                return True
        except PermissionError as e:
            print(f"删除文件失败 (尝试 {attempt + 1}/{max_retries}): {e}", flush=True)
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))  # 递增延迟
        except Exception as e:
            print(f"删除文件时发生错误: {e}", flush=True)
            break
    return False

def update_task_status(task_id: str, **kwargs):
    """线程安全地更新任务状态"""
    with task_lock:
        if task_id in download_tasks:
            for key, value in kwargs.items():
                download_tasks[task_id][key] = value

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """线程安全地获取任务状态"""
    with task_lock:
        return download_tasks.get(task_id, None).copy() if task_id in download_tasks else None

def create_task(task_id: str, task_data: Dict[str, Any]):
    """线程安全地创建任务"""
    with task_lock:
        download_tasks[task_id] = task_data

def load_cookies():
    """加载cookies"""
    try:
        return load_cookies_from_file(COOKIE_FILE)
    except Exception as e:
        print(f"加载cookies失败: {e}")
        return None

@app.get("/", tags=["视频信息"], summary="API服务信息")
async def index():
    """获取API服务的基本信息和使用说明
    
    返回包含所有可用接口、使用方法和示例的详细文本信息。
    """
    text_result = """B站视频下载API服务
版本: 2.1.0 (FastAPI)
作者: 苏晓晴
日期: 2025-09-08

可用接口:
  GET  /                           - 获取API信息
  GET  /api/video/info             - 获取视频信息 (支持 &q=auto 参数获取全部视频和音频流)
  GET  /api/video/quality          - 获取视频质量选项
  GET  /api/video/download         - 下载视频
  GET  /api/download/status/<id>   - 查询下载状态
  GET  /api/download/file/<id>     - 下载文件
  GET  /api/download/merge/<id>    - 合并下载视频音频
  GET  /api/tasks                  - 获取所有任务

参数说明:
  url           - B站视频URL (必需)
  merge         - 是否合并视频音频 (可选，默认true)
  filename      - 自定义文件名 (可选)
  video_quality - 视频质量索引 (可选，默认0-最高质量)
  audio_quality - 音频质量索引 (可选，默认0-最高质量)
  q             - 设置为'auto'获取全部流信息 (可选)

使用示例:
  获取视频信息: /api/video/info?url=https://www.bilibili.com/video/BV1xx411c7mu
  下载视频:     /api/video/download?url=https://www.bilibili.com/video/BV1xx411c7mu&merge=true
  查询下载状态: /api/download/status/task_id_here

服务运行在 http://localhost:8000
API调试在 http://localhost:8000/api
"""
    
    return PlainTextResponse(text_result)

@app.get("/api/video/info", tags=["视频信息"], summary="获取视频详细信息")
async def get_video_info(url: str, q: Optional[str] = None, stream_type: Optional[str] = "all"):
    """获取B站视频的详细信息
    
    Args:
        url: B站视频链接 (支持BV号、av号等格式)
        q: 视频质量参数 (设置为'auto'获取全部流信息)
        stream_type: 流类型选择 ('video'=仅视频流, 'audio'=仅音频流, 'all'=全部流，默认为'all')
    
    Returns:
        包含视频标题、时长、封面、可用质量等详细信息的文本格式数据
    """
    if not url:
        return PlainTextResponse("错误: 缺少必要参数 url", status_code=400)
    
    try:
        # 获取q参数，用于控制返回的流信息
        q_param = q.lower() if q else ''
        
        cookies = load_cookies()
        
        # 获取视频信息
        playinfo = get_playinfo_from_bilibili(url, cookies)
        if not playinfo:
            return PlainTextResponse("错误: 获取视频信息失败，请检查URL或cookie", status_code=400)
        
        video_info = extract_video_info(playinfo, url, cookies)
        if not video_info:
            return PlainTextResponse("错误: 解析视频信息失败", status_code=400)
        
        # 获取视频标题和封面
        title_cover_info = get_video_title_and_cover(url, cookies)
        if title_cover_info:
            video_info.update(title_cover_info)
        
        # 根据stream_type参数决定处理哪些流
        stream_type_param = stream_type.lower() if stream_type else 'all'
        
        # 根据q参数决定返回的流信息
        video_streams = []
        audio_streams = []
        
        # 处理视频流（当stream_type为'video'或'all'时）
        if stream_type_param in ['video', 'all']:
            for video in video_info.get('video_urls', []):
                quality_id = video.get('quality', 0)
                stream_data = {
                    'quality_id': quality_id,
                    'quality_name': get_quality_name(quality_id),
                    'width': video.get('width', 0),
                    'height': video.get('height', 0),
                    'bandwidth': video.get('bandwidth', 0),
                    'frame_rate': video.get('frameRate', 0),
                    'codecs': video.get('codecs', '')
                }
                # 如果q=auto，添加流地址
                if q_param == 'auto':
                    stream_data['url'] = video.get('url', '')
                video_streams.append(stream_data)
            # 按质量ID降序排序（高质量在前）
            video_streams.sort(key=lambda x: x['quality_id'], reverse=True)
        
        # 处理音频流（当stream_type为'audio'或'all'时）
        if stream_type_param in ['audio', 'all']:
            for audio in video_info.get('audio_urls', []):
                quality_id = audio.get('quality', 0)
                stream_data = {
                    'quality_id': quality_id,
                    'quality_name': get_audio_quality_name(quality_id),
                    'bandwidth': audio.get('bandwidth', 0),
                    'codecs': audio.get('codecs', '')
                }
                # 如果q=auto，添加流地址
                if q_param == 'auto':
                    stream_data['url'] = audio.get('url', '')
                audio_streams.append(stream_data)
            # 按质量ID降序排序（高质量在前）
            audio_streams.sort(key=lambda x: x['quality_id'], reverse=True)
        
        # 处理最高质量视频和音频的中文名称
        highest_video = video_info.get('highest_video_url')
        highest_audio = video_info.get('highest_audio_url')
        
        if highest_video:
            highest_video = dict(highest_video)
            highest_video['quality_name'] = get_quality_name(highest_video.get('quality', 0))
        
        if highest_audio:
            highest_audio = dict(highest_audio)
            highest_audio['quality_name'] = get_audio_quality_name(highest_audio.get('quality', 0))
        
        # 构建文本格式返回数据
        # 将封面URL转换为https
        cover_url = video_info.get('cover', '无')
        if cover_url != '无' and cover_url.startswith('http://'):
            cover_url = cover_url.replace('http://', 'https://')
        
        text_result = f"""视频信息获取成功

基本信息:
  标题: {video_info.get('title', '未知')}
  封面: {cover_url}
  时长: {video_info.get('duration', 0)} 秒
  视频URL: {url}

最高质量流:"""
        
        # 根据stream_type参数显示最高质量流信息
        if stream_type_param in ['video', 'all'] and highest_video:
            text_result += f"\n  视频: {get_quality_name(highest_video.get('quality', 0))} ({highest_video.get('width', 0)}x{highest_video.get('height', 0)} @ {highest_video.get('frameRate', 0)}fps)"
        elif stream_type_param == 'video':
            text_result += "\n  视频: 无"
            
        if stream_type_param in ['audio', 'all'] and highest_audio:
            text_result += f"\n  音频: {get_audio_quality_name(highest_audio.get('quality', 0))}"
        elif stream_type_param == 'audio':
            text_result += "\n  音频: 无"
        
        # 显示视频流信息（仅当stream_type为'video'或'all'时）
        if stream_type_param in ['video', 'all'] and video_streams:
            text_result += f"\n\n可用视频流 ({len(video_streams)} 个):"
            for i, stream in enumerate(video_streams, 1):
                text_result += f"\n  {i}. {stream['quality_name']} - {stream['width']}x{stream['height']} @ {stream['frame_rate']}fps"
                text_result += f" (编码: {stream['codecs']}, 带宽: {stream['bandwidth']})"
                if q_param == 'auto' and stream.get('url'):
                    text_result += f"\n     URL: {stream['url']}"
        
        # 显示音频流信息（仅当stream_type为'audio'或'all'时）
        if stream_type_param in ['audio', 'all'] and audio_streams:
            text_result += f"\n\n可用音频流 ({len(audio_streams)} 个):"
            for i, stream in enumerate(audio_streams, 1):
                text_result += f"\n  {i}. {stream['quality_name']} (编码: {stream['codecs']}, 带宽: {stream['bandwidth']})"
                if q_param == 'auto' and stream.get('url'):
                    text_result += f"\n     URL: {stream['url']}"
        
        # 添加使用提示
        if q_param != 'auto':
            text_result += "\n\n提示: 使用 &q=auto 参数可获取完整流地址信息"
        if stream_type_param == 'all':
            text_result += "\n提示: 使用 &stream_type=video 仅显示视频流，&stream_type=audio 仅显示音频流"
        
        return PlainTextResponse(text_result)
        
    except Exception as e:
        return PlainTextResponse(f"服务器错误: {str(e)}", status_code=500)

@app.get("/api/video/quality", tags=["视频信息"], summary="获取可用质量选项")
async def get_video_quality(url: str):
    """获取视频的所有可用质量选项
    
    Args:
        url: B站视频链接
    
    Returns:
        包含所有可用视频质量和音频质量的详细列表
    """
    if not url:
        return PlainTextResponse("错误: 缺少必要参数 url", status_code=400)
    
    try:
        # 加载cookies
        cookies = load_cookies()
        
        # 获取质量选项
        quality_options = get_video_quality_options(url, cookies)
        if not quality_options:
            return PlainTextResponse("错误: 无法获取视频质量选项，请检查URL或cookie", status_code=404)
        
        # 构建文本格式输出
        output_lines = []
        output_lines.append("视频质量选项获取成功")
        output_lines.append("")
        output_lines.append("=== 可用视频质量(video_quality_index) ===")
        
        video_options = quality_options.get('video_options', [])
        if video_options:
            for option in video_options:
                output_lines.append(f'[{option["index"]}] {option["quality_name"]} (ID: {option["quality_id"]})')
                output_lines.append(f'    分辨率: {option["width"]}x{option["height"]}')
                output_lines.append(f'    帧率: {option["frame_rate"]} fps')
                output_lines.append(f'    带宽: {option["bandwidth"]} bps')
                output_lines.append(f'    编码: {option["codecs"]}')
                output_lines.append('')
        else:
            output_lines.append('未找到可用的视频质量选项')
            output_lines.append('')
        
        # 输出音频质量选项
        output_lines.append('=== 可用音频质量(audio_quality_index) ===')
        audio_options = quality_options.get('audio_options', [])
        if audio_options:
            for option in audio_options:
                output_lines.append(f'[{option["index"]}] {option["quality_name"]} (ID: {option["quality_id"]})')
                output_lines.append(f'    带宽: {option["bandwidth"]} bps')
                output_lines.append(f'    编码: {option["codecs"]}')
                output_lines.append('')
        else:
            output_lines.append('未找到可用的音频质量选项')
            output_lines.append('')
        
        output_lines.append('=== 使用说明 ===')
        output_lines.append('下载时可使用 video_quality_index 和 audio_quality_index 参数选择对应的质量选项')
        output_lines.append('例如: /api/video/download?url=...&video_quality=0&audio_quality=0')
        
        # 返回文本响应
        text_output = '\n'.join(output_lines)
        return PlainTextResponse(text_output)
        
    except Exception as e:
        return PlainTextResponse(f'服务器错误: {str(e)}', status_code=500)


@app.get("/api/video/download", tags=["下载管理"], summary="开始下载视频")
async def download_video(
    background_tasks: BackgroundTasks,
    url: str,
    merge: bool = True,
    filename: Optional[str] = None,
    video_quality: int = 0,
    audio_quality: int = 0
):
    """开始下载B站视频
    
    Args:
        url: B站视频链接
        merge: 是否合并视频和音频 (默认为True)
        filename: 自定义文件名 (可选)
        video_quality: 视频质量索引 (默认0-最高质量)
        audio_quality: 音频质量索引 (默认0-最高质量)
    
    Returns:
        包含任务ID和下载信息的文本格式响应
    """
    if not url:
        return PlainTextResponse("错误: 缺少必要参数 url", status_code=400)
    
    try:
        # 检查是否已存在相同URL的下载任务
        for existing_task_id, task_info in download_tasks.items():
            if task_info['url'] == url and task_info['status'] in ['pending', 'downloading', 'completed']:
                text_result = f"""下载任务创建失败

错误: 当前解析已经存在，请勿重复请求
已存在任务ID: {existing_task_id}
任务状态: {task_info['status']}

请使用已存在的任务ID查询状态或下载文件。"""
                return PlainTextResponse(text_result, status_code=409)
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 加载cookies
        cookies = load_cookies()
        
        # 初始化任务状态
        task_data = {
            "id": task_id,
            "url": url,
            "status": "pending",
            "progress": 0,
            "message": "任务已创建，等待开始下载...",
            "created_at": datetime.now().isoformat(),
            "merge": merge,
            "filename": filename,
            "video_quality_index": video_quality,
            "audio_quality_index": audio_quality,
            "file_path": None,
            "video_path": None,
            "audio_path": None,
            "error": None
        }
        
        # 创建任务
        create_task(task_id, task_data)
        
        # 提交到线程池
        future = thread_pool.submit(
            download_video_task,
            task_id, url, cookies, merge, filename, video_quality, audio_quality
        )
        
        text_result = f"""下载任务创建成功

任务ID: {task_id}
视频URL: {url}
合并模式: {'是' if merge else '否'}
视频质量索引: {video_quality}
音频质量索引: {audio_quality}
自定义文件名: {filename if filename else '使用默认名称'}

任务状态: 已创建，等待开始下载...

查询状态: /api/download/status/{task_id}
下载文件: /api/download/file/{task_id}

提示: 请保存任务ID以便后续查询和下载。"""
        
        return PlainTextResponse(text_result)
    
    except Exception as e:
        return PlainTextResponse(f"服务器错误: {str(e)}", status_code=500)

def download_video_task(task_id, url, cookies, merge, filename, video_quality_index=0, audio_quality_index=0):
    """线程池中执行的下载任务"""
    try:
        # 更新任务状态
        update_task_status(task_id, status="downloading", message="正在下载视频...")
        
        def progress_callback(current, total, message):
            if total > 0:
                progress = int((current / total) * 100)
                update_task_status(task_id, progress=progress, message=message)
            else:
                update_task_status(task_id, message=message)
        
        if merge:
            # 下载并合并
            result = select_quality_and_download(
                url, cookies=cookies, output_dir=DOWNLOAD_DIR, merge=True,
                video_quality_index=video_quality_index,
                audio_quality_index=audio_quality_index,
                filename=filename,
                progress_callback=progress_callback
            )
            
            if result and isinstance(result, str):
                update_task_status(
                    task_id, 
                    status="completed", 
                    progress=100, 
                    message="下载完成", 
                    file_path=result
                )
            else:
                update_task_status(task_id, status="failed", message="下载失败")
        else:
            # 只下载，不合并
            result = select_quality_and_download(
                url, cookies=cookies, output_dir=DOWNLOAD_DIR, merge=False,
                video_quality_index=video_quality_index,
                audio_quality_index=audio_quality_index,
                filename=filename,
                progress_callback=progress_callback
            )
            
            if result and isinstance(result, tuple) and len(result) == 2:
                video_path, audio_path = result
                update_task_status(
                    task_id, 
                    status="completed", 
                    progress=100, 
                    message="下载完成", 
                    video_path=video_path, 
                    audio_path=audio_path
                )
            else:
                update_task_status(task_id, status="failed", message="下载失败")
    
    except Exception as e:
        print(f"下载任务执行失败: {e}")
        update_task_status(
            task_id, 
            status="failed", 
            message=f"下载失败: {str(e)}", 
            error=str(e)
        )

@app.get("/api/download/status/{task_id}", tags=["下载管理"], summary="查询下载状态")
async def get_download_status(task_id: str):
    """查询指定任务的下载状态和进度
    
    Args:
        task_id: 下载任务的唯一标识符
    
    Returns:
        包含任务状态、进度、文件信息等的详细文本
    """
    task = get_task_status(task_id)
    if not task:
        return PlainTextResponse("错误: 任务不存在", status_code=404)
    
    # 状态图标映射
    status_icons = {
        'pending': '⏳',
        'downloading': '⬇️',
        'completed': '✅',
        'failed': '❌'
    }
    
    status_icon = status_icons.get(task['status'], '❓')
    
    # 格式化创建时间
    try:
        created_time = datetime.fromisoformat(task['created_at'].replace('T', ' ').split('.')[0])
        formatted_time = created_time.strftime('%Y-%m-%d %H:%M:%S')
    except:
        formatted_time = task['created_at']
    
    text_result = f"""下载任务状态查询

任务ID: {task_id}
状态: {status_icon} {task['status'].upper()}
进度: {task['progress']}%
消息: {task['message']}
创建时间: {formatted_time}

任务详情:
  视频URL: {task['url']}
  合并模式: {'是' if task['merge'] else '否'}
  视频质量索引: {task['video_quality_index']}
  音频质量索引: {task['audio_quality_index']}
  自定义文件名: {task['filename'] if task['filename'] else '使用默认名称'}"""
    
    # 添加文件路径信息
    if task['status'] == 'completed':
        if task['merge'] and task.get('file_path'):
            text_result += f"\n\n文件信息:\n  合并文件: {task['file_path']}"
            text_result += f"\n\n下载链接: /api/download/file/{task_id}"
        elif not task['merge'] and task.get('video_path') and task.get('audio_path'):
            text_result += f"\n\n文件信息:\n  视频文件: {task['video_path']}\n  音频文件: {task['audio_path']}"
            text_result += f"\n\n下载链接:\n  视频: /api/download/file/{task_id}\n  合并: /api/download/merge/{task_id}"
    
    # 添加错误信息
    if task['status'] == 'failed' and task.get('error'):
        text_result += f"\n\n错误信息: {task['error']}"
    
    return PlainTextResponse(text_result)

@app.get("/api/download/file/{task_id}", tags=["下载管理"], summary="下载已完成的文件")
async def download_file(task_id: str):
    """下载已完成任务的文件
    
    Args:
        task_id: 下载任务的唯一标识符
    
    Returns:
        文件流响应，浏览器将自动下载文件
    """
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    # 检查是否是合并的文件
    if task["merge"] and task.get("file_path"):
        file_path = task["file_path"]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        filename = os.path.basename(file_path)
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
    
    # 如果是分离的文件，返回视频文件
    elif not task["merge"] and task.get("video_path"):
        video_path = task["video_path"]
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="视频文件不存在")
        
        filename = os.path.basename(video_path)
        return FileResponse(
            path=video_path,
            filename=filename,
            media_type='application/octet-stream'
        )
    
    else:
        raise HTTPException(status_code=404, detail="文件不存在")

@app.get("/api/download/merge/{task_id}", tags=["下载管理"], summary="合并视频和音频")
async def download_merged_file(task_id: str):
    """合并指定任务的视频和音频文件
    
    Args:
        task_id: 下载任务的唯一标识符
    
    Returns:
        合并后的视频文件流响应
    """
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    if task["merge"]:
        raise HTTPException(status_code=400, detail="该任务已经是合并文件")
    
    video_path = task.get("video_path")
    audio_path = task.get("audio_path")
    
    if not video_path or not audio_path:
        raise HTTPException(status_code=400, detail="缺少视频或音频文件")
    
    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="视频或音频文件不存在")
    
    try:
        # 生成合并后的文件名
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        if base_name.endswith('_video'):
            base_name = base_name[:-6]  # 移除 '_video' 后缀
        
        merged_filename = f"{base_name}_merged.mp4"
        merged_path = os.path.join(DOWNLOAD_DIR, merged_filename)
        
        # 检查是否已经存在合并文件
        if os.path.exists(merged_path):
            return FileResponse(
                path=merged_path,
                filename=merged_filename,
                media_type='video/mp4'
            )
        
        # 使用ffmpeg合并视频和音频
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-y',  # 覆盖输出文件
            merged_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(merged_path):
            # 合并成功，返回文件
            return FileResponse(
                path=merged_path,
                filename=merged_filename,
                media_type='video/mp4'
            )
        else:
            print(f"FFmpeg合并失败: {result.stderr}")
            raise HTTPException(status_code=500, detail="视频合并失败")
    
    except Exception as e:
        print(f"合并文件时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"合并失败: {str(e)}")

@app.get("/api/tasks", tags=["任务管理"], summary="获取所有下载任务")
async def get_all_tasks():
    """获取所有下载任务的详细列表
    
    Returns:
        包含所有任务状态、进度、创建时间等信息的格式化文本列表
    """
    if not download_tasks:
        return PlainTextResponse('当前没有任何下载任务')
    
    # 状态图标映射
    status_icons = {
        'pending': '⏳',
        'downloading': '⬇️',
        'completed': '✅',
        'failed': '❌'
    }
    
    # 线程安全地获取所有任务
    with task_lock:
        tasks_copy = download_tasks.copy()
    
    text_result = f"下载任务列表 (共 {len(tasks_copy)} 个任务)\n\n"
    
    # 按创建时间排序任务
    sorted_tasks = sorted(tasks_copy.items(), key=lambda x: x[1]['created_at'], reverse=True)
    
    for i, (task_id, task) in enumerate(sorted_tasks, 1):
        status_icon = status_icons.get(task['status'], '❓')
        
        text_result += f"{i}. 任务ID: {task_id}\n"
        text_result += f"   状态: {status_icon} {task['status'].upper()}\n"
        text_result += f"   进度: {task['progress']}%\n"
        text_result += f"   消息: {task['message']}\n"
        # created_at 是 ISO 格式字符串，需要解析后格式化
        try:
            created_time = datetime.fromisoformat(task['created_at'].replace('T', ' ').split('.')[0])
            formatted_time = created_time.strftime('%Y-%m-%d %H:%M:%S')
        except:
            formatted_time = task['created_at']  # 如果解析失败，直接使用原字符串
        text_result += f"   创建时间: {formatted_time}\n"
        text_result += f"   视频URL: {task['url'][:50]}{'...' if len(task['url']) > 50 else ''}\n"
        text_result += f"   合并模式: {'是' if task['merge'] else '否'}\n"
        
        # 添加文件信息
        if task['status'] == 'completed':
            if task['merge'] and task.get('file_path'):
                filename = os.path.basename(task['file_path'])
                text_result += f"   文件: {filename}\n"
            elif not task['merge'] and task.get('video_path'):
                video_filename = os.path.basename(task['video_path'])
                text_result += f"   视频文件: {video_filename}\n"
        
        text_result += "\n"  # 任务间空行
    
    text_result += "=== 操作说明 ===\n"
    text_result += "查询任务状态: /api/download/status/<task_id>\n"
    text_result += "下载文件: /api/download/file/<task_id>\n"
    text_result += "合并文件: /api/download/merge/<task_id>\n"
    
    return PlainTextResponse(text_result)

@app.exception_handler(404)
async def not_found_handler(request, exc):
    text_result = """❌ 404 - 接口不存在

请求的接口路径不存在，请检查URL是否正确。

可用接口列表:
  GET  /                           - 获取API信息
  GET  /api/video/info             - 获取视频信息
  GET  /api/video/quality          - 获取视频质量选项
  GET  /api/video/download         - 下载视频
  GET  /api/download/status/<id>   - 查询下载状态
  GET  /api/download/file/<id>     - 下载文件
  GET  /api/download/merge/<id>    - 合并下载视频音频
  GET  /api/tasks                  - 获取所有任务

如需帮助，请访问首页获取详细API文档。"""
    return PlainTextResponse(text_result, status_code=404)

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    text_result = """❌ 500 - 服务器内部错误

服务器遇到了一个意外的情况，无法完成请求。

可能的解决方案:
1. 请稍后重试
2. 检查请求参数是否正确
3. 如果问题持续存在，请联系管理员

如需帮助，请访问首页获取API使用说明。"""
    return PlainTextResponse(text_result, status_code=500)

if __name__ == "__main__":
    import uvicorn
    print("B站视频下载API服务启动中... (FastAPI版本)")
    print("API文档:")
    print("  GET  /                           - 获取API信息")
    print("  GET  /api/video/info             - 获取视频信息 (支持 &q=auto 参数获取全部视频和音频流)")
    print("  GET  /api/video/quality          - 获取视频质量选项")
    print("  GET  /api/video/download         - 下载视频")
    print("  GET  /api/download/status/<id>   - 查询下载状态")
    print("  GET  /api/download/file/<id>     - 下载文件")
    print("  GET  /api/download/merge/<id>    - 合并下载视频音频")
    print("  GET  /api/tasks                  - 获取所有任务")
    print("\n服务器将在 http://localhost:8000 启动")
    

    uvicorn.run(app, host="0.0.0.0", port=8000)
