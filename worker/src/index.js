import { CHUNKS, TOTAL_BYTES } from "./chunks.js";

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

function jsonResponse(body, status = 200, method = "GET") {
  return new Response(method === "HEAD" ? null : JSON.stringify(body), {
    status,
    headers: JSON_HEADERS,
  });
}

function methodNotAllowed(request) {
  return new Response(request.method === "HEAD" ? null : "Method Not Allowed", {
    status: 405,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      allow: "GET, HEAD",
    },
  });
}

async function fetchAsset(env, name, signal) {
  let url = "https://assets.internal/" + name;
  for (let i = 0; i < 4; i++) {
    const res = await env.ASSETS.fetch(new Request(url, { signal }));
    const location = res.headers.get("location");
    if (res.status >= 300 && res.status < 400 && location) {
      url = new URL(location, url).href;
      continue;
    }
    return res;
  }
  throw new Error("too many redirects for " + name);
}

function createHtmlStream(env, signal) {
  let chunkIndex = 0;
  let reader = null;

  return new ReadableStream({
    async pull(controller) {
      try {
        while (true) {
          if (signal.aborted) {
            if (reader) await reader.cancel();
            controller.close();
            return;
          }

          if (!reader) {
            if (chunkIndex >= CHUNKS.length) {
              controller.close();
              return;
            }

            const name = CHUNKS[chunkIndex];
            const response = await fetchAsset(env, name, signal);
            if (!response.ok || !response.body) {
              await response.body?.cancel();
              throw new Error("chunk missing: " + name + " status=" + response.status);
            }
            reader = response.body.getReader();
          }

          const { done, value } = await reader.read();
          if (done) {
            reader.releaseLock();
            reader = null;
            chunkIndex++;
            continue;
          }

          // Pull one body chunk at a time so downstream backpressure is respected.
          controller.enqueue(value);
          return;
        }
      } catch (error) {
        if (signal.aborted) {
          controller.close();
          return;
        }
        controller.error(error);
      }
    },
    async cancel(reason) {
      if (!reader) return;
      try {
        await reader.cancel(reason);
      } catch {
        // The client has disconnected; there is nothing else to send.
      }
      reader = null;
    },
  }, { highWaterMark: 1 });
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);

    if (pathname === "/health") {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return methodNotAllowed(request);
      }
      const ok = Array.isArray(CHUNKS) && CHUNKS.length > 0;
      return jsonResponse({ ok, chunks: CHUNKS.length }, ok ? 200 : 503, request.method);
    }

    if (pathname === "/dbg") {
      return new Response(request.method === "HEAD" ? null : "gone", {
        status: 410,
        headers: { "cache-control": "no-store" },
      });
    }

    if (pathname !== "/" && pathname !== "/index.html") {
      return new Response(request.method === "HEAD" ? null : "Not Found", {
        status: 404,
        headers: {
          "content-type": "text/plain; charset=utf-8",
          "cache-control": "no-store",
        },
      });
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      return methodNotAllowed(request);
    }

    if (!Array.isArray(CHUNKS) || CHUNKS.length === 0) {
      return new Response(request.method === "HEAD" ? null : "HTML chunks are not built", {
        status: 503,
        headers: {
          "content-type": "text/plain; charset=utf-8",
          "cache-control": "no-store",
        },
      });
    }

    const headers = {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "content-length": String(TOTAL_BYTES),
      "x-content-type-options": "nosniff",
      "referrer-policy": "strict-origin-when-cross-origin",
      "x-biggest-html-chunks": String(CHUNKS.length),
    };

    return new Response(
      request.method === "HEAD" ? null : createHtmlStream(env, request.signal),
      { headers },
    );
  },
};
