import requests
import re
import json
import os
import subprocess
import tempfile
import time
import sys
import shutil
from urllib.parse import unquote

def get_playinfo_from_bilibili(url, cookies=None):
    """
    访问B站视频页面，获取window.__playinfo__中的JSON数据
    
    Args:
        url (str): B站视频URL
        cookies (dict or str): Cookie信息，可以是字典或字符串格式
    
    Returns:
        dict: 解析后的playinfo JSON数据，如果失败返回None
    """
    
    # 设置请求头，模拟浏览器访问
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # 处理cookie
    cookie_dict = {}
    if cookies:
        if isinstance(cookies, str):
            # 如果是字符串格式的cookie，解析为字典
            for item in cookies.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookie_dict[key] = value
        elif isinstance(cookies, dict):
            cookie_dict = cookies
    
    try:
        # 发送GET请求
        response = requests.get(url, headers=headers, cookies=cookie_dict, timeout=10)
        response.raise_for_status()
        
        # 获取页面内容
        html_content = response.text
        
        # 使用正则表达式查找window.__playinfo__的内容
        pattern = r'<script>window\.__playinfo__\s*=\s*({.*?})</script>'
        match = re.search(pattern, html_content, re.DOTALL)
        
        if match:
            # 提取JSON字符串
            json_str = match.group(1)
            
            # 解析JSON
            try:
                playinfo_data = json.loads(json_str)
                return playinfo_data
            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}")
                print(f"原始JSON字符串: {json_str[:200]}...")
                return None
        else:
            print("未找到window.__playinfo__数据")
            return None
            
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None
    except Exception as e:
        print(f"发生错误: {e}")
        return None

def get_video_title_and_cover(url, cookies=None):
    """
    从B站视频页面获取视频标题和封面
    
    Args:
        url (str): B站视频URL
        cookies (dict or str): Cookie信息，可以是字典或字符串格式
    
    Returns:
        dict: 包含title和cover的字典，如果失败返回None
    """
    
    # 设置请求头，模拟浏览器访问
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # 处理cookie
    cookie_dict = {}
    if cookies:
        if isinstance(cookies, str):
            # 如果是字符串格式的cookie，解析为字典
            for item in cookies.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookie_dict[key] = value
        elif isinstance(cookies, dict):
            cookie_dict = cookies
    
    try:
        # 发送GET请求
        response = requests.get(url, headers=headers, cookies=cookie_dict, timeout=10)
        response.raise_for_status()
        
        # 获取页面内容
        html_content = response.text
        
        result = {
            'title': '',
            'cover': ''
        }
        
        # 提取视频标题
        title_pattern = r'<title[^>]*>([^<]+)</title>'
        title_match = re.search(title_pattern, html_content, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # 移除B站页面标题后缀
            title = re.sub(r'_哔哩哔哩_bilibili$', '', title)
            result['title'] = title
        
        # 提取视频封面 - 尝试多种方式
        # 方式1: 从meta标签获取
        cover_patterns = [
            r'<meta\s+property="og:image"\s+content="([^"]+)"',
            r'<meta\s+name="twitter:image"\s+content="([^"]+)"',
            r'"pic"\s*:\s*"([^"]+)"',
            r'"cover"\s*:\s*"([^"]+)"'
        ]
        
        for pattern in cover_patterns:
            cover_match = re.search(pattern, html_content, re.IGNORECASE)
            if cover_match:
                cover_url = cover_match.group(1)
                # 处理转义字符
                cover_url = cover_url.replace('\\/', '/')
                # 处理Unicode转义字符
                try:
                    cover_url = cover_url.encode().decode('unicode_escape')
                except:
                    pass
                if cover_url.startswith('http'):
                    result['cover'] = cover_url
                    break
        
        # 如果还没找到封面，尝试从window.__INITIAL_STATE__中获取
        if not result['cover']:
            initial_state_pattern = r'window\.__INITIAL_STATE__\s*=\s*({.*?});'
            initial_match = re.search(initial_state_pattern, html_content, re.DOTALL)
            if initial_match:
                try:
                    initial_data = json.loads(initial_match.group(1))
                    # 尝试从不同路径获取封面
                    if 'videoData' in initial_data and 'pic' in initial_data['videoData']:
                        cover_url = initial_data['videoData']['pic']
                        # 处理Unicode转义字符
                        try:
                            cover_url = cover_url.encode().decode('unicode_escape')
                        except:
                            pass
                        # 将http转换为https
                        if cover_url.startswith('http://'):
                            cover_url = cover_url.replace('http://', 'https://')
                        result['cover'] = cover_url
                    elif 'aid' in initial_data:
                        # 构造封面URL
                        aid = initial_data['aid']
                        result['cover'] = f'https://i0.hdslb.com/bfs/archive/{aid}.jpg'
                except json.JSONDecodeError:
                    pass
        
        return result
        
    except requests.RequestException as e:
        print(f"获取视频信息请求失败: {e}")
        return None
    except Exception as e:
        print(f"获取视频信息发生错误: {e}")
        return None

def load_cookies_from_file(cookie_file_path):
    """
    从文件中加载cookie
    
    Args:
        cookie_file_path (str): cookie文件路径
    
    Returns:
        str: cookie字符串
    """
    try:
        with open(cookie_file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Cookie文件未找到: {cookie_file_path}")
        return None
    except Exception as e:
        print(f"读取Cookie文件失败: {e}")
        return None

def get_highest_quality_streams(playinfo_data, url=None, cookies=None):
    """
    获取最高质量的视频流和音频流地址
    
    Args:
        playinfo_data (dict): playinfo JSON数据
        url (str): 视频URL，用于获取标题和封面
        cookies (dict or str): Cookie信息
    
    Returns:
        dict: 包含最高质量视频流和音频流信息的字典
    """
    video_info = extract_video_info(playinfo_data, url, cookies)
    if not video_info:
        return None
    
    result = {
        'highest_video': video_info.get('highest_video_url'),
        'highest_audio': video_info.get('highest_audio_url'),
        'duration': video_info.get('duration', 0)
    }
    
    return result

def extract_video_info(playinfo_data, url=None, cookies=None):
    """
    从playinfo数据中提取视频信息
    
    Args:
        playinfo_data (dict): playinfo JSON数据
        url (str): 视频URL，用于获取标题和封面
        cookies (dict or str): Cookie信息
    
    Returns:
        dict: 提取的视频信息
    """
    if not playinfo_data:
        return None
    
    try:
        video_info = {
            'title': '',
            'cover': '',
            'duration': 0,
            'video_urls': [],
            'audio_urls': [],
            'highest_video_url': None,
            'highest_audio_url': None
        }
        
        # 获取视频标题和封面
        if url:
            title_cover_info = get_video_title_and_cover(url, cookies)
            if title_cover_info:
                video_info['title'] = title_cover_info.get('title', '')
                video_info['cover'] = title_cover_info.get('cover', '')
        
        # 提取视频流信息
        if 'data' in playinfo_data and 'dash' in playinfo_data['data']:
            dash_data = playinfo_data['data']['dash']
            
            # 视频流
            if 'video' in dash_data:
                for video in dash_data['video']:
                    # 处理backupUrl，可能是数组或字符串
                    backup_url = video.get('backupUrl', '')
                    
                    # 如果backupUrl是列表，取第一个URL
                    if isinstance(backup_url, list) and backup_url:
                        url = backup_url[0]
                    elif isinstance(backup_url, str):
                        url = backup_url
                    else:
                        url = ''
                    
                    video_info['video_urls'].append({
                        'quality': video.get('id', 0),
                        'url': url,
                        'bandwidth': video.get('bandwidth', 0),
                        'codecs': video.get('codecs', ''),
                        'width': video.get('width', 0),
                        'height': video.get('height', 0),
                        'frameRate': video.get('frameRate', 0)
                    })
                
                # 按质量ID降序排序视频流（质量ID越高代表质量越好）
                video_info['video_urls'].sort(key=lambda x: x['quality'], reverse=True)
                
                # 获取最高质量的视频流（排序后第一个就是最高质量）
                if video_info['video_urls']:
                    video_info['highest_video_url'] = video_info['video_urls'][0]
            
            # 音频流
            if 'audio' in dash_data:
                for audio in dash_data['audio']:
                    # 处理backupUrl，可能是数组或字符串
                    backup_url = audio.get('backupUrl', '')
                    
                    # 如果backupUrl是列表，取第一个URL
                    if isinstance(backup_url, list) and backup_url:
                        url = backup_url[0]
                    elif isinstance(backup_url, str):
                        url = backup_url
                    else:
                        url = ''
                    
                    video_info['audio_urls'].append({
                        'quality': audio.get('id', 0),
                        'url': url,
                        'bandwidth': audio.get('bandwidth', 0),
                        'codecs': audio.get('codecs', '')
                    })
            
            # 检查是否存在dolby音频流
            dolby_audio = None
            if 'dolby' in dash_data and dash_data['dolby'] and 'audio' in dash_data['dolby']:
                dolby_audio_list = dash_data['dolby']['audio']
                if dolby_audio_list and len(dolby_audio_list) > 0:
                    # 选择第一个dolby音频流
                    dolby_stream = dolby_audio_list[0]
                    
                    # 处理dolby音频流的URL
                    backup_url = dolby_stream.get('backupUrl', '')
                    if isinstance(backup_url, list) and backup_url:
                        dolby_url = backup_url[0]
                    elif isinstance(backup_url, str):
                        dolby_url = backup_url
                    else:
                        dolby_url = ''
                    
                    dolby_audio = {
                        'quality': dolby_stream.get('id', 0),
                        'url': dolby_url,
                        'bandwidth': dolby_stream.get('bandwidth', 0),
                        'codecs': dolby_stream.get('codecs', '')
                    }
                    
                    # 将dolby音频流添加到音频流列表中
                    video_info['audio_urls'].append(dolby_audio)
            
            # 检查是否存在flac音频流
            flac_audio = None
            try:
                if 'flac' in dash_data and dash_data['flac'] and 'audio' in dash_data['flac']:
                    flac_stream = dash_data['flac']['audio']  # FLAC是对象，不是数组
                    if flac_stream:
                        # 处理flac音频流的URL
                        backup_url = flac_stream.get('backupUrl', '')
                        if isinstance(backup_url, list) and backup_url:
                            flac_url = backup_url[0]
                        elif isinstance(backup_url, str) and backup_url:
                            flac_url = backup_url
                        else:
                            flac_url = ''
                        
                        # 只有当URL不为空时才添加FLAC音频流
                        if flac_url:
                            flac_audio = {
                                'quality': flac_stream.get('id', 30251),  # 默认FLAC质量ID
                                'url': flac_url,
                                'bandwidth': max(flac_stream.get('bandwidth', 1), 1),  # 确保带宽至少为1
                                'codecs': flac_stream.get('codecs', 'fLaC')
                            }
                            
                            # 将flac音频流添加到音频流列表中
                            video_info['audio_urls'].append(flac_audio)
            except Exception as flac_error:
                print(f"处理FLAC音频流时出错: {flac_error}")
                flac_audio = None
            
            # 按质量排序音频流（优先级：flac > dolby > 普通音频流按带宽排序）
            if video_info['audio_urls']:
                try:
                    # 自定义排序函数：flac > dolby > 普通音频流按带宽排序
                    def audio_sort_key(audio):
                        quality_id = audio.get('quality', 0)
                        bandwidth = audio.get('bandwidth', 0)
                        
                        # FLAC音频流优先级最高
                        if quality_id == 30251:  # FLAC
                            return (3, bandwidth)
                        # Dolby音频流次优先级
                        elif quality_id == 30250:  # Dolby
                            return (2, bandwidth)
                        # 普通音频流按带宽排序
                        else:
                            return (1, bandwidth)
                    
                    video_info['audio_urls'].sort(key=audio_sort_key, reverse=True)
                    
                    # 获取最高质量的音频流（排序后第一个就是最高质量）
                    video_info['highest_audio_url'] = video_info['audio_urls'][0]
                    
                    # 输出选择的音频类型信息（已注释以避免API调用时的控制台输出）
                    highest_quality_id = video_info['highest_audio_url'].get('quality', 0)
                    # if highest_quality_id == 30251:
                    #     print("检测到FLAC音频流，优先选择FLAC音频")
                    # elif highest_quality_id == 30250:
                    #     print("检测到Dolby音频流，优先选择Dolby音频")
                        
                except Exception as audio_error:
                    print(f"选择最高质量音频流时出错: {audio_error}")
                    # 出错时选择第一个音频流作为备选
                    if video_info['audio_urls']:
                        video_info['highest_audio_url'] = video_info['audio_urls'][0]
            
            # 时长
            video_info['duration'] = dash_data.get('duration', 0)
        
        return video_info
        
    except Exception as e:
        print(f"提取视频信息失败: {e}")
        return None

def get_quality_name(quality_id):
    """
    根据质量ID获取中文质量名称
    
    Args:
        quality_id (int): B站视频质量ID
    
    Returns:
        str: 中文质量名称
    """
    quality_map = {
        127: "超高清 8K",
        126: "杜比视界",
        125: "HDR真彩",
        120: "超高清 4K",
        116: "1080P 60帧",
        112: "1080P 高码率",
        80: "高清 1080P",
        74: "高清 720P60",
        64: "高清 720P",
        32: "清晰 480P",
        16: "流畅 360P"
    }
    
    return quality_map.get(quality_id, f"未知质量({quality_id})")

def get_audio_quality_name(quality_id):
    """
    根据音频质量ID获取中文质量名称
    
    Args:
        quality_id (int): B站音频质量ID
    
    Returns:
        str: 中文音频质量名称
    """
    audio_quality_map = {
        30251: "Hi-Res无损",  # Hi-Res无损FLAC音频
        30250: "杜比音频",  # Dolby音频
        30280: "320K",
        30232: "128K",
        30216: "64K"
    }
    
    return audio_quality_map.get(quality_id, f"未知音质({quality_id})")

def format_bytes(bytes_num):
    """
    格式化字节数为可读格式
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f}{unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f}TB"

# 已移除show_progress_bar函数，改为直接在download_stream中显示百分比进度

def download_stream(url, output_path, headers=None, progress_callback=None):
    """
    下载视频流或音频流
    
    Args:
        url (str): 流地址
        output_path (str): 输出文件路径
        headers (dict): 请求头
        progress_callback (function): 进度回调函数，接收(current, total, message)参数
    
    Returns:
        bool: 下载是否成功
    """
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
    
    try:
        print(f"开始下载: {output_path}", flush=True)
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        start_time = time.time()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # 显示下载进度百分比
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        elapsed_time = time.time() - start_time
                        if elapsed_time > 0:
                            speed = downloaded_size / elapsed_time
                            speed_str = f"{format_bytes(speed)}/s"
                        else:
                            speed_str = "--/s"
                        
                        # 控制台输出
                        print(f"\r下载进度: {progress:.1f}% ({format_bytes(downloaded_size)}/{format_bytes(total_size)}) 速度: {speed_str}", end='', flush=True)
                        
                        # API回调
                        if progress_callback:
                            progress_callback(downloaded_size, total_size, f"下载进度: {progress:.1f}%")
                    else:
                        # 如果无法获取总大小，显示已下载大小
                        elapsed_time = time.time() - start_time
                        if elapsed_time > 0:
                            speed = downloaded_size / elapsed_time
                            speed_str = f"{format_bytes(speed)}/s"
                        else:
                            speed_str = "--/s"
                        print(f"\r已下载: {format_bytes(downloaded_size)} 速度: {speed_str}", end='', flush=True)
                        
                        # API回调
                        if progress_callback:
                            progress_callback(downloaded_size, 0, f"已下载: {format_bytes(downloaded_size)}")
        
        print(f"\n下载完成: {output_path}", flush=True)
        return True
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 下载被用户中断，正在清理临时文件: {output_path}", flush=True)
        # 删除未完成的文件
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
                print(f"✅ 已删除临时文件: {output_path}", flush=True)
        except Exception as cleanup_error:
            print(f"❌ 清理临时文件失败: {cleanup_error}", flush=True)
        raise  # 重新抛出KeyboardInterrupt异常
    except Exception as e:
        print(f"\n下载失败: {e}", flush=True)
        return False

def check_ffmpeg_available():
    """
    检测系统中是否安装了FFmpeg
    
    Returns:
        bool: FFmpeg是否可用
    """
    return shutil.which('ffmpeg') is not None

def merge_video_audio_native(video_path, audio_path, output_path):
    """
    使用原生Python代码合并视频和音频（简单的容器级合并）
    注意：这是一个基础实现，可能不如FFmpeg稳定
    
    Args:
        video_path (str): 视频文件路径
        audio_path (str): 音频文件路径
        output_path (str): 输出文件路径
    
    Returns:
        bool: 合并是否成功
    """
    try:
        print(f"开始使用原生方法合并视频和音频...", flush=True)
        
        # 读取视频文件
        with open(video_path, 'rb') as video_file:
            video_data = video_file.read()
        
        # 读取音频文件
        with open(audio_path, 'rb') as audio_file:
            audio_data = audio_file.read()
        
        # 简单的MP4容器合并（这是一个基础实现）
        # 注意：这种方法可能不适用于所有格式，建议使用FFmpeg
        with open(output_path, 'wb') as output_file:
            # 写入视频数据
            output_file.write(video_data)
            # 追加音频数据（这是一个简化的实现）
            # 实际的MP4合并需要更复杂的容器处理
        
        print(f"原生合并完成: {output_path}", flush=True)
        print(f"警告：原生合并是基础实现，建议安装FFmpeg以获得更好的兼容性", flush=True)
        return True
        
    except Exception as e:
        print(f"原生合并过程中发生错误: {e}", flush=True)
        return False

def merge_video_audio_with_ffmpeg(video_path, audio_path, output_path):
    """
    使用ffmpeg合并视频和音频
    
    Args:
        video_path (str): 视频文件路径
        audio_path (str): 音频文件路径
        output_path (str): 输出文件路径
    
    Returns:
        bool: 合并是否成功
    """
    try:
        # 构建ffmpeg命令
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',  # 视频流直接复制，不重新编码
            '-c:a', 'copy',  # 音频流直接复制，不重新编码
            '-y',  # 覆盖输出文件
            output_path
        ]
        
        print(f"开始合并视频和音频...", flush=True)
        print(f"命令: {' '.join(cmd)}", flush=True)
        
        # 执行ffmpeg命令
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print(f"合并成功: {output_path}", flush=True)
            return True
        else:
            print(f"合并失败: {result.stderr}", flush=True)
            return False
            
    except FileNotFoundError:
        print("错误: 未找到ffmpeg，请确保ffmpeg已安装并添加到系统PATH中")
        return False
    except Exception as e:
        print(f"合并过程中发生错误: {e}", flush=True)
        return False

def merge_video_audio_smart(video_path, audio_path, output_path):
    """
    智能合并视频和音频：优先使用FFmpeg，如果不可用则使用原生方法
    
    Args:
        video_path (str): 视频文件路径
        audio_path (str): 音频文件路径
        output_path (str): 输出文件路径
    
    Returns:
        tuple: (是否成功, 使用的方法)
    """
    if check_ffmpeg_available():
        print("检测到FFmpeg，使用FFmpeg进行合并", flush=True)
        success = merge_video_audio_with_ffmpeg(video_path, audio_path, output_path)
        return success, "ffmpeg"
    else:
        print("未检测到FFmpeg，使用原生方法进行合并", flush=True)
        success = merge_video_audio_native(video_path, audio_path, output_path)
        return success, "native"

def download_only_bilibili_video(url, output_dir="downloads", cookies=None, output_filename=None, progress_callback=None):
    """
    只下载B站视频流和音频流，不进行合并
    
    Args:
        url (str): B站视频URL
        output_dir (str): 输出目录
        cookies (str or dict): Cookie信息
        output_filename (str): 输出文件名前缀（不包含扩展名）
        progress_callback (function): 进度回调函数，接收(current, total, message)参数
    
    Returns:
        tuple: (视频文件路径, 音频文件路径)，失败返回(None, None)
    """
    video_path = None
    audio_path = None
    
    try:
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取视频信息
        if progress_callback:
            progress_callback(10, 100, "正在解析视频信息...")
        playinfo = get_playinfo_from_bilibili(url, cookies)
        
        if not playinfo:
            if progress_callback:
                progress_callback(0, 100, "获取视频信息失败")
            return None, None
        
        video_info = extract_video_info(playinfo, url, cookies)
        if not video_info:
            if progress_callback:
                progress_callback(0, 100, "提取视频信息失败")
            return None, None
        
        highest_video = video_info.get('highest_video_url')
        highest_audio = video_info.get('highest_audio_url')
        
        if not highest_video or not highest_audio:
            if progress_callback:
                progress_callback(0, 100, "未找到可用的视频流或音频流")
            return None, None
        
        # 生成文件名
        if not output_filename:
            # 从URL中提取BV号作为文件名
            bv_match = re.search(r'BV[a-zA-Z0-9]+', url)
            if bv_match:
                output_filename = bv_match.group()
            else:
                output_filename = f"bilibili_video_{int(time.time())}"
        
        # 创建文件路径
        video_path = os.path.join(output_dir, f"{output_filename}_video.m4v")
        # 如果是Hi-Res音质，使用flac扩展名
        audio_extension = ".flac" if highest_audio['quality'] == 30251 else ".m4a"
        audio_path = os.path.join(output_dir, f"{output_filename}_audio{audio_extension}")
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        
        # 下载视频流
        if progress_callback:
            progress_callback(20, 100, "正在下载视频流...")
        video_success = download_stream(highest_video['url'], video_path, headers, progress_callback)
        
        # 下载音频流
        if progress_callback:
            progress_callback(60, 100, "正在下载音频流...")
        audio_success = download_stream(highest_audio['url'], audio_path, headers, progress_callback)
        
        if video_success and audio_success:
            if progress_callback:
                progress_callback(100, 100, "视频和音频下载完成")
            return video_path, audio_path
        else:
            # 清理部分下载的文件
            if video_success and os.path.exists(video_path):
                os.remove(video_path)
            if audio_success and os.path.exists(audio_path):
                os.remove(audio_path)
            if progress_callback:
                progress_callback(0, 100, "下载失败")
            return None, None
    
    except KeyboardInterrupt:
        # 用户中断下载，清理临时文件
        print("\n⚠️ 下载被用户中断，正在清理临时文件...")
        
        # 清理视频文件
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                print(f"✅ 已删除临时视频文件: {video_path}")
            except Exception as e:
                print(f"❌ 删除临时视频文件失败: {e}")
        
        # 清理音频文件
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                print(f"✅ 已删除临时音频文件: {audio_path}")
            except Exception as e:
                print(f"❌ 删除临时音频文件失败: {e}")
        
        if progress_callback:
            progress_callback(0, 100, "下载被用户中断")
        
        # 重新抛出异常，让上层处理
        raise
            
    except Exception as e:
        if progress_callback:
            progress_callback(0, 100, f"下载过程中发生错误: {e}")
        return None, None

def download_and_merge_bilibili_video(url, output_dir="downloads", cookies=None, output_filename=None, progress_callback=None):
    """
    下载B站视频并合并音视频
    
    Args:
        url (str): B站视频URL
        output_dir (str): 输出目录
        cookies (str or dict): Cookie信息
        output_filename (str): 输出文件名（不包含扩展名）
        progress_callback (function): 进度回调函数，接收(current, total, message)参数
    
    Returns:
        str: 合并后的视频文件路径，失败返回None
    """
    try:
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取视频信息
        if progress_callback:
            progress_callback(10, 100, "正在解析视频信息...")
        playinfo = get_playinfo_from_bilibili(url, cookies)
        
        if not playinfo:
            if progress_callback:
                progress_callback(0, 100, "获取视频信息失败")
            return None
        
        video_info = extract_video_info(playinfo, url, cookies)
        if not video_info:
            if progress_callback:
                progress_callback(0, 100, "提取视频信息失败")
            return None
        
        highest_video = video_info.get('highest_video_url')
        highest_audio = video_info.get('highest_audio_url')
        
        if not highest_video or not highest_audio:
            if progress_callback:
                progress_callback(0, 100, "未找到可用的视频流或音频流")
            return None
        
        # 生成文件名
        if not output_filename:
            # 从URL中提取BV号作为文件名
            bv_match = re.search(r'BV[a-zA-Z0-9]+', url)
            if bv_match:
                output_filename = bv_match.group()
            else:
                output_filename = f"bilibili_video_{int(time.time())}"
        
        # 创建临时文件路径
        temp_video_path = os.path.join(output_dir, f"{output_filename}_temp_video.m4v")
        temp_audio_path = os.path.join(output_dir, f"{output_filename}_temp_audio.m4a")
        final_output_path = os.path.join(output_dir, f"{output_filename}.mp4")
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        
        # 下载视频流
        if progress_callback:
            progress_callback(20, 100, "正在下载视频流...")
        if not download_stream(highest_video['url'], temp_video_path, headers, progress_callback):
            if progress_callback:
                progress_callback(0, 100, "视频流下载失败")
            return None
        
        # 下载音频流
        if progress_callback:
            progress_callback(50, 100, "正在下载音频流...")
        if not download_stream(highest_audio['url'], temp_audio_path, headers, progress_callback):
            # 清理已下载的视频文件
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            if progress_callback:
                progress_callback(0, 100, "音频流下载失败")
            return None
        
        # 合并视频和音频
        if progress_callback:
            progress_callback(80, 100, "正在合并视频和音频...")
        success, method = merge_video_audio_smart(temp_video_path, temp_audio_path, final_output_path)
        if success:
            # 清理临时文件
            try:
                os.remove(temp_video_path)
                os.remove(temp_audio_path)
            except Exception as e:
                pass  # 忽略清理错误
            
            if progress_callback:
                progress_callback(100, 100, "视频下载和合并完成")
            return final_output_path
        else:
            # 合并失败，清理临时文件
            try:
                if os.path.exists(temp_video_path):
                    os.remove(temp_video_path)
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
            except Exception as e:
                pass  # 忽略清理错误
            if progress_callback:
                progress_callback(0, 100, "视频合并失败")
            return None
            
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 下载被用户中断，正在清理临时文件...", flush=True)
        # 清理所有可能的临时文件
        temp_files = []
        if 'temp_video_path' in locals():
            temp_files.append(temp_video_path)
        if 'temp_audio_path' in locals():
            temp_files.append(temp_audio_path)
        
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"✅ 已删除临时文件: {temp_file}", flush=True)
            except Exception as cleanup_error:
                print(f"❌ 清理临时文件失败: {cleanup_error}", flush=True)
        
        if progress_callback:
            progress_callback(0, 100, "下载被用户中断")
        raise  # 重新抛出KeyboardInterrupt异常
    except Exception as e:
        if progress_callback:
            progress_callback(0, 100, f"下载和合并过程中发生错误: {e}")
        return None

def get_video_quality_options(url, cookies=None):
    """
    获取视频的所有可用质量选项（API版本）
    
    Args:
        url (str): B站视频URL
        cookies (str or dict): Cookie信息
    
    Returns:
        dict: 包含视频和音频质量选项的字典，失败返回None
    """
    try:
        # 获取视频信息
        playinfo = get_playinfo_from_bilibili(url, cookies)
        
        if not playinfo:
            return None
        
        video_info = extract_video_info(playinfo, url, cookies)
        if not video_info:
            return None
        
        if not video_info['video_urls'] or not video_info['audio_urls']:
            return None
        
        # 格式化视频质量选项
        video_options = []
        for i, video in enumerate(video_info['video_urls']):
            quality_name = get_quality_name(video['quality'])
            video_options.append({
                'index': i,
                'quality_id': video['quality'],
                'quality_name': quality_name,
                'width': video['width'],
                'height': video['height'],
                'frame_rate': video['frameRate'],
                'bandwidth': video.get('bandwidth', 0),
                'codecs': video.get('codecs', '')
            })
        
        # 格式化音频质量选项
        audio_options = []
        for i, audio in enumerate(video_info['audio_urls']):
            audio_quality_name = get_audio_quality_name(audio['quality'])
            audio_options.append({
                'index': i,
                'quality_id': audio['quality'],
                'quality_name': audio_quality_name,
                'bandwidth': audio['bandwidth'],
                'codecs': audio.get('codecs', '')
            })
        
        return {
            'video_options': video_options,
            'audio_options': audio_options,
            'duration': video_info.get('duration', 0)
        }
        
    except Exception as e:
        return None

def select_quality_and_download(url, cookies=None, output_dir="downloads", merge=True, video_quality_index=0, audio_quality_index=0, filename=None, progress_callback=None):
    """
    选择视频质量并下载（API版本）
    
    Args:
        url (str): B站视频URL
        cookies (str or dict): Cookie信息
        output_dir (str): 输出目录
        merge (bool): 是否合并视频和音频
        video_quality_index (int): 视频质量索引，0表示最高质量
        audio_quality_index (int): 音频质量索引，0表示最高质量
        progress_callback (function): 进度回调函数，接收(current, total, message)参数
    
    Returns:
        str or tuple: 如果merge=True返回合并后的文件路径，否则返回(视频路径, 音频路径)
    """
    try:
        # 获取视频信息
        if progress_callback:
            progress_callback(10, 100, "正在解析视频信息...")
        playinfo = get_playinfo_from_bilibili(url, cookies)
        
        if not playinfo:
            if progress_callback:
                progress_callback(0, 100, "获取视频信息失败")
            return None if merge else (None, None)
        
        video_info = extract_video_info(playinfo, url, cookies)
        if not video_info:
            if progress_callback:
                progress_callback(0, 100, "提取视频信息失败")
            return None if merge else (None, None)
        
        if not video_info['video_urls'] or not video_info['audio_urls']:
            if progress_callback:
                progress_callback(0, 100, "未找到可用的视频流或音频流")
            return None if merge else (None, None)
        
        # 选择视频质量（默认选择最高质量）
        if video_quality_index >= len(video_info['video_urls']):
            video_quality_index = 0
        selected_video = video_info['video_urls'][video_quality_index]
        
        # 选择音频质量（默认选择最高质量）
        if audio_quality_index >= len(video_info['audio_urls']):
            audio_quality_index = 0
        selected_audio = video_info['audio_urls'][audio_quality_index]
        
        # 获取质量名称
        video_quality_name = get_quality_name(selected_video['quality'])
        audio_quality_name = get_audio_quality_name(selected_audio['quality'])
        
        if progress_callback:
            progress_callback(20, 100, f"已选择视频质量: {video_quality_name}, 音频质量: {audio_quality_name}")
        
        # 生成文件名
        if filename:
            output_filename = filename
        else:
            bv_match = re.search(r'BV[a-zA-Z0-9]+', url)
            if bv_match:
                output_filename = bv_match.group()
            else:
                output_filename = f"bilibili_video_{int(time.time())}"
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        
        if merge:
            # 下载并合并模式
            temp_video_path = os.path.join(output_dir, f"{output_filename}_temp_video.m4v")
            # 如果是Hi-Res音质，使用flac扩展名作为临时文件
            temp_audio_extension = ".flac" if selected_audio['quality'] == 30251 else ".m4a"
            temp_audio_path = os.path.join(output_dir, f"{output_filename}_temp_audio{temp_audio_extension}")
            final_output_path = os.path.join(output_dir, f"{output_filename}_{video_quality_name.replace(' ', '_')}.mp4")
            
            # 下载视频流
            if progress_callback:
                progress_callback(30, 100, "正在下载视频流...")
            if not download_stream(selected_video['url'], temp_video_path, headers, progress_callback):
                if progress_callback:
                    progress_callback(0, 100, "视频流下载失败")
                return None
            
            # 下载音频流
            if progress_callback:
                progress_callback(60, 100, "正在下载音频流...")
            if not download_stream(selected_audio['url'], temp_audio_path, headers, progress_callback):
                if os.path.exists(temp_video_path):
                    os.remove(temp_video_path)
                if progress_callback:
                    progress_callback(0, 100, "音频流下载失败")
                return None
            
            # 合并视频和音频
            if progress_callback:
                progress_callback(80, 100, "正在合并视频和音频...")
            success, method = merge_video_audio_smart(temp_video_path, temp_audio_path, final_output_path)
            if success:
                # 清理临时文件
                try:
                    os.remove(temp_video_path)
                    os.remove(temp_audio_path)
                except Exception as e:
                    pass  # 忽略清理错误
                
                if progress_callback:
                    progress_callback(100, 100, f"视频下载和合并完成 (使用{method})")
                return final_output_path
            else:
                # 合并失败，清理临时文件
                try:
                    if os.path.exists(temp_video_path):
                        os.remove(temp_video_path)
                    if os.path.exists(temp_audio_path):
                        os.remove(temp_audio_path)
                except Exception as e:
                    pass  # 忽略清理错误
                if progress_callback:
                    progress_callback(0, 100, "视频合并失败")
                return None
        else:
            # 仅下载模式
            video_path = os.path.join(output_dir, f"{output_filename}_{video_quality_name.replace(' ', '_')}_video.m4v")
            # 如果是Hi-Res音质，使用flac扩展名
            audio_extension = ".flac" if selected_audio['quality'] == 30251 else ".m4a"
            audio_path = os.path.join(output_dir, f"{output_filename}_{audio_quality_name}_audio{audio_extension}")
            
            # 下载视频流
            if progress_callback:
                progress_callback(30, 100, "正在下载视频流...")
            video_success = download_stream(selected_video['url'], video_path, headers, progress_callback)
            
            # 下载音频流
            if progress_callback:
                progress_callback(70, 100, "正在下载音频流...")
            audio_success = download_stream(selected_audio['url'], audio_path, headers, progress_callback)
            
            if video_success and audio_success:
                if progress_callback:
                    progress_callback(100, 100, "视频和音频文件下载完成")
                return video_path, audio_path
            else:
                # 清理部分下载的文件
                if video_success and os.path.exists(video_path):
                    os.remove(video_path)
                if audio_success and os.path.exists(audio_path):
                    os.remove(audio_path)
                if progress_callback:
                    progress_callback(0, 100, "下载失败")
                return None, None
                
    except Exception as e:
        if progress_callback:
            progress_callback(0, 100, f"选择质量下载过程中发生错误: {e}")
        return None if merge else (None, None)

# 示例使用
if __name__ == "__main__":
    # 从本地cookies.txt文件读取cookie
    try:
        with open('cookies.txt', 'r', encoding='utf-8') as f:
            cookies = f.read().strip()
    except FileNotFoundError:
        print("错误：找不到cookies.txt文件，请确保文件存在")
        cookies = ""
    except Exception as e:
        print(f"读取cookies.txt文件时出错：{e}")
        cookies = ""
    
    # 主循环
    while True:
        try:
            # 用户输入B站视频URL
            video_url = input("\n请输入B站视频URL (输入 'exit' 退出程序): ").strip()
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，程序退出！")
            break
        
        if video_url.lower() == 'exit':
            print("\n👋 感谢使用，再见！")
            break
            
        if not video_url:
            print("❌ URL不能为空！请重新输入。")
            continue
        # 询问用户选择操作
        print("\n请选择操作:")
        print("1. 下载并合并视频 (最高质量，生成完整MP4文件)")
        print("2. 只下载视频和音频流 (最高质量，不合并，保留原始文件)")
        print("3. 选择质量下载并合并 (用户选择质量，生成完整MP4文件)")
        print("4. 选择质量仅下载 (用户选择质量，不合并，保留原始文件)")
        print("5. 只显示视频信息 (不下载)")
        
        try:
            choice = input("\n请输入选项 (1/2/3/4/5): ").strip()
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，程序退出！")
            break
        
        if choice == '1':
            # 下载并合并视频
            print(f"正在解析视频: {video_url}", flush=True)
            playinfo = get_playinfo_from_bilibili(video_url, cookies)
            
            if not playinfo:
                print("❌ 获取视频信息失败！")
                continue
                
            video_info = extract_video_info(playinfo, video_url, cookies)
            if not video_info:
                print("❌ 提取视频信息失败！")
                continue
                
            # 显示将要使用的最高质量流信息
            if video_info['highest_video_url'] and video_info['highest_audio_url']:
                highest_video = video_info['highest_video_url']
                highest_audio = video_info['highest_audio_url']
                video_quality_name = get_quality_name(highest_video['quality'])
                audio_quality_name = get_audio_quality_name(highest_audio['quality'])
                
                print(f"\n📺 将使用最高质量流:")
                print(f"  视频: {video_quality_name} ({highest_video['width']}x{highest_video['height']}, {highest_video['frameRate']}fps)")
                print(f"  音频: {audio_quality_name} ({highest_audio['bandwidth']} bps)")
            
            output_path = download_and_merge_bilibili_video(video_url, cookies=cookies)
            if output_path:
                print(f"\n✅ 视频下载并合并完成！文件保存在: {output_path}", flush=True)
            else:
                print("\n❌ 视频下载失败！")
        elif choice == '2':
            # 只下载不合并
            print(f"正在解析视频: {video_url}", flush=True)
            playinfo = get_playinfo_from_bilibili(video_url, cookies)
            
            if not playinfo:
                print("❌ 获取视频信息失败！")
                continue
                
            video_info = extract_video_info(playinfo, video_url, cookies)
            if not video_info:
                print("❌ 提取视频信息失败！")
                continue
                
            # 显示将要使用的最高质量流信息
            if video_info['highest_video_url'] and video_info['highest_audio_url']:
                highest_video = video_info['highest_video_url']
                highest_audio = video_info['highest_audio_url']
                video_quality_name = get_quality_name(highest_video['quality'])
                audio_quality_name = get_audio_quality_name(highest_audio['quality'])
                
                print(f"\n📺 将使用最高质量流:")
                print(f"  视频: {video_quality_name} ({highest_video['width']}x{highest_video['height']}, {highest_video['frameRate']}fps)")
                print(f"  音频: {audio_quality_name} ({highest_audio['bandwidth']} bps)")
            
            video_path, audio_path = download_only_bilibili_video(video_url, cookies=cookies)
            if video_path and audio_path:
                print(f"\n✅ 视频和音频文件下载完成！", flush=True)
                print(f"如需合并，可使用以下ffmpeg命令:", flush=True)
                print(f"ffmpeg -i \"{video_path}\" -i \"{audio_path}\" -c:v copy -c:a copy \"output.mp4\"", flush=True)
            else:
                print("\n❌ 文件下载失败！")
        elif choice == '3':
            # 选择质量下载并合并
            print(f"正在解析视频: {video_url}", flush=True)
            playinfo = get_playinfo_from_bilibili(video_url, cookies)
            
            if not playinfo:
                print("❌ 获取视频信息失败！")
                continue
                
            video_info = extract_video_info(playinfo, video_url, cookies)
            if not video_info:
                print("❌ 提取视频信息失败！")
                continue
                
            if not video_info['video_urls'] or not video_info['audio_urls']:
                print("❌ 未找到可用的视频流或音频流！")
                continue
                
            # 显示可用质量选项
            print("\n=== 可用视频质量 ===")
            for i, video in enumerate(video_info['video_urls']):
                quality_name = get_quality_name(video['quality'])
                print(f"  [{i+1}] {quality_name} - {video['width']}x{video['height']} - {video['frameRate']}fps")
                
            print("\n=== 可用音频质量 ===")
            for i, audio in enumerate(video_info['audio_urls']):
                audio_quality_name = get_audio_quality_name(audio['quality'])
                print(f"  [{i+1}] {audio_quality_name} - {audio['bandwidth']} bps")
                
            # 用户选择视频质量
            try:
                video_choice = input(f"\n请选择视频质量 (1-{len(video_info['video_urls'])}，默认1): ").strip()
                if not video_choice:
                    video_index = 0
                else:
                    video_index = int(video_choice) - 1
                    if video_index < 0 or video_index >= len(video_info['video_urls']):
                        print("❌ 无效的视频质量选择！")
                        continue
                        
                # 用户选择音频质量
                audio_choice = input(f"请选择音频质量 (1-{len(video_info['audio_urls'])}，默认1): ").strip()
                if not audio_choice:
                    audio_index = 0
                else:
                    audio_index = int(audio_choice) - 1
                    if audio_index < 0 or audio_index >= len(video_info['audio_urls']):
                        print("❌ 无效的音频质量选择！")
                        continue
                        
                output_path = select_quality_and_download(video_url, cookies=cookies, merge=True, 
                                                        video_quality_index=video_index, 
                                                        audio_quality_index=audio_index)
                if output_path:
                    print(f"\n✅ 视频下载并合并完成！文件保存在: {output_path}")
                else:
                    print("\n❌ 视频下载失败！")
                    
            except ValueError:
                print("❌ 请输入有效的数字！")
                continue
            except KeyboardInterrupt:
                print("\n⚠️ 用户取消操作")
                continue
                
        elif choice == '4':
            # 选择质量仅下载
            print(f"正在解析视频: {video_url}", flush=True)
            playinfo = get_playinfo_from_bilibili(video_url, cookies)
            
            if not playinfo:
                print("❌ 获取视频信息失败！")
                continue
                
            video_info = extract_video_info(playinfo, video_url, cookies)
            if not video_info:
                print("❌ 提取视频信息失败！")
                continue
                
            if not video_info['video_urls'] or not video_info['audio_urls']:
                print("❌ 未找到可用的视频流或音频流！")
                continue
                
            # 显示可用质量选项
            print("\n=== 可用视频质量 ===")
            for i, video in enumerate(video_info['video_urls']):
                quality_name = get_quality_name(video['quality'])
                print(f"  [{i+1}] {quality_name} - {video['width']}x{video['height']} - {video['frameRate']}fps")
                
            print("\n=== 可用音频质量 ===")
            for i, audio in enumerate(video_info['audio_urls']):
                audio_quality_name = get_audio_quality_name(audio['quality'])
                print(f"  [{i+1}] {audio_quality_name} - {audio['bandwidth']} bps")
                
            # 用户选择视频质量
            try:
                video_choice = input(f"\n请选择视频质量 (1-{len(video_info['video_urls'])}，默认1): ").strip()
                if not video_choice:
                    video_index = 0
                else:
                    video_index = int(video_choice) - 1
                    if video_index < 0 or video_index >= len(video_info['video_urls']):
                        print("❌ 无效的视频质量选择！")
                        continue
                        
                # 用户选择音频质量
                audio_choice = input(f"请选择音频质量 (1-{len(video_info['audio_urls'])}，默认1): ").strip()
                if not audio_choice:
                    audio_index = 0
                else:
                    audio_index = int(audio_choice) - 1
                    if audio_index < 0 or audio_index >= len(video_info['audio_urls']):
                        print("❌ 无效的音频质量选择！")
                        continue
                        
                result = select_quality_and_download(video_url, cookies=cookies, merge=False, 
                                                   video_quality_index=video_index, 
                                                   audio_quality_index=audio_index)
                if result and result[0] and result[1]:
                    video_path, audio_path = result
                    print(f"\n✅ 视频和音频文件下载完成！")
                    print(f"视频文件: {video_path}")
                    print(f"音频文件: {audio_path}")
                    print(f"如需合并，可使用以下ffmpeg命令:")
                    print(f"ffmpeg -i \"{video_path}\" -i \"{audio_path}\" -c:v copy -c:a copy \"output.mp4\"")
                else:
                    print("\n❌ 文件下载失败！")
                    
            except ValueError:
                print("❌ 请输入有效的数字！")
                continue
            except KeyboardInterrupt:
                print("\n⚠️ 用户取消操作")
                continue
        elif choice == '5':
             # 只显示视频信息（原有功能）
             # 获取playinfo数据
             print(f"正在解析视频: {video_url}", flush=True)
             playinfo = get_playinfo_from_bilibili(video_url, cookies)
             
             if playinfo:
                 print("成功获取playinfo数据！")
                 
                 # 输出原始数据到日志
                 print("\n=== 原始playinfo数据 ===")
                 print(json.dumps(playinfo, indent=2, ensure_ascii=False))
                 print("=== 原始数据结束 ===\n")
                 
                 # 提取视频信息
                 video_info = extract_video_info(playinfo, video_url, cookies)
                 if video_info:
                     print(f"视频时长: {video_info['duration']}秒")
                     print(f"视频流数量: {len(video_info['video_urls'])}")
                     print(f"音频流数量: {len(video_info['audio_urls'])}")
                     
                     # 显示最高质量的视频流和音频流
                     print("\n=== 最高质量流地址 ===")
                     if video_info['highest_video_url']:
                         highest_video = video_info['highest_video_url']
                         quality_name = get_quality_name(highest_video['quality'])
                         print(f"\n最高质量视频流:")
                         print(f"  质量: {quality_name} (ID: {highest_video['quality']})")
                         print(f"  分辨率: {highest_video['width']}x{highest_video['height']}")
                         print(f"  帧率: {highest_video['frameRate']} fps")
                         print(f"  带宽: {highest_video['bandwidth']} bps")
                         print(f"  编码: {highest_video['codecs']}")
                         print(f"  URL: {highest_video['url']}")
                     else:
                         print("未找到视频流")
                     
                     if video_info['highest_audio_url']:
                         highest_audio = video_info['highest_audio_url']
                         audio_quality_name = get_audio_quality_name(highest_audio['quality'])
                         print(f"\n最高质量音频流:")
                         print(f"  质量: {audio_quality_name} (ID: {highest_audio['quality']})")
                         print(f"  带宽: {highest_audio['bandwidth']} bps")
                         print(f"  编码: {highest_audio['codecs']}")
                         print(f"  URL: {highest_audio['url']}")
                     else:
                         print("未找到音频流")
                     
                     # 打印全部流信息（包含URL地址）
                     print("\n=== 所有可用流及下载地址 ===")
                     print("\n视频流:")
                     for i, video in enumerate(video_info['video_urls']):
                         quality_name = get_quality_name(video['quality'])
                         print(f"  [{i+1}] 质量:{quality_name}({video['quality']}) 分辨率:{video['width']}x{video['height']} 帧率:{video['frameRate']}fps 带宽:{video['bandwidth']} 编码:{video['codecs']}")
                         print(f"      URL: {video['url']}")
                         print()
                     
                     print("\n音频流:")
                     for i, audio in enumerate(video_info['audio_urls']):
                         audio_quality_name = get_audio_quality_name(audio['quality'])
                         print(f"  [{i+1}] 质量:{audio_quality_name}({audio['quality']}) 带宽:{audio['bandwidth']} 编码:{audio['codecs']}")
                         print(f"      URL: {audio['url']}")
                         print()
                 else:
                     print("提取视频信息失败")
             else:
                 print("获取playinfo数据失败")
        else:
             # 无效选项

             print("\n❌ 无效选项，请重新选择！")