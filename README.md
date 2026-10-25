# biggest-html · 世界最最最大的 HTML

## 新作品：万象折页 / The Folded Atlas

一个可以离线打开的、纸本图鉴风格的大型虚构群岛。每座岛屿有固定编号、
种子、程序地形图、气候档案与十二个月的模拟温度。支持八类地貌、编号跳转、
随机探索、深链接和本地收藏。没有真实地理数据、外部照片、字体、框架或网络依赖。
所有数据明确是创作，不能用于导航或科学判断。

它沿用“一个大 HTML”的目标，但不以无意义填充或世界纪录为目标：
把完整的可探索记录装进一个文件，只展开一个小窗口。原知识展览生成器、
Worker 与部署配置原样保留；这次没有替换线上站点。

### 生成与打开

只需 Python 3 标准库，不需要 Node、打包器或服务端。

```bash
# 推荐先用这个版本：65,536 条档案，约 7.2 MiB
python3 gen/atlas.py
# 解锁大型版：262,144 条档案，约 28.8 MiB
python3 gen/atlas.py --count 262144 --html artifacts/folded-atlas-large.html
```

生成的 HTML 是成品：用现代浏览器直接打开，断网也能运行。默认版优先照顾
移动设备，大型版增加真实档案而不是更多常驻卡片。不推荐一开始就在低内存
设备上打开大型版。`--count` 仅允许 256 的倍数，范围 256–262144；不默认
无限膨胀。生成文件继续遵循本仓库“不把构建产物提交进 Git”的约定，PR 的
`folded-atlas` Actions 任务会上传两个可下载成品与测试证据。

如果之后想使用现有 Worker 的拼接管线，可显式生成分片和清单：

```bash
python3 gen/atlas.py --count 262144 --html artifacts/folded-atlas-large.html \
  --out worker/chunks --worker-src worker/src --chunk-mib 20
```

该命令会改写生成目录和清单，不会部署。每片不超过设定的 1–24 MiB，
拼接的字节与单文件一致。线上可用性仍取决于 Cloudflare 账户、额度与配置。

### 性能边界：大文件不等于大活动页面

- 记录是每 256 条一块的惰性 JSON，不在页面启动时执行数十万次数组追加。
- 只解码当前需要的块；LRU 最多 4 块，即 1024 条已解码记录。
- 索引固定最多 24 张卡片，无无限滚动、全表排序或逐项扫描筛选。
- 完整原始文本仍由浏览器保存。DOM 中有每块一个惰性 script 节点，节点数与
  文件规模有关；这里限制的是交互 DOM 和解码工作集，绝不声称总内存恒定。
- 地图只画当前岛屿，画布宽度上限 720 像素；节能模式/可识别的 ≤4 GB
  设备上限 360。忽略高 DPR 的像素倍增，无常驻帧循环，窗口缩放有防抖。
- 无外部请求、音视频、巨图解码或后台动画。支持窄屏、暗色、键盘和减少动态。
- 收藏最多 100 条；存储被禁用时退化为本次会话收藏，不阻止浏览。
- HTML 必须先被浏览器解析，启动时间和原始文本内存仍随文件大小增长。
  桌面浏览器的 360px 模拟、4 倍 CPU 节流都不是 Android/iOS 真机保证。
  Safari、旧 WebView、文件管理器内置预览和极低内存设备未在本次验收中覆盖。

### 回归测试

```bash
python3 -m unittest discover -s tests -v
# 浏览器工具仅供开发测试，不进入 HTML
python3 -m venv .venv
.venv/bin/pip install playwright==1.58.0
.venv/bin/python -m playwright install --with-deps chromium firefox
mkdir -p artifacts
curl --fail --location https://cdn.jsdelivr.net/npm/axe-core@4.11.0/axe.min.js -o artifacts/axe.min.js
.venv/bin/python tests/browser_atlas.py
ATLAS_HTML=artifacts/folded-atlas-large.html .venv/bin/python tests/browser_atlas.py
```

请先生成上面的两个 HTML。浏览器脚本使用断网环境，覆盖 Chromium/Firefox ×
360/1440px，Chromium 另加 4 倍 CPU 节流；检查分类、末页跳转、随机、深链接、
收藏/撤销/空收藏、禁止存储、大字体溢出、键盘焦点、低分辨率与 150 页遍历。
存在 axe 脚本时执行 WCAG 2.1 A/AA 自动检查；自动检查不能代替屏幕阅读器实测。
JSON 报告与截图写入 `artifacts/`，含初始节点数、卡片数、缓存、加载时间、
控制台错误和外部请求。载入时间仅代表执行测试的环境，不是设备速度承诺。

---

纯代码、零素材的知识宇宙展览站：单个 HTML 由 N 个 ≤25MiB 静态分片组成，
Cloudflare Worker 在边缘把分片拼接成**一次** `text/html` 响应发出。

- `gen/build.py` — 生成器：读真实数据集（GeoNames / Unihan / HYG / π），
  输出 `worker/chunks/chunk-*.html` + `worker/src/chunks.js`（分片清单）
- `worker/` — Worker 源码（wrangler 部署；`worker/chunks/` 是构建产物，不进仓）
- `data/` — 原始数据集（不进仓，见 `.gitignore`）

构建：

```bash
python3 gen/build.py --data /path/to/data --out worker/chunks \
    --worker-src worker/src [--max-cities N] [--pi-digits 100000] [--chunk-mib 20]
```

测试（仅需 Python 3）：

```bash
python3 -m unittest discover -s tests -v
```

部署（需 Cloudflare API token 作 `CLOUDFLARE_API_TOKEN`）：

```bash
cd worker && wrangler deploy
```

线上域名：`https://your-domain.example.com`（Worker Route，需 DNS CNAME 指向 workers.dev）。
