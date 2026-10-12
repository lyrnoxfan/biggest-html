// biggest-html edge stitcher: concatenates static chunk assets into ONE html response.
import { CHUNKS } from "./chunks.js";

async function fetchAsset(env, name) {
  let url = "https://assets.internal/" + name;
  for (let i = 0; i < 4; i++) {
    const res = await env.ASSETS.fetch(new Request(url));
    const loc = res.headers.get("location");
    if (res.status >= 300 && res.status < 400 && loc) {
      url = new URL(loc, url).href; // dev serves extensionless paths via 307
      continue;
    }
    return res;
  }
  throw new Error("too many redirects for " + name);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return new Response(JSON.stringify({ ok: true, chunks: CHUNKS.length }), {
        headers: { "content-type": "application/json" },
      });
    }
    if (url.pathname === "/dbg") {
      return new Response("gone", { status: 410 });
    }
    const stream = new ReadableStream({
      async start(controller) {
        try {
          for (const name of CHUNKS) {
            const res = await fetchAsset(env, name);
            if (!res.ok || !res.body) {
              throw new Error("chunk missing: " + name + " status=" + res.status);
            }
            const reader = res.body.getReader();
            for (;;) {
              const { done, value } = await reader.read();
              if (done) break;
              controller.enqueue(value); // zero-copy passthrough, ~no CPU
            }
          }
          controller.close();
        } catch (e) {
          controller.error(e);
        }
      },
    });
    return new Response(stream, {
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
        "x-biggest-html-chunks": String(CHUNKS.length),
      },
    });
  },
};
