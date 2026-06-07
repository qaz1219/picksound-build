# -*- coding: utf-8 -*-
"""
乐转站 v5.8.6 Android 版 — Kivy 界面
使用方法: buildozer android debug
"""

import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.utils import platform

from core import (
    MusicCore, batch_download, find_ffmpeg, find_ffprobe,
    APP_VERSION,
)


class SearchTab(TabbedPanelItem):
    """搜索下载页"""
    def __init__(self, app, **kwargs):
        super().__init__(text="搜索下载", **kwargs)
        self.app = app
        self._search_results = []

        layout = BoxLayout(orientation="vertical", padding=10, spacing=8)

        # 搜索栏
        search_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=6)
        self.search_input = TextInput(
            hint_text="输入歌名搜索...",
            multiline=False, size_hint_x=0.75,
        )
        self.search_input.bind(on_text_validate=self._do_search)
        search_btn = Button(text="搜索", size_hint_x=0.25, background_color=(0.29, 0.56, 0.85, 1))
        search_btn.bind(on_press=self._do_search)
        search_row.add_widget(self.search_input)
        search_row.add_widget(search_btn)
        layout.add_widget(search_row)

        # 保存目录
        dir_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=36, spacing=4)
        dir_row.add_widget(Label(text="保存:", size_hint_x=None, width=50, color=(0.35, 0.35, 0.35, 1)))
        self.dir_input = TextInput(
            text=app.save_dir, readonly=True, multiline=False,
            size_hint_x=0.8,
        )
        dir_row.add_widget(self.dir_input)
        layout.add_widget(dir_row)

        # 结果列表
        self.result_scroll = ScrollView()
        self.result_grid = GridLayout(cols=1, spacing=2, size_hint_y=None)
        self.result_grid.bind(minimum_height=self.result_grid.setter("height"))
        self.result_scroll.add_widget(self.result_grid)
        layout.add_widget(self.result_scroll)

        # 按钮行
        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=6)
        self.download_btn = Button(text="下载", background_color=(0.19, 0.76, 0.49, 1))
        self.download_btn.bind(on_press=self._do_download)
        self.preview_btn = Button(text="试听", background_color=(0.95, 0.6, 0.07, 1))
        self.preview_btn.bind(on_press=self._do_preview)
        btn_row.add_widget(self.download_btn)
        btn_row.add_widget(self.preview_btn)
        layout.add_widget(btn_row)

        # 进度条
        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=8)
        layout.add_widget(self.progress)

        # 状态
        self.status_label = Label(text="就绪", size_hint_y=None, height=24, color=(0.5, 0.5, 0.5, 1))
        layout.add_widget(self.status_label)

        self.add_widget(layout)

    def _do_search(self, instance):
        keyword = self.search_input.text.strip()
        if not keyword:
            self.status_label.text = "请输入歌名"
            return

        self.status_label.text = f"正在搜索「{keyword}」..."

        def _run():
            try:
                results = MusicCore.search(keyword)
                Clock.schedule_once(lambda dt: self._on_search_done(results, keyword))
            except Exception as e:
                Clock.schedule_once(lambda dt: setattr(self.status_label, "text", f"搜索失败: {e}"))

        threading.Thread(target=_run, daemon=True).start()

    def _on_search_done(self, results, keyword):
        self._search_results = results
        self.result_grid.clear_widgets()
        if not results:
            self.status_label.text = f"未找到「{keyword}」相关歌曲"
            return

        for i, r in enumerate(results):
            label = Label(
                text=f"{i+1}. {r['song']} - {r['artist']}",
                size_hint_y=None, height=40,
                halign="left", valign="middle",
                color=(0.2, 0.2, 0.2, 1),
            )
            label.bind(size=label.setter("text_size"))
            label.index = i
            label.bind(on_touch_down=self._on_tap_result)
            self.result_grid.add_widget(label)

        self.status_label.text = f"找到 {len(results)} 首歌曲"

    def _on_tap_result(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self._selected_idx = instance.index
            self.download_btn.text = f"下载 #{instance.index+1}"
            self.preview_btn.text = f"试听 #{instance.index+1}"

    def _do_download(self, instance):
        if not hasattr(self, "_selected_idx"):
            self.status_label.text = "请先选择一首歌"
            return
        idx = self._selected_idx
        item = self._search_results[idx]
        self.status_label.text = f"正在下载「{item['song']}」..."
        self.progress.value = 0

        def _run():
            try:
                def _cb(pct):
                    Clock.schedule_once(lambda dt, p=pct: setattr(self.progress, "value", p))
                path = MusicCore.download(item["song"], item["artist"],
                                         item["play_url"], self.dir_input.text,
                                         progress_cb=_cb)
                Clock.schedule_once(lambda dt: self._on_done(path))
            except Exception as e:
                Clock.schedule_once(lambda dt: setattr(self.status_label, "text", f"下载失败: {e}"))

        threading.Thread(target=_run, daemon=True).start()

    def _on_done(self, path):
        self.progress.value = 100
        self.status_label.text = f"下载完成: {os.path.basename(path)}"

    def _do_preview(self, instance):
        self.status_label.text = "提示: 移动端请下载后播放"


class BatchTab(TabbedPanelItem):
    """批量下载页"""
    def __init__(self, app, **kwargs):
        super().__init__(text="批量下载", **kwargs)
        self.app = app
        self._cancelled = False
        self._songs = []

        layout = BoxLayout(orientation="vertical", padding=10, spacing=8)

        layout.add_widget(Label(
            text="每行输入一首歌名,或粘贴 TXT 内容",
            size_hint_y=None, height=24, color=(0.4, 0.4, 0.4, 1),
        ))

        self.batch_input = TextInput(
            hint_text="歌名1\n歌名2 - 歌手\n...",
            size_hint_y=0.4,
        )
        layout.add_widget(self.batch_input)

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=6)
        self.start_btn = Button(text="开始批量下载", background_color=(0.19, 0.76, 0.49, 1))
        self.start_btn.bind(on_press=self._do_batch)
        self.cancel_btn = Button(text="取消", background_color=(0.91, 0.36, 0.46, 1))
        self.cancel_btn.bind(on_press=self._cancel_batch)
        btn_row.add_widget(self.start_btn)
        btn_row.add_widget(self.cancel_btn)
        layout.add_widget(btn_row)

        self.batch_progress = ProgressBar(max=100, value=0, size_hint_y=None, height=8)
        layout.add_widget(self.batch_progress)

        self.batch_log = TextInput(readonly=True, size_hint_y=0.4)
        layout.add_widget(self.batch_log)

        self.add_widget(layout)

    def _do_batch(self, instance):
        text = self.batch_input.text.strip()
        if not text:
            return
        self._songs = [s.strip() for s in text.split("\n") if s.strip()]
        if not self._songs:
            return
        self._cancelled = False
        self.start_btn.disabled = True
        self.batch_log.text = ""
        self.batch_progress.value = 0

        def _run():
            def _progress(n, total):
                if self._cancelled:
                    return
                Clock.schedule_once(lambda dt, n=n, t=total: setattr(self.batch_progress, "value", int(n / t * 100)))

            def _item_cb(idx, status, path):
                if self._cancelled:
                    return
                fname = os.path.basename(path) if path else ""
                line = f"[{'OK' if status == 'ok' else '✗'}] {self._songs[idx]}  {fname}\n"
                Clock.schedule_once(lambda dt, l=line: self._append_log(l))

            results = batch_download(
                self._songs, self.app.save_dir,
                progress_cb=_progress, item_cb=_item_cb,
            )
            Clock.schedule_once(lambda dt, r=results: self._on_batch_done(r))

        threading.Thread(target=_run, daemon=True).start()

    def _cancel_batch(self, instance):
        self._cancelled = True

    def _append_log(self, text):
        self.batch_log.text += text

    def _on_batch_done(self, results):
        self.start_btn.disabled = False
        ok = sum(1 for r in results if r)
        self.batch_log.text += f"\n完成: {ok}/{len(results)} 成功"


class ConvertTab(TabbedPanelItem):
    """格式转换页"""
    def __init__(self, app, **kwargs):
        super().__init__(text="格式转换", **kwargs)
        self.app = app
        self._files = []

        layout = BoxLayout(orientation="vertical", padding=10, spacing=8)

        # 模式
        mode_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=6)
        mode_row.add_widget(Label(text="类型:", size_hint_x=0.25))
        self.mode_spinner = Spinner(
            text="音频转换", values=["音频转换", "视频转换"],
            size_hint_x=0.75,
        )
        mode_row.add_widget(self.mode_spinner)
        layout.add_widget(mode_row)

        # 目标格式
        fmt_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=6)
        fmt_row.add_widget(Label(text="格式:", size_hint_x=0.25))
        self.fmt_spinner = Spinner(
            text="mp3", values=["mp3", "aac", "m4a", "wav", "flac", "ogg", "wma", "opus"],
            size_hint_x=0.75,
        )
        fmt_row.add_widget(self.fmt_spinner)
        layout.add_widget(fmt_row)

        # 文件列表
        self.file_label = Label(
            text="未添加文件",
            size_hint_y=0.3, color=(0.4, 0.4, 0.4, 1),
        )
        layout.add_widget(self.file_label)

        # 按钮
        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=6)
        add_btn = Button(text="添加文件", background_color=(0.29, 0.56, 0.85, 1))
        add_btn.bind(on_press=self._add_files)
        clear_btn = Button(text="清空", background_color=(0.7, 0.7, 0.7, 1))
        clear_btn.bind(on_press=self._clear)
        btn_row.add_widget(add_btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        self.convert_btn = Button(text="开始转换", background_color=(0.19, 0.76, 0.49, 1))
        self.convert_btn.bind(on_press=self._do_convert)
        layout.add_widget(self.convert_btn)

        self.convert_progress = ProgressBar(max=100, value=0, size_hint_y=None, height=8)
        layout.add_widget(self.convert_progress)

        self.status_label = Label(text="就绪", size_hint_y=None, height=24, color=(0.5, 0.5, 0.5, 1))
        layout.add_widget(self.status_label)

        self.add_widget(layout)

    def _add_files(self, instance):
        # Android 上需要通过文件选择器,这里简化处理
        self.status_label.text = "请在文件管理器中分享文件到本应用"

    def _clear(self, instance):
        self._files.clear()
        self.file_label.text = "未添加文件"

    def _do_convert(self, instance):
        if not self._files:
            self.status_label.text = "请先添加文件"
            return
        self.status_label.text = "转换功能需要在完整版中使用"


class ClipTab(TabbedPanelItem):
    """音频提取页"""
    def __init__(self, app, **kwargs):
        super().__init__(text="音频提取", **kwargs)
        self.app = app

        layout = BoxLayout(orientation="vertical", padding=10, spacing=8)

        layout.add_widget(Label(
            text="从视频中提取音频",
            size_hint_y=None, height=30,
            font_size=16, bold=True,
        ))

        self.file_label = Label(
            text="未选择视频文件",
            size_hint_y=None, height=40, color=(0.4, 0.4, 0.4, 1),
        )
        layout.add_widget(self.file_label)

        select_btn = Button(text="选择视频", background_color=(0.29, 0.56, 0.85, 1))
        select_btn.bind(on_press=self._select_file)
        layout.add_widget(select_btn)

        extract_btn = Button(text="提取音频", background_color=(0.19, 0.76, 0.49, 1))
        extract_btn.bind(on_press=self._do_extract)
        layout.add_widget(extract_btn)

        self.status_label = Label(text="就绪", size_hint_y=None, height=24, color=(0.5, 0.5, 0.5, 1))
        layout.add_widget(self.status_label)

        self.add_widget(layout)

    def _select_file(self, instance):
        self.status_label.text = "请在文件管理器中分享视频到本应用"

    def _do_extract(self, instance):
        self.status_label.text = "提取功能需要在完整版中使用"


class PicksoundApp(App):
    def build(self):
        self.title = f"乐转站 {APP_VERSION}"
        self.save_dir = "/sdcard/Download/乐转站" if platform == "android" else os.path.join(
            os.path.expanduser("~"), "Downloads", "乐转站"
        )
        os.makedirs(self.save_dir, exist_ok=True)

        panel = TabbedPanel(do_default_tab=False)
        panel.default_tab_text = "搜索下载"

        panel.add_widget(SearchTab(self, text="搜索下载"))
        panel.add_widget(BatchTab(self, text="批量下载"))
        panel.add_widget(ConvertTab(self, text="格式转换"))
        panel.add_widget(ClipTab(self, text="音频提取"))

        return panel


if __name__ == "__main__":
    PicksoundApp().run()
(内容由AI生成,仅供参考)
