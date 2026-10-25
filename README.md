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
# 中型版：262,144 条档案，约 28.8 MiB
python3 gen/atlas.py --count 262144 --html artifacts/folded-atlas-large.html
# 可选压力版：2,097,152 条，242,968,030 字节 / 231.7 MiB
# 不推荐低内存设备；先读下方实测边界
python3 gen/atlas.py --count 2097152 --html artifacts/folded-atlas-expedition.html
```

生成的 HTML 是成品：用现代浏览器直接打开，断网也能运行。默认版优先照顾
移动设备，更大版本增加完整的虚构档案而不是更多常驻卡片。不推荐一开始就在低内存
设备上打开大型版。`--count` 仅允许 256 的倍数，范围 256–2097152；不默认
无限膨胀。生成文件继续遵循本仓库“不把构建产物提交进 Git”的约定，PR 的
`folded-atlas` Actions 任务会上传三个可下载成品与测试证据。

如果之后想使用现有 Worker 的拼接管线，可显式生成分片和清单：

```bash
python3 gen/atlas.py --count 262144 --html artifacts/folded-atlas-large.html \
  --out worker/chunks --worker-src worker/src --chunk-mib 20
```

该命令会改写生成目录和清单，不会部署。每片不超过设定的 1–24 MiB，
拼接的字节与单文件一致。线上可用性仍取决于 Cloudflare 账户、额度与配置。

### 性能边界：大文件不等于大活动页面

- 记录是每 256 条一块的惰性 JSON，不在页面启动时执行数百万次数组追加。
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

### 大文件实验：不是只把目标缩成小网页

压力版是 **242,968,030 字节（231.7 MiB / 243.0 MB）** 的单一 HTML，
含 2,097,152 条按编号可直接访问的档案。体积来自编号、名称、地形种子、
纬度、雨量、温度、主峰和十二月气候值，不是重复注释、空白或解码巨图。
档案是确定性模拟而非真实岛屿；名称会重复，编号、种子和参数区分记录。
它已经达到并超过约 226 MB 的旧作量级，但没有世界纪录声明。

一次 Linux 4 GB 测试环境（Playwright 1.58.0；Chromium 145.0.7632.6 / Firefox
146.0.1；本地 `file://`、断网、DPR 3）实测如下。启动为导航到界面就绪，包含
HTML 解析和首绘，不是单独的 JSON 解码时间；末项跳转包含输入与点击的工具开销。

| 浏览器 / 视口 | CPU 节流 | 启动 | 跳转第 2,097,152 项 | 进程树 RSS 峰值* |
|---|---:|---:|---:|---:|
| Chromium / 1440 | 1× | 2.548 s | 0.106 s | 1.37 GiB |
| Chromium / 360 | 4× | 12.882 s | 0.244 s | 1.47 GiB |
| Firefox / 1440 | 1× | 1.699 s | 0.230 s | 1.45 GiB |
| Firefox / 360 | 1× | 1.495 s | 0.204 s | 1.38 GiB |

\*每 200 ms 采样 Linux 测试驱动及全部浏览器子进程 RSS 总和，**共享页会重复计数**，
不是独占内存，不是准确的 JS 堆用量，也不是设备最低内存要求。没有通过扩大 Node
或浏览器堆上限才能打开。原始 JSON 文本必须驻留，惰性解码绝不等于免 HTML 解析或免内存。
测试结果保存于 `docs/expedition-measurement.json`，CI 会产生自己环境的新结果。

四组均完成末项跳转、收藏/撤销、八类之一筛选、随机探索、节能绘图与 150 页遍历；
零外部请求、零控制台/页面错误，无横向溢出。DOM 共 8,470 个节点，其中 8,192 个是
惰性 JSON 块；初始只解码 1 块，遍历后最多 4 块，活动卡片始终 24 张。
更完整的八类筛选、存储拒绝、暗色、大字与 axe 验收在默认/中型版执行，
压力版不冒称重跑了 axe 或真实手机测试。

**取舍：231.7 MiB 可打开，不等于适合所有设备。** 4× CPU 实测的近 13 秒启动和
原文内存成本是保留 7.2 MiB 默认版的原因。低配请选默认文件，并用“节能”绘图；
切换绘图精度只能减少画布工作，不能卸载已经加载的大文件。28.8 MiB 是中间选项，
231.7 MiB 是主动选择的规模实验，不自动推给手机。超过 2,097,152 条会明确拒绝；
未测试更大规模，不许诺任何设备都能打开，不靠无限扩容冒充成功。

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
# >226 MB 可复现压力实验（请先生成 expedition 版）
.venv/bin/python tests/scale_atlas.py
```

请先生成上面的 HTML。浏览器脚本使用断网环境，覆盖 Chromium/Firefox ×
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
