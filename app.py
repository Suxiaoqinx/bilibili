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
    """API首页"""
    return jsonify({
        'message': 'B站视频下载API服务',
        'version': '1.0.0',
        'endpoints': {
            'GET /': '获取API信息',
            'GET /api/video/info': '获取视频信息 (支持 &q=auto 参数获取全部视频和音频流)',
            'GET /api/video/quality': '获取视频质量选项',
            'GET /api/video/download': '下载视频',
            'GET /api/download/status/<task_id>': '查询下载状态',
            'GET /api/download/file/<task_id>': '下载文件'
        }
    })

@app.route('/api/video/info', methods=['GET'])
def get_video_info():
    """获取视频信息API"""
    try:
        # 从URL参数获取视频链接
        url = request.args.get('url')
        if not url:
            return jsonify({
                'success': False,
                'error': '缺少必要参数: url'
            }), 400
        
        # 获取q参数，用于控制返回的流信息
        q_param = request.args.get('q', '').lower()
        
        cookies = load_cookies()
        
        # 获取视频信息
        playinfo = get_playinfo_from_bilibili(url, cookies)
        if not playinfo:
            return jsonify({
                'success': False,
                'error': '获取视频信息失败，请检查URL或cookie'
            }), 400
        
        video_info = extract_video_info(playinfo, url, cookies)
        if not video_info:
            return jsonify({
                'success': False,
                'error': '解析视频信息失败'
            }), 400
        
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
        
        # 格式化返回数据（使用OrderedDict确保字段顺序）
        result = OrderedDict([
            ('success', True),
            ('title', video_info.get('title', '')),
            ('cover', video_info.get('cover', '')),
            ('data', OrderedDict([
                ('duration', video_info.get('duration', 0)),
                ('highest_quality', OrderedDict([
                    ('video', highest_video),
                    ('audio', highest_audio)
                ])),
                ('video_streams', video_streams),
                ('audio_streams', audio_streams)
            ]))
        ])
        
        # 使用json.dumps确保字段顺序
        json_str = json.dumps(result, ensure_ascii=False, indent=2)
        return Response(json_str, mimetype='application/json')
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/video/quality', methods=['GET'])
def get_video_quality():
    """获取视频质量选项API"""
    try:
        url = request.args.get('url')
        if not url:
            return jsonify({
                'success': False,
                'error': '缺少必要参数: url'
            }), 400
        
        cookies_param = request.args.get('cookies')
        cookies = cookies_param if cookies_param else load_cookies()
        
        # 获取视频质量选项
        quality_options = get_video_quality_options(url, cookies)
        if not quality_options:
            return jsonify({
                'success': False,
                'error': '获取视频质量选项失败，请检查URL或cookie'
            }), 400
        
        return jsonify({
            'success': True,
            'data': quality_options
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/video/download', methods=['GET'])
def download_video():
    """下载视频API"""
    try:
        url = request.args.get('url')
        if not url:
            return jsonify({
                'success': False,
                'error': '缺少必要参数: url'
            }), 400
        
        # 检查是否已存在相同URL的下载任务
        for existing_task_id, task_info in download_tasks.items():
            if task_info['url'] == url and task_info['status'] in ['pending', 'downloading', 'completed']:
                return jsonify({
                    'success': False,
                    'error': '当前解析已经存在，请勿重复请求',
                    'existing_task_id': existing_task_id,
                    'existing_status': task_info['status']
                }), 409
        
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
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '下载任务已启动'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        }), 500

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
    """查询下载状态API"""
    if task_id not in download_tasks:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    task = download_tasks[task_id]
    return jsonify({
        'success': True,
        'data': {
            'task_id': task_id,
            'status': task['status'],
            'progress': task['progress'],
            'message': task['message'],
            'created_at': task['created_at'],
            'error': task.get('error')
        }
    })

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
    """获取所有任务列表API"""
    tasks = []
    for task_id, task in download_tasks.items():
        tasks.append({
            'task_id': task_id,
            'status': task['status'],
            'progress': task['progress'],
            'message': task['message'],
            'created_at': task['created_at'],
            'url': task['url']
        })
    
    return jsonify({
        'success': True,
        'data': tasks
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': '接口不存在'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': '服务器内部错误'
    }), 500

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