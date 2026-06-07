# -*- coding: utf-8 -*-
"""
乐转站 v5.8.6 Android 版 — 核心逻辑(提取自桌面版 V20.3.0)
音乐搜索 / 下载 / 格式转换 / 音频提取
"""

import urllib.request
import urllib.parse
import urllib.error
import re
import json
import os
import sys
import subprocess
import shutil
import threading


# ==================== 常量 ====================

APP_VERSION = "v5.8.6-android"
BASE_URL = "https://www.gequhai.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 主题配色方案
THEMES = {
    "天空蓝": {
        "bg": "#E3F0FB", "header": "#B8D9F0", "primary": "#4A90D9",
        "success": "#31C27C", "warn": "#F39C12", "danger": "#E85D75",
        "text_dark": "#2C3E50", "text_mid": "#5D6D7E",
        "card": "#FFFFFF", "play": "#ECF5FD",
        "sidebar_bg": "#2C3E50", "sidebar_active": "#4A6FA5", "sidebar_fg": "#FFFFFF",
    },
    "深蓝": {
        "bg": "#1A2A44", "header": "#243356", "primary": "#4A7FCC",
        "success": "#3AAF6B", "warn": "#E8A030", "danger": "#D9544A",
        "text_dark": "#D8DEE9", "text_mid": "#8FA0B8",
        "card": "#243356", "play": "#1E2C4A",
        "sidebar_bg": "#0F1B30", "sidebar_active": "#3A5080", "sidebar_fg": "#B8C8E0",
    },
    "夜间模式": {
        "bg": "#1E1E2E", "header": "#2D2D44", "primary": "#6C8EBF",
        "success": "#4CAF50", "warn": "#FF9800", "danger": "#E74C3C",
        "text_dark": "#C4C4D6", "text_mid": "#8A8AA2",
        "card": "#2A2A3C", "play": "#252538",
        "sidebar_bg": "#16162A", "sidebar_active": "#3D3D60", "sidebar_fg": "#A8A8BE",
    },
}

THEME_NAME = "天空蓝"


# ==================== 工具函数 ====================

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        # Try UTF-8 first, then GBK
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode("gbk", errors="ignore")


def http_post(url, data_dict, extra_headers=None, timeout=15):
    data = urllib.parse.urlencode(data_dict).encode("utf-8")
    headers = {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def find_ffmpeg():
    """在 mobile-ffmpeg 或系统 PATH 中查找 ffmpeg"""
    for name in ["ffmpeg", "ffmpeg.exe"]:
        path = shutil.which(name)
        if path:
            return path
    return None


def find_ffprobe():
    for name in ["ffprobe", "ffprobe.exe"]:
        path = shutil.which(name)
        if path:
            return path
    return None


def get_media_duration(file_path):
    """获取媒体文件时长(秒)"""
    ffprobe = find_ffprobe()
    if not ffprobe:
        return 0
    try:
        cmd = [
            ffprobe, "-v", "quiet", "-show_format", "-print_format", "json",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        info = json.loads(result.stdout)
        return float(info.get("format", {}).get("duration", 0))
    except Exception:
        return 0


# ==================== 核心功能 ====================

class MusicCore:
    """音乐搜索/下载/转换核心"""

    @staticmethod
    def search(keyword):
        """搜索歌曲,返回结果列表 [{song, artist, play_url, source}]"""
        url = f"{BASE_URL}/s/{urllib.parse.quote(keyword)}"
        html = http_get(url)
        results = []
        pattern = re.compile(
            r'<td[^>]*>\s*\d+\s*</td>\s*<td[^>]*>\s*'
            r'<a[^>]*href="(/play/\d+)"[^>]*>(.*?)</a>\s*</td>\s*'
            r'<td[^>]*>(.*?)</td>',
            re.DOTALL,
        )
        for m in pattern.finditer(html):
            song = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            artist = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            if song and artist:
                results.append({
                    "song": song,
                    "artist": artist,
                    "play_url": BASE_URL + m.group(1),
                    "source": "gequhai"
                })
        return results

    @staticmethod
    def get_play_info(play_url):
        """获取播放页面信息,返回 (play_id, mp3_type)"""
        html = http_get(play_url)
        pid = re.search(r"window\.play_id\s*=\s*'([^']+)'", html)
        if not pid:
            raise Exception("无法解析 play_id")
        mt = re.search(r"window\.mp3_type\s*=\s*(-?\d+)", html)
        return pid.group(1), int(mt.group(1)) if mt else 0

    @staticmethod
    def get_download_url(play_id, mp3_type=0):
        """获取下载直链 URL"""
        decoded_id = urllib.parse.unquote(play_id)
        result = http_post(
            f"{BASE_URL}/api/music",
            {"id": decoded_id, "type": str(mp3_type)},
            extra_headers={"X-Requested-With": "XMLHttpRequest",
                           "Accept": "application/json, text/javascript, */*; q=0.01",
                           "Referer": BASE_URL},
        )
        data = json.loads(result)
        if data.get("code") == 200 and data.get("data", {}).get("url"):
            return data["data"]["url"]
        # 备用: 直接拼接
        encoded = urllib.parse.quote(play_id, safe="")
        return f"{BASE_URL}/api/music?id={encoded}&type={mp3_type}"

    @staticmethod
    def download(song_name, artist, play_url, save_dir, progress_cb=None):
        """
        下载单首歌曲,返回保存路径.
        progress_cb(percent) 为可选进度回调.
        """
        play_id, mp3_type = MusicCore.get_play_info(play_url)
        dl_url = MusicCore.get_download_url(play_id, mp3_type)

        # 生成安全文件名
        safe_name = f"{song_name} - {artist}"
        for ch in r'\/:*?"<>|':
            safe_name = safe_name.replace(ch, "_")
        safe_name = safe_name.strip()[:80]

        # 尝试多种格式重定向
        ext = ".mp3"
        # 先请求 HEAD 看响应 Content-Type
        import socket
        socket.setdefaulttimeout(15)

        try:
            req = urllib.request.Request(dl_url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
            resp = urllib.request.urlopen(req, timeout=10)
            content_type = resp.headers.get("Content-Type", "")
            resp.close()
        except Exception:
            content_type = ""

        if "flac" in content_type or dl_url.endswith(".flac"):
            ext = ".flac"
        elif "m4a" in content_type:
            ext = ".m4a"
        elif "wav" in content_type:
            ext = ".wav"
        elif "ogg" in content_type:
            ext = ".ogg"

        out_path = os.path.join(save_dir, safe_name + ext)

        # 避免重复
        counter = 1
        while os.path.exists(out_path):
            out_path = os.path.join(save_dir, f"{safe_name}_{counter}{ext}")
            counter += 1

        # 下载
        req = urllib.request.Request(dl_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total else 0
            downloaded = 0
            with open(out_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(int(downloaded / total * 100))

        # 如果下载的是非 MP3 格式,自动转 MP3
        if ext != ".mp3":
            mp3_path = out_path.rsplit(".", 1)[0] + ".mp3"
            if MusicCore.convert_audio(out_path, mp3_path, "mp3"):
                try:
                    os.remove(out_path)
                except Exception:
                    pass
                return mp3_path

        return out_path

    @staticmethod
    def convert_audio(src_path, dst_path, target_format):
        """音频格式转换,成功返回 True"""
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise Exception("ffmpeg 未安装,无法转换格式")

        codec_map = {
            "mp3": "libmp3lame", "aac": "aac", "m4a": "aac",
            "wav": "pcm_s16le", "flac": "flac", "ogg": "libvorbis",
            "wma": "wmav2", "opus": "libopus",
        }
        codec = codec_map.get(target_format, "libmp3lame")

        cmd = [
            ffmpeg, "-y", "-i", src_path,
            "-acodec", codec,
            "-b:a", "192k",
        ]
        if target_format == "mp3":
            cmd.extend(["-f", "mp3"])
        cmd.append(dst_path)

        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            return os.path.exists(dst_path) and os.path.getsize(dst_path) > 0
        except Exception:
            return False

    @staticmethod
    def convert_video(src_path, dst_path, target_format):
        """视频格式转换"""
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise Exception("ffmpeg 未安装,无法转换格式")

        codec_map = {"mp4": "libx264", "avi": "mpeg4", "mkv": "libx264",
                     "mov": "libx264", "webm": "libvpx", "wmv": "wmv2",
                     "flv": "flv", "m4v": "libx264", "3gp": "h263"}
        codec = codec_map.get(target_format, "libx264")

        cmd = [
            ffmpeg, "-y", "-i", src_path,
            "-sn", "-map", "0:v:0", "-map", "0:a?",
            "-vcodec", codec, "-pix_fmt", "yuv420p",
            "-acodec", "aac", "-b:a", "128k",
        ]
        cmd.append(dst_path)
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
            return os.path.exists(dst_path) and os.path.getsize(dst_path) > 0
        except Exception:
            return False

    @staticmethod
    def extract_audio(src_path, dst_path, target_format="mp3"):
        """从视频中提取音频"""
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise Exception("ffmpeg 未安装,无法提取音频")

        codec_map = {"mp3": "libmp3lame", "aac": "aac", "m4a": "aac",
                     "wav": "pcm_s16le", "flac": "flac", "ogg": "libvorbis"}
        codec = codec_map.get(target_format, "libmp3lame")

        cmd = [
            ffmpeg, "-y", "-i", src_path,
            "-vn", "-acodec", codec, "-b:a", "192k",
        ]
        if target_format == "mp3":
            cmd.extend(["-f", "mp3"])
        cmd.append(dst_path)
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            return os.path.exists(dst_path) and os.path.getsize(dst_path) > 0
        except Exception:
            return False


# ==================== 批量下载 ====================

def batch_download(song_list, save_dir, progress_cb=None, item_cb=None):
    """
    批量下载.
    song_list: [(song_name, artist), ...] 或 [song_name, ...]
    progress_cb(n, total): 整体进度
    item_cb(idx, status, path): 单首结果回调
    """
    results = []
    total = len(song_list)
    for i, item in enumerate(song_list):
        if isinstance(item, tuple):
            name, artist = item
        else:
            name = item.strip()
            artist = ""

        if not name:
            if item_cb:
                item_cb(i, "skip", "")
            if progress_cb:
                progress_cb(i + 1, total)
            continue

        try:
            keyword = f"{name} {artist}".strip() if artist else name
            search_results = MusicCore.search(keyword)
            if not search_results:
                if item_cb:
                    item_cb(i, "not_found", "")
                results.append(None)
                if progress_cb:
                    progress_cb(i + 1, total)
                continue

            best = search_results[0]
            path = MusicCore.download(best["song"], best["artist"],
                                      best["play_url"], save_dir)
            results.append(path)
            if item_cb:
                item_cb(i, "ok", path)
        except Exception as e:
            results.append(None)
            if item_cb:
                item_cb(i, "error", str(e))

        if progress_cb:
            progress_cb(i + 1, total)

    return results
