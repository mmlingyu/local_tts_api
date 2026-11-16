const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const http = require("node:http");
const test = require("node:test");

function listenPort() {
  return new Promise((resolve, reject) => {
    const probe = http.createServer();
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
    probe.on("error", reject);
  });
}

function get(port, path) {
  return new Promise((resolve, reject) => {
    const req = http.get({ hostname: "127.0.0.1", port, path }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8"), headers: res.headers }));
    });
    req.on("error", reject);
  });
}

test("Chinese static server still serves the default page and the Piper compare page", async () => {
  const port = await listenPort();
  const child = spawn(process.execPath, ["server.cjs"], {
    cwd: __dirname,
    env: { ...process.env, PORT: String(port) },
    stdio: ["ignore", "pipe", "pipe"],
  });
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("server did not start")), 5000);
      child.stdout.on("data", () => {
        clearTimeout(timer);
        resolve();
      });
      child.on("exit", (code) => reject(new Error(`server exited ${code}`)));
    });
    const home = await get(port, "/");
    assert.equal(home.status, 200);
    assert.match(home.body, /Kokoro/);
    assert.match(home.body, /piper-compare\.html/);
    const compare = await get(port, "/piper-compare.html");
    assert.equal(compare.status, 200);
    assert.match(compare.body, /多音字/);
    assert.match(compare.body, /人工音质/);
    assert.equal(compare.headers["cross-origin-embedder-policy"], "require-corp");
    const script = await get(port, "/piper-compare.js");
    assert.equal(script.status, 200);
    assert.match(script.body, /full-wav|X-Streaming/);
    const escaped = await get(port, "/..%2FREADME.md");
    assert.notEqual(escaped.status, 200);
    const outside = await get(port, "/piper-compare.html/../../README.md");
    assert.notEqual(outside.status, 200);
  } finally {
    child.kill("SIGTERM");
  }
});
