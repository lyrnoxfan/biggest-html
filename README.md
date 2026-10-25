# biggest-html · 世界最最最大的 HTML

这个仓库把真实数据与代码绘图装进一个自包含页面：太阳系、地球居民点、分形与圆周率、汉字、合成音乐和世界时钟。生成器取用 GeoNames、HYG、Unicode Unihan 与原作的 NASA 行星参数；页面不靠复制图像、重复段落或空白填充增加体积。

## 生成建议版本

默认纳入按人口排序的 1,000,000 条 GeoNames 居民点记录。本次完整生成的单页 HTML 为 **38,447,020 字节（约 36.7 MiB）**，构建器默认上限也是 1,000,000 条。该规模在下文所列 Chromium 环境中完成实际打开与交互检查；这不是所有设备的兼容保证。

```bash
uv run --no-project --with mpmath==1.3.0 python gen/build.py \
  --data /path/to/data --out /tmp/big-html/chunks \
  --worker-src /tmp/big-html/worker --max-cities 1000000 \
  --pi-digits 100000 --chunk-mib 20
cat /tmp/big-html/chunks/chunk-*.html > biggest.html
```

原始数据不包含在 Git 中。`--max-cities N` 选取人口最大的 N 条 PPL 居民点记录；默认 N 为 1,000,000，生成器读取源文件时用有界堆保留结果，避免先把 500 多万条记录全部载入内存。将 N 设为 `0` 会纳入全部源记录，输出会显著增大，需另行测试目标设备。构建分片仅供生成和 Worker 传输；按清单顺序拼接后才是可直接打开的单个 HTML。

## 实测规模与体验

本次使用 GeoNames `allCountries.txt`、HYG v3、Unicode Unihan 17.0 和 100,000 位 π，生成 1,000,000 条居民点记录、8,878 条恒星记录、44,350 条汉字记录以及 100,000 位 π 小数。居民点数组中有 999,995 条不同字段组合、993,559 个不同坐标；其余是源数据中字段完全相同或坐标重合的记录，并未复制填充。地图动画最多绘制 120,000 个居民点，其余记录仍完整载入页面；以有限采样避免每帧重绘百万个点。图上的每个点对应真实坐标，人口规模决定点大小。

验收为 Linux 上的 Chromium 文件页面：离线网络条件下，360×800 视口以 4 倍 CPU 节流新开页面，完整加载 6.568 秒；1440×900 新开页面加载 2.109 秒。两次均载入 1,000,000 条居民点、8,878 条恒星、44,350 条汉字和 100,000 位 π；共有 876 个 DOM 节点、6 个 Canvas，汉字“龙”搜索和详情卡可用，地球画布有绘制像素，控制台/页面错误及外部请求均为 0。360 视口最长观察到的长任务为 252ms。浏览器自动化结果和截图来自本次 Linux Chromium 验收；CI 单独运行仓库生成器单测及 Worker dry-run。该环境不是 Android/iOS 真机；Safari、旧版 WebView、低内存设备没有测试，不能据此保证它们能打开 36.7 MiB 文件。

## 数据来源与许可

- 居民点：GeoNames `allCountries.txt` 的 PPL 记录，页面提供 GeoNames 来源及 CC BY 4.0 许可链接。
- 恒星：Astronexus HYG Database v3，页面提供来源与 CC BY-SA 4.0 许可链接；输出对记录作筛选和格式转换。
- 汉字字段：Unicode Unihan 的 `kMandarin`、`kRSUnicode`。单页内附 Unicode License V3 的版权、许可和免责声明；完整文本见 [Unicode License V3](https://www.unicode.org/license.txt)。
- 行星参数沿用原作品的 NASA 数据说明；生成页面保留其来源说明。

## 仓库结构与测试

- `gen/build.py` 生成 HTML 分片及 Worker 清单；原始数据需自行准备。
- `worker/` 是仓库原有 Cloudflare Worker；分片产物不提交。
- `tests/` 覆盖生成器基础行为、分片完整性和有界人口筛选。

```bash
python3 -m unittest discover -s tests -v
```
