# -*- coding: utf-8 -*-
"""
乐转站 v5.8.6 Android 版 — Toga 界面
"""

import os
import threading
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from .core import (
    MusicCore, batch_download, find_ffmpeg, find_ffprobe,
    get_media_duration, APP_VERSION, THEME_NAME,
)


class PickSoundAndroid(toga.App):
    def startup(self):
        self.save_dir = os.path.join(
            os.path.expanduser("~"), "Downloads", "乐转站"
        )
        os.makedirs(self.save_dir, exist_ok=True)

        self._search_results = []
        self._file_list = []

        self.main_window = toga.MainWindow(title="乐转站")
        self.main_window.content = self._build_ui()
        self.main_window.show()

    # ==================== UI 构建 ====================

    def _build_ui(self):
        """构建主界面：顶部分页标签 + 内容区"""
        outer = toga.Box(style=Pack(direction=COLUMN, flex=1))

        # 顶部标题
        header = toga.Box(style=Pack(direction=ROW, padding=10, background_color="#2C3E50"))
        title = toga.Label(
            f"乐转站 {APP_VERSION}",
            style=Pack(color="#FFFFFF", font_size=16, font_weight="bold", flex=1),
        )
        header.add(title)
        outer.add(header)

        # 分页容器
        self.option_container = toga.OptionContainer(
            style=Pack(flex=1, padding=0),
        )

        self._build_search_tab()
        self._build_batch_tab()
        self._build_convert_tab()
        self._build_clip_tab()

        outer.add(self.option_container)

        # 底部状态栏
        self.status_label = toga.Label(
            "就绪 — 输入歌名搜索",
            style=Pack(padding=(5, 10), font_size=11, color="#888"),
        )
        outer.add(self.status_label)

        return outer

    # ==================== 搜索下载页 ====================

    def _build_search_tab(self):
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # 搜索栏
        search_row = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        self.search_input = toga.TextInput(
            placeholder="输入歌名搜索...",
            style=Pack(flex=1, padding=(0, 5, 0, 0)),
            on_confirm=self._do_search,
        )
        search_row.add(self.search_input)

        search_btn = toga.Button(
            "搜索", on_press=self._do_search,
            style=Pack(padding=5, width=70),
        )
        search_row.add(search_btn)
        box.add(search_row)

        # 保存目录
        dir_row = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        dir_label = toga.Label("保存到:", style=Pack(padding=(0, 5, 0, 0)))
        self.dir_input = toga.TextInput(
            value=self.save_dir,
            readonly=True,
            style=Pack(flex=1),
        )
        dir_row.add(dir_label)
        dir_row.add(self.dir_input)
        box.add(dir_row)

        # 结果列表
        self.result_table = toga.Table(
            headings=["序号", "歌曲名", "歌手"],
            style=Pack(flex=1, padding=(0, 0, 10, 0)),
            on_select=self._on_select_result,
        )
        box.add(self.result_table)

        # 操作按钮行
        btn_row = toga.Box(style=Pack(direction=ROW))
        self.download_btn = toga.Button(
            "下载选中", on_press=self._do_download,
            style=Pack(padding=5, flex=1),
            enabled=False,
        )
        self.preview_btn = toga.Button(
            "试听", on_press=self._do_preview,
            style=Pack(padding=5, flex=1),
            enabled=False,
        )
        btn_row.add(self.download_btn)
        btn_row.add(self.preview_btn)
        box.add(btn_row)

        # 进度条
        self.progress_bar = toga.ProgressBar(
            max=100, value=0,
            style=Pack(padding=(10, 0, 0, 0)),
        )
        box.add(self.progress_bar)

        self.option_container.add("搜索下载", box)

    def _do_search(self, widget):
        keyword = self.search_input.value.strip()
        if not keyword:
            self.status_label.text = "请输入歌名"
            return

        self.status_label.text = f"正在搜索「{keyword}」..."
        self.search_input.enabled = False

        def _run():
            try:
                results = MusicCore.search(keyword)
                self._search_results = results
                self.main_window._impl.loop.call_soon_threadsafe(
                    self._on_search_done, results, keyword
                )
            except Exception as e:
                self.main_window._impl.loop.call_soon_threadsafe(
                    self._on_search_error, str(e)
                )

        threading.Thread(target=_run, daemon=True).start()

    def _on_search_done(self, results, keyword):
        self.search_input.enabled = True
        self.result_table.data.clear()
        if not results:
            self.status_label.text = f"未找到「{keyword}」相关歌曲"
            self._search_results = []
            return

        for i, r in enumerate(results):
            self.result_table.data.append(
                (str(i + 1), r["song"], r["artist"])
            )
        self.status_label.text = f"找到 {len(results)} 首歌曲"

    def _on_search_error(self, err_msg):
        self.search_input.enabled = True
        self.status_label.text = f"搜索失败: {err_msg}"

    def _on_select_result(self, table, row):
        if row is not None:
            self.download_btn.enabled = True
            self.preview_btn.enabled = True
        else:
            self.download_btn.enabled = False
            self.preview_btn.enabled = False

    def _do_download(self, widget):
        sel = self.result_table.selection
        if not sel or not self._search_results:
            return
        idx = int(sel.data[0]) - 1
        item = self._search_results[idx]

        self.download_btn.enabled = False
        self.status_label.text = f"正在下载「{item['song']}」..."
        self.progress_bar.value = 0

        save_dir = self.dir_input.value or self.save_dir
        os.makedirs(save_dir, exist_ok=True)

        def _run():
            try:
                def _progress(pct):
                    self.main_window._impl.loop.call_soon_threadsafe(
                        lambda: setattr(self.progress_bar, "value", pct)
                    )
                path = MusicCore.download(
                    item["song"], item["artist"],
                    item["play_url"], save_dir,
                    progress_cb=_progress,
                )
                self.main_window._impl.loop.call_soon_threadsafe(
                    self._on_download_done, path, item["song"]
                )
            except Exception as e:
                self.main_window._impl.loop.call_soon_threadsafe(
                    self._on_download_error, str(e)
                )

        threading.Thread(target=_run, daemon=True).start()

    def _on_download_done(self, path, song_name):
        self.download_btn.enabled = True
        self.progress_bar.value = 100
        self.status_label.text = f"下载完成: {os.path.basename(path) if path else song_name}"

    def _on_download_error(self, err_msg):
        self.download_btn.enabled = True
        self.progress_bar.value = 0
        self.status_label.text = f"下载失败: {err_msg}"

    def _do_preview(self, widget):
        sel = self.result_table.selection
        if not sel or not self._search_results:
            return
        idx = int(sel.data[0]) - 1
        item = self._search_results[idx]
        self.status_label.text = f"提示: 移动端试听功能需浏览器支持，请下载后播放"

    # ==================== 批量下载页 ====================

    def _build_batch_tab(self):
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        hint = toga.Label(
            "每行输入一首歌名，或粘贴 TXT 文件内容",
            style=Pack(padding=(0, 0, 5, 0), font_size=11, color="#666"),
        )
        box.add(hint)

        self.batch_input = toga.MultilineTextInput(
            placeholder="歌名1\n歌名2 - 歌手\n...",
            style=Pack(flex=1, padding=(0, 0, 10, 0)),
        )
        box.add(self.batch_input)

        btn_row = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        self.batch_start_btn = toga.Button(
            "开始批量下载", on_press=self._do_batch_download,
            style=Pack(padding=5, flex=1),
        )
        self.batch_stop_btn = toga.Button(
            "取消", on_press=self._cancel_batch,
            style=Pack(padding=5, flex=1),
        )
        btn_row.add(self.batch_start_btn)
        btn_row.add(self.batch_stop_btn)
        box.add(btn_row)

        self.batch_progress = toga.ProgressBar(
            max=100, value=0,
            style=Pack(padding=5),
        )
        box.add(self.batch_progress)

        self.batch_log = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1),
        )
        box.add(self.batch_log)

        self.option_container.add("批量下载", box)

    def _do_batch_download(self, widget):
        text = self.batch_input.value.strip()
        if not text:
            self.status_label.text = "请输入歌名列表"
            return

        songs = [s.strip() for s in text.split("\n") if s.strip()]
        if not songs:
            self.status_label.text = "未找到有效歌名"
            return

        self._batch_cancelled = False
        self.batch_start_btn.enabled = False
        self.batch_log.value = ""
        self.batch_progress.value = 0
        self.batch_input.readonly = True

        save_dir = self.dir_input.value or self.save_dir
        os.makedirs(save_dir, exist_ok=True)

        def _run():
            def _progress(n, total):
                if self._batch_cancelled:
                    return
                self.main_window._impl.loop.call_soon_threadsafe(
                    lambda n=n, t=total: setattr(self.batch_progress, "value", int(n / t * 100))
                )
                self.main_window._impl.loop.call_soon_threadsafe(
                    lambda n=n, t=total: setattr(self.status_label, "text", f"批量下载 {n}/{t}")
                )

            def _item_cb(idx, status, path):
                if self._batch_cancelled:
                    return
                self.main_window._impl.loop.call_soon_threadsafe(
                    lambda i=idx, s=status, p=path: self._append_log(
                        f"[{'OK' if s == 'ok' else '✗'}] {songs[i]}  {os.path.basename(p) if p else ''}"
                    )
                )

            results = batch_download(songs, save_dir, progress_cb=_progress, item_cb=_item_cb)

            self.main_window._impl.loop.call_soon_threadsafe(self._on_batch_done, results)

        threading.Thread(target=_run, daemon=True).start()

    def _cancel_batch(self, widget):
        self._batch_cancelled = True
        self.status_label.text = "正在取消..."

    def _append_log(self, text):
        current = self.batch_log.value
        self.batch_log.value = (current + text + "\n") if current else (text + "\n")

    def _on_batch_done(self, results):
        self.batch_start_btn.enabled = True
        self.batch_input.readonly = False
        ok_count = sum(1 for r in results if r)
        self.status_label.text = f"批量下载完成: {ok_count}/{len(results)} 成功"

    # ==================== 格式转换页 ====================

    def _build_convert_tab(self):
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # 模式选择
        mode_row = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        mode_label = toga.Label("转换类型:", style=Pack(padding=(0, 5, 0, 0)))
        self.convert_mode = toga.Selection(
            items=["音频转换", "视频转换"],
            style=Pack(flex=1),
            on_select=self._on_convert_mode_change,
        )
        mode_row.add(mode_label)
        mode_row.add(self.convert_mode)
        box.add(mode_row)

        # 目标格式
        fmt_row = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        fmt_label = toga.Label("目标格式:", style=Pack(padding=(0, 5, 0, 0)))
        self.convert_fmt = toga.Selection(
            items=["mp3", "aac", "m4a", "wav", "flac", "ogg", "wma", "opus"],
            style=Pack(flex=1),
        )
        fmt_row.add(fmt_label)
        fmt_row.add(self.convert_fmt)
        box.add(fmt_row)

        # 文件列表
        self.convert_file_list = toga.MultilineTextInput(
            readonly=True,
            placeholder="点击「添加文件」选择要转换的文件",
            style=Pack(flex=1, padding=(0, 0, 10, 0)),
        )
        box.add(self.convert_file_list)

        # 按钮
        btn_row = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        self.convert_add_btn = toga.Button(
            "添加文件", on_press=self._convert_add_files,
            style=Pack(padding=5, flex=1),
        )
        self.convert_clear_btn = toga.Button(
            "清空列表", on_press=self._convert_clear,
            style=Pack(padding=5, flex=1),
        )
        btn_row.add(self.convert_add_btn)
        btn_row.add(self.convert_clear_btn)
        box.add(btn_row)

        self.convert_start_btn = toga.Button(
            "开始转换", on_press=self._do_convert,
            style=Pack(padding=5),
        )
        box.add(self.convert_start_btn)

        self.convert_progress = toga.ProgressBar(
            max=100, value=0,
            style=Pack(padding=5),
        )
        box.add(self.convert_progress)

        self.option_container.add("格式转换", box)

    def _on_convert_mode_change(self, widget):
        """切换音频/视频转换模式，自动更新格式列表"""
        if widget.value == "音频转换":
            self.convert_fmt.items = ["mp3", "aac", "m4a", "wav", "flac", "ogg", "wma", "opus"]
        else:
            self.convert_fmt.items = ["mp4", "avi", "mkv", "mov", "webm", "wmv", "flv", "m4v", "3gp"]
        self.convert_fmt.value = self.convert_fmt.items[0] if self.convert_fmt.items else None

    def _convert_add_files(self, widget):
        try:
            paths = self.main_window.open_file_dialog(
                "选择文件", multiselect=True,
                file_types=["mp3", "aac", "m4a", "wav", "flac", "ogg", "wma",
                           "mp4", "avi", "mkv", "mov", "webm", "wmv"],
            )
            if paths:
                for p in paths:
                    if p not in self._file_list:
                        self._file_list.append(p)
                self._update_convert_list()
        except Exception as e:
            self.status_label.text = f"选择文件失败: {e}"

    def _convert_clear(self, widget):
        self._file_list.clear()
        self._update_convert_list()

    def _update_convert_list(self):
        lines = [f"{i+1}. {os.path.basename(p)}" for i, p in enumerate(self._file_list)]
        self.convert_file_list.value = "\n".join(lines) if lines else ""

    def _do_convert(self, widget):
        if not self._file_list:
            self.status_label.text = "请先添加文件"
            return

        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            self.status_label.text = "ffmpeg 未安装，无法转换"
            return

        self.convert_start_btn.enabled = False
        self.convert_progress.value = 0
        target = self.convert_fmt.value or "mp3"
        is_video = self.convert_mode.value == "视频转换"

        save_dir = self.dir_input.value or self.save_dir
        os.makedirs(save_dir, exist_ok=True)

        def _run():
            total = len(self._file_list)
            for i, src in enumerate(self._file_list):
                base = os.path.splitext(os.path.basename(src))[0]
                ext = f".{target}"
                dst = os.path.join(save_dir, base + ext)
                # 去重
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(save_dir, f"{base}_{counter}{ext}")
                    counter += 1

                try:
                    if is_video:
                        ok = MusicCore.convert_video(src, dst, target)
                    else:
                        ok = MusicCore.convert_audio(src, dst, target)
                    status = "OK" if ok else "FAIL"
                except Exception as e:
                    status = f"ERR: {e}"

                pct = int((i + 1) / total * 100)
                fname = os.path.basename(src)
                self.main_window._impl.loop.call_soon_threadsafe(
                    lambda p=pct, f=fname, s=status, i=i, t=total:
                    self._on_convert_step(p, f, s, i + 1, t)
                )

        threading.Thread(target=_run, daemon=True).start()

    def _on_convert_step(self, pct, fname, status, n, total):
        self.convert_progress.value = pct
        self.status_label.text = f"转换 {n}/{total}: {fname} [{status}]"

    # ==================== 音频提取页 ====================

    def _build_clip_tab(self):
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        hint = toga.Label(
            "从视频文件中提取音频",
            style=Pack(padding=(0, 0, 10, 0), font_size=14, font_weight="bold"),
        )
        box.add(hint)

        # 文件选择
        file_row = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        self.clip_file_label = toga.Label(
            "未选择文件",
            style=Pack(flex=1, padding=(5, 5, 0, 0)),
        )
        self.clip_select_btn = toga.Button(
            "选择视频", on_press=self._clip_select_file,
            style=Pack(padding=5),
        )
        file_row.add(self.clip_file_label)
        file_row.add(self.clip_select_btn)
        box.add(file_row)

        # 目标格式
        fmt_row = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        fmt_label = toga.Label("输出格式:", style=Pack(padding=(0, 5, 0, 0)))
        self.clip_fmt = toga.Selection(
            items=["mp3", "aac", "m4a", "wav", "flac", "ogg"],
            style=Pack(flex=1),
        )
        fmt_row.add(fmt_label)
        fmt_row.add(self.clip_fmt)
        box.add(fmt_row)

        self.clip_extract_btn = toga.Button(
            "提取音频", on_press=self._do_extract_audio,
            style=Pack(padding=10),
        )
        box.add(self.clip_extract_btn)

        self.clip_progress = toga.ProgressBar(
            max=100, value=0,
            style=Pack(padding=(10, 0)),
        )
        box.add(self.clip_progress)

        self.option_container.add("音频提取", box)

    def _clip_select_file(self, widget):
        try:
            paths = self.main_window.open_file_dialog(
                "选择视频文件",
                file_types=["mp4", "avi", "mkv", "mov", "webm", "wmv", "flv", "m4v",
                           "ts", "mts", "m2ts", "vob", "3gp", "ogv"],
            )
            if paths:
                self._clip_file = paths[0]
                self.clip_file_label.text = os.path.basename(paths[0])
        except Exception as e:
            self.status_label.text = f"选择文件失败: {e}"

    def _do_extract_audio(self, widget):
        if not hasattr(self, "_clip_file") or not self._clip_file:
            self.status_label.text = "请先选择视频文件"
            return

        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            self.status_label.text = "ffmpeg 未安装，无法提取音频"
            return

        save_dir = self.dir_input.value or self.save_dir
        os.makedirs(save_dir, exist_ok=True)
        target = self.clip_fmt.value or "mp3"
        base = os.path.splitext(os.path.basename(self._clip_file))[0]
        dst = os.path.join(save_dir, f"{base}.{target}")

        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(save_dir, f"{base}_{counter}.{target}")
            counter += 1

        self.clip_extract_btn.enabled = False
        self.clip_progress.value = 0
        self.status_label.text = "正在提取音频..."

        def _run():
            try:
                ok = MusicCore.extract_audio(self._clip_file, dst, target)
                self.main_window._impl.loop.call_soon_threadsafe(
                    self._on_extract_done, ok, dst
                )
            except Exception as e:
                self.main_window._impl.loop.call_soon_threadsafe(
                    self._on_extract_done, False, str(e)
                )

        threading.Thread(target=_run, daemon=True).start()

    def _on_extract_done(self, ok, path):
        self.clip_extract_btn.enabled = True
        self.clip_progress.value = 100
        if ok:
            self.status_label.text = f"提取完成: {os.path.basename(path)}"
        else:
            self.status_label.text = f"提取失败: {path}"


def main():
    return PickSoundAndroid()
