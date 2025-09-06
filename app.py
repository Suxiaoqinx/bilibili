from flask import Flask, request, jsonify, send_file, after_this_request, Response
from flask_cors import CORS
import os
import tempfile
import threading
import uuid
from datetime import datetime
import json
import time
import subprocess
from collections import OrderedDict
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
    get_audio_quality_name
)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置JSON响应格式
app.config['JSON_AS_ASCII'] = False  # 支持中文字符
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True  # 格式化JSON输出

# 全局变量存储下载任务状态
download_tasks = {}

# 配置
DOWNLOAD_DIR = "downloads"
COOKIE_FILE = "cookies.txt"

# 确保下载目录存在
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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
            else:
                print(f"最终删除失败: {file_path}", flush=True)
                return False
        except Exception as e:
            print(f"删除文件时出现其他错误: {e}", flush=True)
            return False
    return False

def load_cookies():
    """加载cookie文件"""
    if os.path.exists(COOKIE_FILE):
        return load_cookies_from_file(COOKIE_FILE)
    return None

@app.route('/', methods=['GET'])
def index():
    """API首页 - 返回文本格式"""
    text_result = """B站视频下载API服务
版本: 2.0.0

可用接口:
  GET  /                           - 获取API信息
  GET  /api/video/info             - 获取视频信息 (支持 &q=auto 参数获取全部视频和音频流)
  GET  /api/video/quality          - 获取视频质量选项
  GET  /api/video/download         - 下载视频
  GET  /api/download/status/<id>   - 查询下载状态
  GET  /api/download/file/<id>     - 下载文件
  GET  /api/download/merge/<id>    - 合并下载视频音频
  GET  /api/tasks                  - 获取所有任务

使用说明:
1. 所有接口均支持GET请求
2. 参数通过URL查询字符串传递
3. 返回数据为文本格式
4. 服务运行在 http://localhost:5000"""
    
    return Response(text_result, mimetype='text/plain; charset=utf-8')
@app.route('/api/video/info', methods=['GET'])
def get_video_info():
    """获取视频信息API - 返回文本格式"""
    try:
        # 从URL参数获取视频链接
        url = request.args.get('url')
        if not url:
            return Response('错误: 缺少必要参数 url', mimetype='text/plain; charset=utf-8', status=400)
        
        # 获取q参数，用于控制返回的流信息
        q_param = request.args.get('q', '').lower()
        
        cookies = load_cookies()
        
        # 获取视频信息
        playinfo = get_playinfo_from_bilibili(url, cookies)
        if not playinfo:
            return Response('错误: 获取视频信息失败，请检查URL或cookie', mimetype='text/plain; charset=utf-8', status=400)
        
        video_info = extract_video_info(playinfo, url, cookies)
        if not video_info:
            return Response('错误: 解析视频信息失败', mimetype='text/plain; charset=utf-8', status=400)
        
        # 根据q参数决定返回的流信息
        if q_param == 'auto':
            # q=auto时，返回所有可用的视频和音频流
            video_streams = []
            for video in video_info.get('video_urls', []):
                quality_id = video.get('quality', 0)
                video_streams.append({
                    'quality_id': quality_id,
                    'quality_name': get_quality_name(quality_id),
                    'width': video.get('width', 0),
                    'height': video.get('height', 0),
                    'bandwidth': video.get('bandwidth', 0),
                    'frame_rate': video.get('frameRate', 0),
                    'codecs': video.get('codecs', ''),
                    'url': video.get('url', '')  # 添加流地址
                })
            # 按质量ID降序排序（高质量在前）
            video_streams.sort(key=lambda x: x['quality_id'], reverse=True)
            
            # 处理音频流信息并按质量排序
            audio_streams = []
            for audio in video_info.get('audio_urls', []):
                quality_id = audio.get('quality', 0)
                audio_streams.append({
                    'quality_id': quality_id,
                    'quality_name': get_audio_quality_name(quality_id),
                    'bandwidth': audio.get('bandwidth', 0),
                    'codecs': audio.get('codecs', ''),
                    'url': audio.get('url', '')  # 添加流地址
                })
            # 按质量ID降序排序（高质量在前）
            audio_streams.sort(key=lambda x: x['quality_id'], reverse=True)
        else:
            # 默认情况，返回基本流信息（不包含URL）
            video_streams = []
            for video in video_info.get('video_urls', []):
                quality_id = video.get('quality', 0)
                video_streams.append({
                    'quality_id': quality_id,
                    'quality_name': get_quality_name(quality_id),
                    'width': video.get('width', 0),
                    'height': video.get('height', 0),
                    'bandwidth': video.get('bandwidth', 0),
                    'frame_rate': video.get('frameRate', 0),
                    'codecs': video.get('codecs', '')
                })
            # 按质量ID降序排序（高质量在前）
            video_streams.sort(key=lambda x: x['quality_id'], reverse=True)
            
            # 处理音频流信息并按质量排序
            audio_streams = []
            for audio in video_info.get('audio_urls', []):
                quality_id = audio.get('quality', 0)
                audio_streams.append({
                    'quality_id': quality_id,
                    'quality_name': get_audio_quality_name(quality_id),
                    'bandwidth': audio.get('bandwidth', 0),
                    'codecs': audio.get('codecs', '')
                })
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

最高质量流:
  视频: {get_quality_name(highest_video.get('quality', 0)) if highest_video else '无'} ({highest_video.get('width', 0)}x{highest_video.get('height', 0)} @ {highest_video.get('frameRate', 0)}fps)
  音频: {get_audio_quality_name(highest_audio.get('quality', 0)) if highest_audio else '无'}

可用视频流 ({len(video_streams)} 个):"""
        
        for i, stream in enumerate(video_streams, 1):
            text_result += f"\n  {i}. {stream['quality_name']} - {stream['width']}x{stream['height']} @ {stream['frame_rate']}fps"
            text_result += f" (编码: {stream['codecs']}, 带宽: {stream['bandwidth']})"
            if q_param == 'auto' and stream.get('url'):
                text_result += f"\n     URL: {stream['url']}"
        
        text_result += f"\n\n可用音频流 ({len(audio_streams)} 个):"
        for i, stream in enumerate(audio_streams, 1):
            text_result += f"\n  {i}. {stream['quality_name']} (编码: {stream['codecs']}, 带宽: {stream['bandwidth']})"
            if q_param == 'auto' and stream.get('url'):
                text_result += f"\n     URL: {stream['url']}"
        
        if q_param != 'auto':
            text_result += "\n\n提示: 使用 &q=auto 参数可获取完整流地址信息"
        
        return Response(text_result, mimetype='text/plain; charset=utf-8')
        
    except Exception as e:
        return Response(f'服务器错误: {str(e)}', mimetype='text/plain; charset=utf-8', status=500)


@app.route('/api/video/quality', methods=['GET'])
def get_video_quality():
    """获取视频质量选项API（文本格式输出）"""
    try:
        url = request.args.get('url')
        if not url:
            return Response('错误: 缺少必要参数 url\n', mimetype='text/plain; charset=utf-8'), 400
        
        cookies_param = request.args.get('cookies')
        cookies = cookies_param if cookies_param else load_cookies()
        
        # 获取视频质量选项
        quality_options = get_video_quality_options(url, cookies)
        if not quality_options:
            return Response('错误: 获取视频质量选项失败，请检查URL或cookie\n', mimetype='text/plain; charset=utf-8'), 400
        
        # 构建文本输出
        output_lines = []
        output_lines.append('=== B站视频质量选项 ===')
        output_lines.append(f'视频URL: {url}')
        output_lines.append(f'视频时长: {quality_options.get("duration", 0)} 秒')
        output_lines.append('')
        
        # 输出视频质量选项
        output_lines.append('=== 可用视频质量(video_quality_index) ===')
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
        output_lines.append('例如: /api/video/download?url=...&video_quality_index=0&audio_quality_index=0')
        
        # 返回文本响应
        text_output = '\n'.join(output_lines)
        return Response(text_output, mimetype='text/plain; charset=utf-8')
        
    except Exception as e:
        return Response(f'服务器错误: {str(e)}\n', mimetype='text/plain; charset=utf-8'), 500


@app.route('/api/video/download', methods=['GET'])
def download_video():
    """下载视频API - 返回文本格式"""
    try:
        url = request.args.get('url')
        if not url:
            return Response('错误: 缺少必要参数 url', mimetype='text/plain; charset=utf-8', status=400)
        
        # 检查是否已存在相同URL的下载任务
        for existing_task_id, task_info in download_tasks.items():
            if task_info['url'] == url and task_info['status'] in ['pending', 'downloading', 'completed']:
                text_result = f"""下载任务创建失败

错误: 当前解析已经存在，请勿重复请求
已存在任务ID: {existing_task_id}
任务状态: {task_info['status']}

请使用已存在的任务ID查询状态或下载文件。"""
                return Response(text_result, mimetype='text/plain; charset=utf-8', status=409)
        
        cookies_param = request.args.get('cookies')
        cookies = cookies_param if cookies_param else load_cookies()
        merge = request.args.get('merge', 'true').lower() == 'true'  # 默认合并
        filename = request.args.get('filename')  # 可选的文件名
        video_quality_index = int(request.args.get('video_quality_index', 0))  # 视频质量索引，默认最高质量
        audio_quality_index = int(request.args.get('audio_quality_index', 0))  # 音频质量索引，默认最高质量
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务记录
        download_tasks[task_id] = {
            'id': task_id,
            'url': url,
            'status': 'pending',
            'progress': 0,
            'message': '任务已创建，等待开始下载',
            'created_at': datetime.now().isoformat(),
            'file_path': None,
            'error': None
        }
        
        # 启动后台下载任务
        thread = threading.Thread(
            target=download_video_task,
            args=(task_id, url, cookies, merge, filename, video_quality_index, audio_quality_index)
        )
        thread.daemon = True
        thread.start()
        
        text_result = f"""下载任务创建成功

任务ID: {task_id}
视频URL: {url}
合并模式: {'是' if merge else '否'}
视频质量索引: {video_quality_index}
音频质量索引: {audio_quality_index}
自定义文件名: {filename if filename else '使用默认名称'}
创建时间: {download_tasks[task_id]['created_at']}

状态: 下载任务已启动，正在后台处理

使用以下接口查询进度:
  GET /api/download/status/{task_id}

下载完成后使用以下接口获取文件:
  GET /api/download/file/{task_id}"""
        
        return Response(text_result, mimetype='text/plain; charset=utf-8')
        
    except Exception as e:
        return Response(f'服务器错误: {str(e)}', mimetype='text/plain; charset=utf-8', status=500)

def download_video_task(task_id, url, cookies, merge, filename, video_quality_index=0, audio_quality_index=0):
    """下载视频的后台任务"""
    def progress_callback(current, total, message):
        """进度回调函数"""
        progress = int((current / total) * 100) if total > 0 else 0
        download_tasks[task_id]['progress'] = progress
        download_tasks[task_id]['message'] = message
        if progress == 0 and "失败" in message:
            download_tasks[task_id]['status'] = 'failed'
            download_tasks[task_id]['error'] = message
        elif progress == 100:
            download_tasks[task_id]['status'] = 'completed'
    
    try:
        # 更新任务状态
        download_tasks[task_id]['status'] = 'downloading'
        download_tasks[task_id]['message'] = '正在初始化下载...'
        download_tasks[task_id]['progress'] = 0
        
        # 使用select_quality_and_download函数进行下载
        result = select_quality_and_download(
            url, 
            cookies, 
            DOWNLOAD_DIR, 
            merge, 
            video_quality_index, 
            audio_quality_index, 
            filename,
            progress_callback
        )
        
        if result:
            download_tasks[task_id]['status'] = 'completed'
            download_tasks[task_id]['progress'] = 100
            download_tasks[task_id]['message'] = '下载完成'
            download_tasks[task_id]['file_path'] = result
        else:
            if download_tasks[task_id]['status'] != 'failed':
                download_tasks[task_id]['status'] = 'failed'
                download_tasks[task_id]['message'] = '下载失败'
                download_tasks[task_id]['error'] = '未知错误'
                
    except Exception as e:
        download_tasks[task_id]['status'] = 'failed'
        download_tasks[task_id]['message'] = '下载失败'
        download_tasks[task_id]['error'] = str(e)

@app.route('/api/download/status/<task_id>', methods=['GET'])
def get_download_status(task_id):
    """查询下载状态API - 返回文本格式"""
    if task_id not in download_tasks:
        return Response('错误: 任务不存在', mimetype='text/plain; charset=utf-8', status=404)
    
    task = download_tasks[task_id]
    
    # 根据状态显示不同的状态图标
    status_icons = {
        'pending': '⏳',
        'downloading': '⬇️',
        'completed': '✅',
        'failed': '❌'
    }
    
    status_icon = status_icons.get(task['status'], '❓')
    
    text_result = f"""下载任务状态查询

任务ID: {task_id}
状态: {status_icon} {task['status'].upper()}
进度: {task['progress']}%
消息: {task['message']}
创建时间: {task['created_at']}"""
    
    if task.get('error'):
        text_result += f"\n错误信息: {task['error']}"
    
    if task['status'] == 'completed' and task.get('file_path'):
        text_result += f"\n\n文件已准备就绪，可以下载:"
        text_result += f"\n  GET /api/download/file/{task_id}"
    elif task['status'] == 'downloading':
        text_result += f"\n\n正在下载中，请稍后再次查询状态"
    elif task['status'] == 'failed':
        text_result += f"\n\n下载失败，请检查错误信息或重新创建下载任务"
    elif task['status'] == 'pending':
        text_result += f"\n\n任务等待中，即将开始下载"
    
    return Response(text_result, mimetype='text/plain; charset=utf-8')

@app.route('/api/download/file/<task_id>', methods=['GET'])
def download_file(task_id):
    """下载文件API"""
    if task_id not in download_tasks:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    task = download_tasks[task_id]
    if task['status'] != 'completed':
        return jsonify({
            'success': False,
            'error': '文件尚未准备好'
        }), 400
    
    file_path = task['file_path']
    if not file_path:
        return jsonify({
            'success': False,
            'error': '文件路径不存在'
        }), 400
    
    # 如果是合并的视频文件
    if isinstance(file_path, str) and os.path.exists(file_path):
        # 创建下载后清理功能
        def cleanup_after_download():
            # 使用安全删除函数
            safe_delete_file(file_path)
            # 从任务字典中删除task_id记录
            if task_id in download_tasks:
                del download_tasks[task_id]
        
        # 使用Flask的after_request装饰器在响应发送后执行清理
        
        @after_this_request
        def cleanup(response):
            cleanup_after_download()
            return response
        
        return send_file(file_path, as_attachment=True)
    
    # 如果是分离的视频和音频文件
    elif isinstance(file_path, dict):
        file_type = request.args.get('type', 'video')  # 默认返回视频文件
        target_file = None
        
        if file_type == 'audio' and 'audio' in file_path:
            if os.path.exists(file_path['audio']):
                target_file = file_path['audio']
        elif file_type == 'video' and 'video' in file_path:
            if os.path.exists(file_path['video']):
                target_file = file_path['video']
        
        if target_file:
            # 创建下载后清理功能
            def cleanup_after_download():
                # 使用安全删除函数删除所有相关文件
                if 'video' in file_path:
                    safe_delete_file(file_path['video'])
                if 'audio' in file_path:
                    safe_delete_file(file_path['audio'])
                # 从任务字典中删除task_id记录
                if task_id in download_tasks:
                    del download_tasks[task_id]
            
            # 使用Flask的after_request装饰器在响应发送后执行清理
            
            @after_this_request
            def cleanup(response):
                cleanup_after_download()
                return response
            
            return send_file(target_file, as_attachment=True)
    
    return jsonify({
        'success': False,
        'error': '文件不存在'
    }), 404


@app.route('/api/download/merge/<task_id>', methods=['GET'])
def download_merged_file(task_id):
    """合并下载视频和音频文件API"""
    if task_id not in download_tasks:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    task = download_tasks[task_id]
    if task['status'] != 'completed':
        return jsonify({
            'success': False,
            'error': '文件尚未准备好'
        }), 400
    
    file_path = task['file_path']
    if not file_path:
        return jsonify({
            'success': False,
            'error': '文件路径不存在'
        }), 400
    
    # 如果已经是合并的视频文件，直接返回
    if isinstance(file_path, str) and os.path.exists(file_path):
        # 创建下载后清理功能
        def cleanup_after_download():
            # 使用安全删除函数
            safe_delete_file(file_path)
            # 从任务字典中删除task_id记录
            if task_id in download_tasks:
                del download_tasks[task_id]
        
        # 使用Flask的after_request装饰器在响应发送后执行清理
        
        @after_this_request
        def cleanup(response):
            cleanup_after_download()
            return response
        
        return send_file(file_path, as_attachment=True)
    
    # 如果是分离的视频和音频文件，进行合并
    elif isinstance(file_path, dict) and 'video' in file_path and 'audio' in file_path:
        video_path = file_path['video']
        audio_path = file_path['audio']
        
        if not (os.path.exists(video_path) and os.path.exists(audio_path)):
            return jsonify({
                'success': False,
                'error': '视频或音频文件不存在'
            }), 404
        
        try:
            # 导入ffmpeg合并功能
            import subprocess
            
            # 生成合并后的文件名
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            merged_filename = f"{base_name}_merged.mp4"
            merged_path = os.path.join(DOWNLOAD_DIR, merged_filename)
            
            # 如果合并文件已存在，直接返回
            if os.path.exists(merged_path):
                return send_file(merged_path, as_attachment=True)
            
            # 使用ffmpeg合并视频和音频
            cmd = [
                'ffmpeg', '-i', video_path, '-i', audio_path,
                '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental',
                '-y', merged_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(merged_path):
                # 更新任务记录中的文件路径
                download_tasks[task_id]['file_path'] = merged_path
                
                # 创建一个响应对象，在发送完成后清理文件和任务记录
                def cleanup_after_download():
                    # 使用安全删除函数删除原始的视频和音频文件
                    safe_delete_file(video_path)
                    safe_delete_file(audio_path)
                    # 删除合并后的文件
                    safe_delete_file(merged_path)
                    # 从任务字典中删除task_id记录
                    if task_id in download_tasks:
                        del download_tasks[task_id]
                
                # 使用Flask的after_request装饰器在响应发送后执行清理
                
                @after_this_request
                def cleanup(response):
                    cleanup_after_download()
                    return response
                
                return send_file(merged_path, as_attachment=True)
            else:
                return jsonify({
                    'success': False,
                    'error': f'合并失败: {result.stderr}'
                }), 500
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'合并过程中出错: {str(e)}'
            }), 500
    
    return jsonify({
        'success': False,
        'error': '无法处理的文件格式'
    }), 400


@app.route('/api/tasks', methods=['GET'])
def get_all_tasks():
    """获取所有任务列表API - 返回文本格式"""
    if not download_tasks:
        return Response('当前没有任何下载任务', mimetype='text/plain; charset=utf-8')
    
    # 状态图标映射
    status_icons = {
        'pending': '⏳',
        'downloading': '⬇️',
        'completed': '✅',
        'failed': '❌'
    }
    
    text_result = f"下载任务列表 (共 {len(download_tasks)} 个任务)\n\n"
    
    # 按创建时间排序任务
    sorted_tasks = sorted(download_tasks.items(), key=lambda x: x[1]['created_at'], reverse=True)
    
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
        text_result += f"   视频URL: {task['url']}\n"
        
        if task.get('error'):
            text_result += f"   错误: {task['error']}\n"
        
        if task['status'] == 'completed':
            text_result += f"   下载链接: GET /api/download/file/{task_id}\n"
        
        text_result += "\n" + "-" * 60 + "\n\n"
    
    text_result += "使用说明:\n"
    text_result += "- 查询单个任务状态: GET /api/download/status/<task_id>\n"
    text_result += "- 下载已完成文件: GET /api/download/file/<task_id>\n"
    text_result += "- 创建新下载任务: GET /api/video/download?url=<video_url>"
    
    return Response(text_result, mimetype='text/plain; charset=utf-8')

@app.errorhandler(404)
def not_found(error):
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
    return Response(text_result, mimetype='text/plain; charset=utf-8', status=404)

@app.errorhandler(500)
def internal_error(error):
    text_result = """❌ 500 - 服务器内部错误

服务器在处理请求时发生了内部错误。

可能的原因:
- 服务器配置问题
- 依赖服务不可用
- 代码执行异常

请稍后重试，如果问题持续存在，请联系管理员。"""
    return Response(text_result, mimetype='text/plain; charset=utf-8', status=500)

if __name__ == '__main__':
    print("B站视频下载API服务启动中...")
    print("API文档:")
    print("  GET  /                           - 获取API信息")
    print("  GET  /api/video/info             - 获取视频信息 (支持 &q=auto 参数获取全部视频和音频流)")
    print("  GET  /api/video/quality          - 获取视频质量选项")
    print("  GET  /api/video/download         - 下载视频")
    print("  GET  /api/download/status/<id>   - 查询下载状态")
    print("  GET  /api/download/file/<id>     - 下载文件")
    print("  GET  /api/download/merge/<id>    - 合并下载视频音频")
    print("  GET  /api/tasks                  - 获取所有任务")
    print("\n服务器将在 http://localhost:5000 启动")
    
    app.run(host='0.0.0.0', port=5000, debug=True)