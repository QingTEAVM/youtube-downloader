# YouTube 下载器（Mac 版）

免费分享的 YouTube 视频 / 音频 / 字幕下载工具，配套浏览器插件自动传递登录 Cookie。
本仓库通过 GitHub Actions 在云端编译，自动产出 **Apple Silicon（arm64）** 和 **Intel（x86_64）** 两个版本。

## 产物怎么选

在 Actions 最新一次成功运行里下载对应产物：

| 对方芯片（关于本机里看） | 下载产物 |
| --- | --- |
| Apple M1 / M2 / M3 / M4 / M5 | `YouTubeDownloader-Mac-arm64` |
| Intel 处理器 | `YouTubeDownloader-Mac-Intel` |

## 使用要点

1. 解压后首次**右键点 app → 打开**（软件未做苹果签名，绕开安全提示，之后可双击）。
2. 在浏览器扩展页开启开发者模式，加载 `browser-extension` 文件夹。
3. 打开 YouTube 视频页，点插件把实时登录 Cookie 传给下载器，再回软件粘贴链接。
4. ffmpeg / ffprobe 已静态内置，无需用户自行安装。

## 仓库结构

```
.github/workflows/build.yml      # 云端双架构编译流程
YouTube下载器_mac.py              # Mac 主程序（Tkinter）
app.icns                         # app 图标
叮一声，完成提示.mp3              # 完成提示音
Mac版使用说明.txt                 # 详细使用说明
browser-extension/               # 浏览器插件（传 Cookie）
```

## 重新编译

推送 main 即自动触发；也可在 Actions 页面手动 `Run workflow`。
- arm64 跑在 `macos-14`，Intel 跑在 `macos-15-intel`。
- ffmpeg/ffprobe 用 npm 静态包（`ffmpeg-static`、`@ffprobe-installer/ffprobe`），无外部动态库依赖。

> 免费分享，请勿倒卖。
