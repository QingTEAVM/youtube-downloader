# -*- coding: utf-8 -*-
"""
YouTube 视频下载器 —— yt-dlp 图形化封装（Mac 适配版）
功能：输入链接下载视频，可选清晰度（4K/1440p/1080p…）、字幕、编码；
      实时显示下载速度 / 进度 / 保存位置。默认保存到系统下载文件夹。
本文件由 Windows 版复制适配而来：自动探测 Mac 上的 ffmpeg / node / 保存目录。
"""
import os
import re
import socket
import subprocess
import sys
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ---------------- 常量与探测 ----------------
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Downloads")  # Mac 默认下载文件夹

_PACK = getattr(sys, "_MEIPASS", None)

# Mac 版路径探测：优先打包内置，其次常见安装位置（brew / 系统目录）
FFMPEG_CANDIDATES = [
    (os.path.join(_PACK, "ffmpeg") if _PACK else None),
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/usr/bin/ffmpeg",
]
FFPROBE_CANDIDATES = [
    (os.path.join(_PACK, "ffprobe") if _PACK else None),
    "/opt/homebrew/bin/ffprobe",
    "/usr/local/bin/ffprobe",
    "/usr/bin/ffprobe",
]

NODE_CANDIDATES = [
    (os.path.join(_PACK, "node") if _PACK else None),
    "/opt/homebrew/bin/node",
    "/usr/local/bin/node",
    "/usr/bin/node",
]


def find_node():
    """查找可用的 node.js 运行时（yt-dlp 处理 YouTube 验证挑战需要）"""
    for p in NODE_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    for p in os.environ.get("PATH", "").split(os.pathsep):
        cand = os.path.join(p, "node")
        if os.path.isfile(cand):
            return cand
    return None

QUALITY_OPTIONS = ["最高画质（自动）", "2160p 4K", "1440p 2K", "1080p", "720p", "480p", "360p"]
ENCODING_OPTIONS = [
    "自动（推荐）",
    "H.264（最兼容）",
    "AV1（体积小，需装扩展）",
    "VP9（需装扩展）",
]
SUB_LANG_OPTIONS = ["简体中文", "英文", "简体中文+英文", "全部语言"]
AUDIO_FORMAT_OPTIONS = ["MP3", "M4A", "WAV"]
SUB_FMT_OPTIONS = ["SRT", "TXT", "LRC"]

# Mac 版图标：开发模式窗口图标在 Mac 上由系统管理，无需设置；
# 打包为 .app 时使用 app.icns（见 Mac 使用说明）
ICON_PATH = None  # Mac 版窗口图标由系统管理；打包 .app 用 app.icns
BRAND = "卿捻酒ai开发 · 免费分享，请勿倒卖"
# 注：Windows 版的 LOGO_PNG 常量在 Mac 版中已移除（界面不再显示 logo 图片）

HEIGHT_MAP = {
    "最高画质（自动）": 2160,
    "2160p 4K": 2160,
    "1440p 2K": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}
LANG_MAP = {
    "简体中文": ["zh", "zh-Hans"],
    "英文": ["en", "en-US"],
    "简体中文+英文": ["zh", "zh-Hans", "en"],
    "全部语言": ["all"],
}

# 常见语言代码 → 中文名（用于“检测字幕语言”后的显示）
LANG_NAMES = {
    "zh": "中文", "zh-Hans": "中文（简体）", "zh-Hant": "中文（繁体）",
    "en": "英文", "ko": "韩语", "ja": "日语", "es": "西班牙语",
    "fr": "法语", "de": "德语", "ru": "俄语", "vi": "越南语",
    "th": "泰语", "id": "印尼语", "ar": "阿拉伯语", "pt": "葡萄牙语",
    "it": "意大利语", "nl": "荷兰语", "tr": "土耳其语", "hi": "印地语",
    "ms": "马来语", "fil": "菲律宾语", "pl": "波兰语", "uk": "乌克兰语",
    "he": "希伯来语", "sv": "瑞典语", "no": "挪威语", "da": "丹麦语",
    "fi": "芬兰语", "cs": "捷克语", "hu": "匈牙利语", "ro": "罗马尼亚语",
}


def find_tool(candidates):
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def detect_proxy():
    """扫描常见代理端口 / 系统代理，返回代理地址或空字符串"""
    for port in (7892, 7890, 10809, 10808, 1080, 8888):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.3)
            s.close()
            return "http://127.0.0.1:%d" % port
        except OSError:
            continue
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if enable and server:
            return "http://" + server
    except Exception:
        pass
    return ""


# ---------------- 主界面 ----------------
class DownloaderApp:
    def __init__(self, root):
        self.root = root
        root.title("YouTube 视频下载器")
        root.geometry("760x760")
        root.minsize(700, 700)

        self.ffmpeg = find_tool(FFMPEG_CANDIDATES)
        self.ffprobe = find_tool(FFPROBE_CANDIDATES)
        self.node = find_node()
        self.msg_q = queue.Queue()
        self.busy = False

        # 窗口图标（Mac 上由系统管理，打包为 .app 时使用 app.icns）
        ico = None
        if hasattr(sys, "_MEIPASS"):
            cand = os.path.join(sys._MEIPASS, "app.icns")
            if os.path.isfile(cand):
                ico = cand
        elif ICON_PATH and os.path.isfile(ICON_PATH):
            ico = ICON_PATH
        if ico:
            try:
                root.iconbitmap(ico)
            except Exception:
                pass

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass

        pad = {"padx": 8, "pady": 5}
        frm = ttk.Frame(root, padding=10)
        frm.pack(fill="both", expand=True)

        # 链接
        ttk.Label(frm, text="视频链接（YouTube）:").grid(row=0, column=0, sticky="w", **pad)
        self.url_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.url_var, width=70).grid(row=0, column=1, columnspan=3, sticky="we", **pad)

        # 清晰度 / 编码
        ttk.Label(frm, text="清晰度:").grid(row=1, column=0, sticky="w", **pad)
        self.quality_var = tk.StringVar(value="最高画质（自动）")
        self.quality_box = ttk.Combobox(frm, textvariable=self.quality_var, values=QUALITY_OPTIONS,
                                        state="readonly", width=16)
        self.quality_box.grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(frm, text="编码:").grid(row=1, column=2, sticky="e", **pad)
        self.encoding_var = tk.StringVar(value=ENCODING_OPTIONS[0])
        self.encoding_box = ttk.Combobox(frm, textvariable=self.encoding_var, values=ENCODING_OPTIONS,
                                         state="readonly", width=24)
        self.encoding_box.grid(row=1, column=3, sticky="w", **pad)

        # 下载模式（三选一：视频 / 仅音频 / 仅字幕）
        ttk.Label(frm, text="下载模式:").grid(row=2, column=0, sticky="w", **pad)
        mode_frame = ttk.Frame(frm)
        mode_frame.grid(row=2, column=1, columnspan=2, sticky="w", **pad)
        self.mode_var = tk.StringVar(value="video")
        ttk.Radiobutton(mode_frame, text="下载视频", variable=self.mode_var, value="video",
                        command=self._toggle_mode).pack(side="left")
        ttk.Radiobutton(mode_frame, text="仅下载音频", variable=self.mode_var, value="audio",
                        command=self._toggle_mode).pack(side="left", padx=14)
        ttk.Radiobutton(mode_frame, text="仅下载字幕", variable=self.mode_var, value="sub",
                        command=self._toggle_mode).pack(side="left", padx=14)
        ttk.Button(frm, text="检测字幕语言", command=self._detect_subs).grid(row=2, column=3, sticky="w", **pad)

        # 附加选项（随模式切换显示）
        self.sub_var = tk.BooleanVar(value=False)
        self.sub_check = ttk.Checkbutton(frm, text="附带下载字幕", variable=self.sub_var,
                                         command=self._toggle_sub)
        self.sub_check.grid(row=3, column=0, sticky="w", **pad)
        self.lang_var = tk.StringVar(value=SUB_LANG_OPTIONS[0])
        self.lang_box = ttk.Combobox(frm, textvariable=self.lang_var, values=SUB_LANG_OPTIONS,
                                     state="disabled", width=20)
        self.lang_box.grid(row=3, column=1, sticky="w", **pad)
        self.sub_fmt_var = tk.StringVar(value=SUB_FMT_OPTIONS[0])
        self.sub_fmt_box = ttk.Combobox(frm, textvariable=self.sub_fmt_var, values=SUB_FMT_OPTIONS,
                                        state="disabled", width=8)
        # 字幕格式框默认隐藏，仅『仅下载字幕』模式显示
        self.audio_fmt_var = tk.StringVar(value=AUDIO_FORMAT_OPTIONS[0])
        self.audio_fmt_box = ttk.Combobox(frm, textvariable=self.audio_fmt_var, values=AUDIO_FORMAT_OPTIONS,
                                          state="disabled", width=8)
        # 音频格式框默认隐藏，仅『仅下载音频』模式显示
        self.mode_hint = tk.StringVar(value="视频模式：可勾选『附带下载字幕』")
        ttk.Label(frm, textvariable=self.mode_hint, foreground="#666").grid(row=3, column=3, sticky="w", **pad)

        # 保存位置
        ttk.Label(frm, text="保存位置:").grid(row=4, column=0, sticky="w", **pad)
        self.dir_var = tk.StringVar(value=DEFAULT_DIR)
        ttk.Entry(frm, textvariable=self.dir_var, width=55).grid(row=4, column=1, columnspan=2, sticky="we", **pad)
        bf = ttk.Frame(frm)
        bf.grid(row=4, column=3, sticky="w", **pad)
        ttk.Button(bf, text="浏览…", command=self._browse_dir).pack(side="left")
        ttk.Label(bf, text="（无D盘时自动改用系统下载）", foreground="#999").pack(side="left", padx=4)

        # 代理
        ttk.Label(frm, text="代理:").grid(row=5, column=0, sticky="w", **pad)
        self.proxy_var = tk.StringVar(value=detect_proxy())
        ttk.Entry(frm, textvariable=self.proxy_var, width=55).grid(row=5, column=1, columnspan=2, sticky="we", **pad)
        ttk.Label(frm, text="留空 = 直连").grid(row=5, column=3, sticky="w", **pad)

        # 开始按钮
        self.btn = ttk.Button(frm, text="开始下载", command=self._start)
        self.btn.grid(row=6, column=0, columnspan=4, sticky="we", pady=8)

        # 进度
        self.progress = ttk.Progressbar(frm, maximum=100, value=0)
        self.progress.grid(row=7, column=0, columnspan=4, sticky="we", **pad)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(frm, textvariable=self.status_var).grid(row=8, column=0, columnspan=4, sticky="w", **pad)

        # 日志
        ttk.Label(frm, text="日志:").grid(row=9, column=0, sticky="w", **pad)
        self.log_text = tk.Text(frm, height=10, state="disabled", wrap="word")
        self.log_text.grid(row=10, column=0, columnspan=4, sticky="nsew", **pad)
        frm.rowconfigure(10, weight=1)
        frm.columnconfigure(1, weight=1)

        # 角落标识（防倒卖）
        ttk.Label(frm, text=BRAND, foreground="#a0a0a0").grid(row=11, column=0, columnspan=4, sticky="e", padx=8, pady=(0, 2))

        self._log("就绪。粘贴 YouTube 链接，选择下载模式，点『开始下载』。")
        self._toggle_mode()
        if self.ffmpeg:
            self._log("已找到 ffmpeg：" + self.ffmpeg)
        else:
            self._log("未找到 ffmpeg，4K/转码功能可能受限。")
        if self.node:
            self._log("已找到 node.js：" + self.node)
        else:
            self._log("未找到 node.js，高清格式解析可能受限（部分格式缺失）。")

        # 轮询消息队列
        self.root.after(100, self._poll_queue)

    # ---- UI 辅助 ----
    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _toggle_sub(self):
        """视频模式勾选『附带下载字幕』：启用语言选择，并自动检测字幕语言"""
        if self.mode_var.get() != "video":
            return
        if self.sub_var.get():
            self.lang_box.config(state="readonly")
            self.mode_hint.set("已勾选附带字幕：自动检测语言后选中，点『开始下载』即视频+字幕一起下")
            self._auto_detect_if_needed()
        else:
            self.lang_box.config(state="disabled")
            self.mode_hint.set("视频模式：可勾选『附带下载字幕』")

    def _auto_detect_if_needed(self):
        """勾选附带字幕时自动检测可用字幕语言（若链接已填且未检测过）"""
        url = self.url_var.get().strip()
        if not url:
            self.msg_q.put(("log", "提示：粘贴视频链接后，会自动检测可用的字幕语言。"))
            return
        if self.busy:
            return
        if "·" in self.lang_var.get():
            return  # 已经是检测结果，不重复检测
        self._detect_subs()

    def _toggle_mode(self):
        """下载模式切换：video / audio / sub，联动各控件的显隐与可用性"""
        m = self.mode_var.get()
        if m == "video":
            self.quality_box.config(state="readonly")
            self.encoding_box.config(state="readonly")
            self.sub_check.grid()
            self.lang_box.grid()
            self.sub_fmt_box.grid_remove()
            self.audio_fmt_box.grid_remove()
            self.mode_hint.set("视频模式：可勾选『附带下载字幕』")
            self._toggle_sub()
        elif m == "audio":
            self.quality_box.config(state="disabled")
            self.encoding_box.config(state="disabled")
            self.sub_check.grid_remove()
            self.lang_box.grid_remove()
            self.sub_fmt_box.grid_remove()
            self.audio_fmt_box.grid(row=3, column=1, sticky="w", padx=8, pady=5)
            self.audio_fmt_box.config(state="readonly")
            self.mode_hint.set("音频模式：只下载声音（不下载画面）")
        else:  # sub
            self.quality_box.config(state="disabled")
            self.encoding_box.config(state="disabled")
            self.sub_check.grid_remove()
            self.lang_box.grid()
            self.lang_box.config(state="readonly")
            self.sub_fmt_box.grid(row=3, column=2, sticky="w", padx=8, pady=5)
            self.sub_fmt_box.config(state="readonly")
            self.audio_fmt_box.grid_remove()
            self.mode_hint.set("字幕模式：只保存字幕文件（可选 SRT/TXT/LRC 格式）")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get() or DEFAULT_DIR)
        if d:
            self.dir_var.set(d)

    def _set_busy(self, busy):
        self.busy = busy
        self.btn.config(state="disabled" if busy else "normal")

    # ---- 核心逻辑 ----
    def build_format(self, height, enc):
        h = "[height<=%d]" % height if height else ""
        lim = ("best" + h) if height else "best"
        if enc == "H.264（最兼容）":
            return ("bestvideo%s[vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
                    "bestvideo%s+bestaudio/%s/best" % (h, h, lim))
        if enc == "AV1（体积小，需装扩展）":
            return ("bestvideo%s[vcodec^=av01]+bestaudio[acodec^=mp4a]/"
                    "bestvideo%s+bestaudio/%s/best" % (h, h, lim))
        if enc == "VP9（需装扩展）":
            return ("bestvideo%s[vcodec^=vp09]+bestaudio[acodec^=mp4a]/"
                    "bestvideo%s+bestaudio/%s/best" % (h, h, lim))
        # 自动：4K/2K 优先 AV1（体积小），1080p 及以下优先 H.264（兼容）
        if height and height >= 1440:
            return ("bestvideo%s[vcodec^=av01]+bestaudio[acodec^=mp4a]/"
                    "bestvideo%s+bestaudio/%s/best" % (h, h, lim))
        return ("bestvideo%s[vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
                "bestvideo%s+bestaudio/%s/best" % (h, h, lim))

    def _detect_subs(self):
        """检测当前视频实际可用的字幕语言，列到下拉框供选择"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请先粘贴视频链接。")
            return
        if self.busy:
            return
        self.status_var.set("正在检测字幕语言…")
        t = threading.Thread(target=self._detect_subs_worker, args=(url,), daemon=True)
        t.start()

    def _detect_subs_worker(self, url):
        try:
            import yt_dlp
        except Exception as e:
            self.msg_q.put(("log", "错误：未找到 yt-dlp（%s）" % e))
            return
        proxy = self.proxy_var.get().strip()
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "proxy": proxy or None,
            "sleep_requests": 1,  # 解析阶段请求间隔 1 秒，降低被限流概率
        }
        if self.ffmpeg:
            opts["ffmpeg_location"] = self.ffmpeg
        if self.node:
            opts["js_runtimes"] = {"node": {"path": self.node}}
        try:
            import curl_cffi  # noqa: F401
            from yt_dlp.networking.impersonate import ImpersonateTarget
            opts["impersonate"] = ImpersonateTarget.from_str("chrome")
        except Exception:
            pass
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            msg = str(e) or repr(e)
            self.msg_q.put(("log", "字幕检测失败：" + msg))
            self.status_var.set("检测失败，请看日志")
            return
        langs = set()
        for grp in ("subtitles", "automatic_captions"):
            for code in (info.get(grp) or {}):
                langs.add(code)
        langs = sorted(langs)
        if not langs:
            self.msg_q.put(("log", "该视频没有可用的字幕。"))
            self.status_var.set("未检测到字幕")
            return
        self.msg_q.put(("log", "检测到 %d 个字幕语言，已列到下拉框：" % len(langs)))
        names = []
        for code in langs:
            display = "%s·%s" % (code, LANG_NAMES.get(code.split("-")[0], LANG_NAMES.get(code, code)))
            names.append(display)
            self.msg_q.put(("log", "  " + display))
        self.lang_box["values"] = names
        self.lang_var.set(names[0])
        self.status_var.set("检测完成，请在语言框选择后点『开始下载』")

    def _start(self):
        if self.busy:
            return
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请先粘贴视频链接。")
            return
        out_dir = self._ensure_out_dir(self.dir_var.get().strip())
        if not out_dir:
            messagebox.showwarning("提示", "保存位置不可用，请重新选择。")
            return
        if out_dir != self.dir_var.get().strip():
            self.dir_var.set(out_dir)
            self.msg_q.put(("log", "默认位置不可用，已自动改用：" + out_dir))
        self._set_busy(True)
        self.progress["value"] = 0
        self.status_var.set("开始解析…")
        t = threading.Thread(target=self._worker, args=(url,), daemon=True)
        t.start()

    @staticmethod
    def _ensure_out_dir(path):
        """确保保存目录存在；若失败（如电脑没有 D 盘），自动改用系统可用目录"""
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except Exception:
            pass
        cands = [
            os.path.join(os.path.expanduser("~"), "Downloads", "YouTube下载"),
            os.path.join(os.path.expanduser("~"), "Desktop", "YouTube下载"),
            os.path.join(os.path.expanduser("~"), "Documents", "YouTube下载"),
        ]
        for c in cands:
            try:
                os.makedirs(c, exist_ok=True)
                return c
            except Exception:
                continue
        return None

    def _worker(self, url):
        try:
            import yt_dlp
        except Exception as e:
            self.msg_q.put(("log", "错误：未找到 yt-dlp（%s）" % e))
            self.msg_q.put(("done", False))
            return
        quality = self.quality_var.get()
        encoding = self.encoding_var.get()
        mode = self.mode_var.get()
        start_ts = time.time()
        height = HEIGHT_MAP.get(quality, 2160)
        if mode == "video":
            fmt = self.build_format(height, encoding)
        else:
            fmt = "bestaudio/best"
        out_dir = self.dir_var.get().strip()
        proxy = self.proxy_var.get().strip()

        opts = {
            "outtmpl": os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s"),
            "format": fmt,
            "noplaylist": True,
            "nocheckcertificate": True,
            "proxy": proxy or None,
            "progress_hooks": [self._hook],
            "logger": _QueueLogger(self.msg_q),
            "quiet": True,
            "no_warnings": True,
            "sleep_requests": 1,  # 解析阶段请求间隔 1 秒，降低被限流概率
        }
        if mode == "video":
            opts["merge_output_format"] = "mp4"
        if self.ffmpeg:
            opts["ffmpeg_location"] = self.ffmpeg
        if self.node:
            opts["js_runtimes"] = {"node": {"path": self.node}}
        # YouTube 反爬伪装：伪装成 Chrome 浏览器，避免被限流（429）
        try:
            import curl_cffi  # noqa: F401
            from yt_dlp.networking.impersonate import ImpersonateTarget
            opts["impersonate"] = ImpersonateTarget.from_str("chrome")
        except Exception:
            pass

        # 字幕
        lang_sel = self.lang_var.get()
        if "·" in lang_sel:
            # 检测模式：直接使用所选语言代码（如 zh-Hans）
            langs = [lang_sel.split("·")[0]]
        else:
            # 固定选项：同语言只取一个代表代码（简体中文→zh、英文→en），
            # 避免一次下载多个同语言变体文件
            raw = LANG_MAP.get(lang_sel, ["zh", "zh-Hans"])
            primary = {"zh-Hans": "zh", "zh-Hant": "zh", "en-US": "en"}
            langs = []
            for c in raw:
                c2 = primary.get(c, c)
                if c2 not in langs:
                    langs.append(c2)
        if mode == "sub":
            # 仅下载字幕：跳过媒体下载，只保存字幕文件
            opts["skip_download"] = True
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitleslangs"] = langs
            if self.ffmpeg:
                opts["postprocessors"] = [{
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                }]
        elif mode == "video" and self.sub_var.get():
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitleslangs"] = langs
            if self.ffmpeg:
                opts["postprocessors"] = [{
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                }]

        # 仅音频：提取音轨并转换为选定格式
        if mode == "audio" and self.ffmpeg:
            codec = {"MP3": "mp3", "M4A": "m4a", "WAV": "wav"}.get(self.audio_fmt_var.get(), "mp3")
            pp = {"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": "192"}
            if opts.get("postprocessors"):
                opts["postprocessors"].append(pp)
            else:
                opts["postprocessors"] = [pp]

        if mode == "sub":
            # 仅下载字幕：遇到限流自动等待 60 秒重试（最多 2 次尝试）
            err = None
            for attempt in range(2):
                err = None
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        self.msg_q.put(("log", "仅下载字幕模式，将只保存字幕文件，不下载视频和音频。"))
                        info = ydl.extract_info(url, download=True)
                    break
                except Exception as e:
                    err = e
                    msg = str(e) or repr(e)
                    if "429" in msg and attempt == 0:
                        self.msg_q.put(("log", "⚠ 遇到限流(429)，60 秒后自动重试…"))
                        time.sleep(60)
                    else:
                        break
            if err is not None:
                msg = str(err) or repr(err)
                if "429" in msg:
                    self.msg_q.put(("log", "⚠ YouTube 限流了（HTTP 429）：请等待 1-2 分钟再重试，或先下载其他视频。"))
                self.msg_q.put(("log", "下载失败：" + msg))
                self.msg_q.put(("done", False))
                return
        else:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    if mode == "audio":
                        codec = {"MP3": "mp3", "M4A": "m4a", "WAV": "wav"}.get(self.audio_fmt_var.get(), "mp3")
                        self.msg_q.put(("log", "仅下载音频模式，将提取音轨并转换为 %s 格式。" % codec.upper()))
                        info = ydl.extract_info(url, download=True)
                    else:
                        # 先解析，提示视频源实际最高画质
                        info_pre = ydl.extract_info(url, download=False)
                        max_h = 0
                        for f in (info_pre.get("formats") or []):
                            h = f.get("height") or 0
                            if h > max_h:
                                max_h = h
                        want_h = HEIGHT_MAP.get(quality, 2160)
                        if max_h:
                            self.msg_q.put(("log", "该视频在 YouTube 上最高支持 %dp 画质。" % max_h))
                            if want_h > max_h:
                                self.msg_q.put(("log", "你选择的『%s』高于视频最高画质，将自动下载最高 %dp。" % (quality, max_h)))
                        info = ydl.extract_info(url, download=True)
            except Exception as e:
                msg = str(e) or repr(e)
                if "429" in msg:
                    self.msg_q.put(("log", "⚠ YouTube 限流了（HTTP 429）：请等待 1-2 分钟再重试，或先下载其他视频。"))
                self.msg_q.put(("log", "下载失败：" + msg))
                self.msg_q.put(("done", False))
                return

        # 是否需要转码成 H.264（自动/H.264 模式下，非 H.264 源）
        if mode == "audio":
            self._report_files(out_dir, start_ts)
            self.msg_q.put(("done", True))
            return
        if mode == "sub":
            self._convert_subtitles(out_dir, start_ts, self.sub_fmt_var.get())
            self._check_subs(out_dir, start_ts)
            self._report_files(out_dir, start_ts)
            self.msg_q.put(("log", "字幕下载完成。"))
            self.msg_q.put(("done", True))
            return
        try:
            vcodec = ""
            if info:
                vcodec = (info.get("vcodec") or "") or ""
            if not vcodec and info and info.get("requested_downloads"):
                vcodec = info["requested_downloads"][0].get("vcodec") or ""
            need_trans = (encoding != "AV1（体积小，需装扩展）" and encoding != "VP9（需装扩展）"
                          and vcodec and not vcodec.startswith("avc1"))
            if need_trans and self.ffmpeg and self.ffprobe:
                self._transcode_latest(out_dir)
            elif need_trans:
                self.msg_q.put(("log", "检测到非 H.264 编码，但未找到 ffmpeg，跳过转码。"))
        except Exception as e:
            self.msg_q.put(("log", "转码判断出错：" + str(e)))
        if mode == "video" and self.sub_var.get():
            self._convert_subtitles(out_dir, start_ts, "SRT")
            self._check_subs(out_dir, start_ts)
        self._report_files(out_dir, start_ts)
        self.msg_q.put(("done", True))

    @staticmethod
    def _srt_to_txt(srt_text):
        """SRT 文本 → TXT（去掉序号、时间码和 HTML 标签，只留字幕文字）"""
        import re
        out = []
        for block in srt_text.strip().split("\n\n"):
            for line in block.split("\n"):
                if "-->" in line:
                    continue
                if re.match(r"^\d+$", line.strip()):
                    continue
                if line.strip():
                    out.append(re.sub(r"<[^>]+>", "", line.strip()))
        return "\n".join(out) + "\n"

    @staticmethod
    def _srt_to_lrc(srt_text):
        """SRT 文本 → LRC（[mm:ss.xx]歌词格式）"""
        import re
        lines = []
        for block in srt_text.strip().split("\n\n"):
            blines = block.split("\n")
            time_line = None
            text = []
            for line in blines:
                if "-->" in line:
                    time_line = line
                elif re.match(r"^\d+$", line.strip()):
                    continue
                elif line.strip():
                    text.append(line.strip())
            if not time_line or not text:
                continue
            start = time_line.split(" --> ")[0].strip()
            m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)", start)
            if not m:
                continue
            h, mi, s, ms = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
            total = h * 3600 + mi * 60 + s
            ts = "[%02d:%02d.%02d]" % (total // 60, total % 60, ms // 10)
            txt = re.sub(r"<[^>]+>", "", " ".join(text))
            lines.append(ts + txt)
        return "\n".join(lines) + "\n"

    def _convert_subtitles(self, out_dir, since_ts, target_fmt):
        """把下载的字幕统一转为目标格式（SRT / TXT / LRC）"""
        import glob
        fmt_map = {"SRT": "srt", "TXT": "txt", "LRC": "lrc"}
        target = fmt_map.get(target_fmt, "srt")
        files = [f for f in (glob.glob(os.path.join(out_dir, "*.srt"))
                             + glob.glob(os.path.join(out_dir, "*.vtt")))
                 if os.path.getmtime(f) >= since_ts - 2]
        if not files:
            return
        for f in files:
            base = os.path.splitext(f)[0]
            ext = os.path.splitext(f)[1].lower()
            # 1) 先把非 SRT（如 VTT）转成 SRT
            srt_path = f
            if ext == ".vtt":
                srt_path = base + ".srt"
                if not self.ffmpeg:
                    self.msg_q.put(("log", "未找到 ffmpeg，无法把 VTT 转成 SRT。"))
                    continue
                r = subprocess.run([self.ffmpeg, "-y", "-i", f, srt_path],
                                   capture_output=True, timeout=300)
                if r.returncode != 0 or not os.path.isfile(srt_path):
                    self.msg_q.put(("log", "VTT 转 SRT 失败：" + os.path.basename(f)))
                    continue
                self.msg_q.put(("log", "字幕已从 VTT 转成 SRT：" + os.path.basename(srt_path)))
                os.remove(f)
            # 2) 目标 SRT：直接保留
            if target == "srt":
                continue
            # 3) 目标 TXT / LRC：从 SRT 转换
            try:
                with open(srt_path, "r", encoding="utf-8-sig") as fh:
                    text = fh.read()
            except Exception as e:
                self.msg_q.put(("log", "读取字幕失败：" + str(e)))
                continue
            out_path = base + "." + target
            if target == "txt":
                out_text = self._srt_to_txt(text)
            else:
                out_text = self._srt_to_lrc(text)
            if not out_text.strip():
                self.msg_q.put(("log", "转换后内容为空（原字幕可能无文本）。"))
                continue
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(out_text)
            self.msg_q.put(("log", "已生成 %s 字幕：%s" % (target.upper(), os.path.basename(out_path))))
            # 目标非 SRT 时删除中间 SRT，只留目标格式
            if srt_path != f and os.path.isfile(srt_path):
                os.remove(srt_path)

    def _check_subs(self, out_dir, since_ts):
        """检查字幕文件是否真的生成，没有则明确提示"""
        import glob
        subs = [f for f in (glob.glob(os.path.join(out_dir, "*.srt"))
                            + glob.glob(os.path.join(out_dir, "*.vtt"))
                            + glob.glob(os.path.join(out_dir, "*.txt"))
                            + glob.glob(os.path.join(out_dir, "*.lrc")))
                if os.path.getmtime(f) >= since_ts - 2]
        if not subs:
            self.msg_q.put(("log", "⚠ 未生成字幕文件：该视频可能没有所选语言的字幕，可更换语言或稍后重试。"))

    def _report_files(self, out_dir, since_ts):
        """列出本次任务实际生成的文件，并显示完整路径"""
        import glob
        exts = ("*.mp4", "*.mkv", "*.webm", "*.mp3", "*.m4a", "*.wav", "*.srt", "*.vtt")
        files = []
        for ext in exts:
            files += glob.glob(os.path.join(out_dir, ext))
        files = [f for f in files if os.path.getmtime(f) >= since_ts - 2]
        files.sort(key=os.path.getmtime, reverse=True)
        if not files:
            self.msg_q.put(("log", "完成。文件保存在：" + out_dir))
            return
        self.msg_q.put(("log", "已保存文件："))
        for f in files[:3]:
            self.msg_q.put(("log", "  " + f))
        if len(files) > 3:
            self.msg_q.put(("log", "  …共 %d 个文件（均在 %s）" % (len(files), out_dir)))

    def _transcode_latest(self, out_dir):
        """把目录下刚下载的 mp4 转成 H.264，成功则替换原文件"""
        import glob
        files = [f for f in glob.glob(os.path.join(out_dir, "*.mp4"))
                 if not f.lower().endswith("(h264).mp4")]
        if not files:
            return
        files.sort(key=os.path.getmtime, reverse=True)
        src = files[0]
        tmp = src[:-4] + "_h264_tmp.mp4"
        self.msg_q.put(("status", "正在转码为 H.264（通用编码），请稍候…"))
        self.msg_q.put(("log", "转码：" + os.path.basename(src)))
        cmd = [self.ffmpeg, "-y", "-i", src, "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", tmp]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=3600)
            if r.returncode != 0 or not os.path.isfile(tmp):
                self.msg_q.put(("log", "转码失败，保留原文件（可尝试换编码选项）。"))
                if os.path.isfile(tmp):
                    os.remove(tmp)
                return
            os.remove(src)
            os.rename(tmp, src)
            self.msg_q.put(("log", "转码完成，文件已替换为 H.264 通用编码。"))
        except Exception as e:
            self.msg_q.put(("log", "转码异常：" + str(e)))
            if os.path.isfile(tmp):
                os.remove(tmp)

    def _hook(self, d):
        st = d.get("status")
        if st == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = (done * 100.0 / total) if total else 0
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0
            fn = os.path.basename(d.get("filename") or "")
            spd = ("%.1f MB/s" % (speed / 1048576)) if speed else "--"
            eta_s = "%d:%02d" % (eta // 60, eta % 60) if eta else "--:--"
            self.msg_q.put(("progress", (pct, "%s  %s  剩余 %s" % (spd, fn, eta_s))))
        elif st == "finished":
            self.msg_q.put(("status", "下载完成，正在合并音视频…"))

    def _poll_queue(self):
        try:
            while True:
                item = self.msg_q.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._log(item[1])
                elif kind == "status":
                    self.status_var.set(item[1])
                elif kind == "progress":
                    pct, text = item[1]
                    self.progress["value"] = pct
                    self.status_var.set(text)
                elif kind == "done":
                    ok = item[1]
                    self._set_busy(False)
                    if ok:
                        self.progress["value"] = 100
                        self.status_var.set("全部完成 ✅ 文件在：" + self.dir_var.get().strip())
                        self._log("完成！")
                    else:
                        self.status_var.set("失败，请看日志")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


class _QueueLogger:
    def __init__(self, q):
        self.q = q

    def debug(self, msg):
        pass

    def info(self, msg):
        self.q.put(("log", msg))

    def warning(self, msg):
        self.q.put(("log", "[警告] " + msg))

    def error(self, msg):
        self.q.put(("log", "[错误] " + msg))


def main():
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
