# biggest-html · 世界最最最大的 HTML

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

部署（需 Cloudflare API token 作 `CLOUDFLARE_API_TOKEN`）：

```bash
cd worker && wrangler deploy
```

线上域名：`https://biggest.lyrnox.com`（Worker Route，需 DNS CNAME 指向 workers.dev）。
