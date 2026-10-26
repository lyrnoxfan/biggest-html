# biggest-html · 单文件作品实验

## 回声工坊

把一段音乐变成自己的：先听六首原创的八小节小曲，再在八轨节奏格里删音、改音或直接弹奏。音色由生成器合成后嵌进单个 HTML；作品不加载图片、外部字体、音频服务或其他网络资源，下载后可直接打开。

每首小曲都用不同的速度、调性、织体和留白方式写成，不是同一段旋律换名。毡音钢琴、木片琴、玻璃钟、拨弦、圆低音和风琴各有音色，另有底鼓、沙鼓与细镲。可逐小节聆听、调节速度、静音和音轨音量；键盘或触屏演奏；撤销、恢复、保存到本机、导入/导出工程，并导出 44.1kHz 立体声 WAV。

### 作品文件

- 推荐手机先试 `echo-sketch.html`：约 26.1 MiB，219 个独立的可演奏 WAV 样本，24kHz 单声道，覆盖 C2–B4。较小的采样库让首次解析更快。
- 较完整的 `echo-studio.html`：约 277.1 MiB，582 个独立 WAV 样本，48kHz 立体声，含两个力度层，覆盖 C2–B5。它是本次已实测的较大版本，不代表所有设备都能顺畅打开。

两版都可直接打开；文件本身不需要安装。若浏览器没有 Web Audio，仍可查看和编辑乐谱、保存工程，但无法发声。播放由明确的点击/触键启动；页面进入后台时会停止声音。主音量有余量并经过压缩器限制峰值。每个样本均按音高、音色、力度与声道独立合成；构建器会检查样本不重复，避免附加静音或复制内容来增加大小。

### 本机生成

生成需要 Python 3、NumPy 2.4.2；生成完成的 HTML 无这些运行时依赖。

```bash
python -m pip install numpy==2.4.2
python gen/echo.py --out artifacts/echo-sketch.html --low 36 --high 71 --layers 1 --rate 24000 --mono
python gen/echo.py --out artifacts/echo-studio.html --low 36 --high 83 --layers 2 --rate 48000
python tests/verify_echo.py artifacts/echo-sketch.html
python tests/verify_echo.py artifacts/echo-studio.html
```

构建会同时生成 `.manifest.json`，记录配置、样本数、原始 WAV 字节数和各样本 SHA-256。独立验证器逐个解码嵌入样本、核对 WAV 格式、摘要和构建体积。`artifacts/` 下的 HTML 与证据不提交到 Git；CI 会上传可下载的文件。

### 实测范围与取舍

以下是在 Linux 上以本地 `file://`、断网浏览器所做的实际测试，不是用户手机的实测。Chromium 360×800 使用 4 倍 CPU 节流；1440×900 为 1 倍。Firefox 没有 CPU 节流。加载时间包括 HTML 解析与首绘；进程树 RSS 是 Playwright 驱动的各浏览器后代进程 RSS 总和（不含驱动本身），共享页可能重复计算，不能当作设备最低内存要求。

| 文件 | 浏览器 / 视口 | 加载 | 首次开始播放 | 进程树 RSS 峰值 |
|---|---|---:|---:|---:|
| 26.1 MiB sketch | Chromium / 360，4× | 1.11 s | 0.27 s | 540 MB |
| 26.1 MiB sketch | Firefox / 360 | 0.31 s | 0.41 s | 795 MB |
| 277.1 MiB studio | Chromium / 360，4× | 7.12 s | 0.40 s | 994 MB |
| 277.1 MiB studio | Firefox / 360 | 1.45 s | 1.56 s | 1,154 MB |
| 622.9 MiB 压力版 | Chromium / 360，4× | 15.64 s | 0.41 s | 1,745 MB |

最后一档只作为边界实验，不作为推荐交付；其文件超过 600 MiB、移动视口需约 16 秒才完成加载。推荐从 26.1 MiB 版开始。277.1 MiB 版在模拟器中可用，但解析耗时和内存占用明显更高；未在 Android/iOS 真机、Safari 或旧 WebView 验收，不能据桌面浏览器推断这些环境一定能打开。

测试覆盖 Chromium/Firefox 的 360px 与 1440px 视口、作品切换、逐小节播放、暂停/停止、键盘与屏幕钢琴、八轨编辑/力度/静音/速度/循环、撤销、保存、有效与无效工程导入、WAV 导出、窄屏与大字布局、页面异常和外部请求。六首示例均可选择并播放。实际导出的 WAV 为双声道 44.1kHz、非静音信号；峰值低于满刻度，避免削波。axe 自动扫描在受测页面未发现 WCAG 2.1 A/AA 违规；自动扫描不能替代辅助技术实测。

证据保存在 `artifacts/echo-sketch-browser.json`、`artifacts/echo-studio-browser.json`、`artifacts/echo-scale-results.json` 及手机/桌面截图中。完整验收步骤：

```bash
python -m unittest discover -s tests -v
python tests/verify_echo.py artifacts/echo-sketch.html
python tests/verify_echo.py artifacts/echo-studio.html
# 全浏览器尺寸矩阵（需安装 Playwright 与浏览器；Linux 无声服务器还需 PulseAudio 音频输出端）
ECHO_HTML=artifacts/echo-sketch.html .venv/bin/python tests/browser_echo.py
ECHO_HTML=artifacts/echo-studio.html .venv/bin/python tests/browser_echo.py
```

要复现较大的边界实验（非推荐手机版本）：

```bash
python gen/echo.py --out artifacts/echo-workshop.html --low 24 --high 95 --layers 3 --rate 48000
python tests/verify_echo.py artifacts/echo-workshop.html
python tests/scale_echo.py
```

CI 为 Firefox 启动 PulseAudio 空输出端，它提供真实 Web Audio 时钟与解码输出；测试读取输出分析器的非零信号，不用伪造 AudioContext 或跳过发声断言。实测没有扬声器的听音验收。

### 来源与许可

作品的六首示例乐曲、矢量插图和音色合成均为本项目原创；没有从录音或第三方数据集复制内容。代码和随构建输出的原创样本按 `gen/ECHO-LICENSE.txt` 中的 MIT 条款提供。原仓库的知识展览与 Worker 代码、数据及其许可不因本作品改变。
