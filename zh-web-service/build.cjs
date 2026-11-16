const fs = require('node:fs');
const path = require('node:path');
const esbuild = require('esbuild');

const root = __dirname;
const kokoroEntry = path.join(root, 'node_modules/@uzen/kokoro-js/dist/kokoro.web.js');
if (!fs.existsSync(kokoroEntry)) {
  console.error('缺少 @uzen/kokoro-js。请在 zh-web-service 目录执行 npm install。');
  process.exit(1);
}

function findOrtDist() {
  const candidates = [
    path.join(root, 'node_modules/onnxruntime-web/dist'),
    path.join(root, 'node_modules/@huggingface/transformers/node_modules/onnxruntime-web/dist'),
  ];
  const found = candidates.find((dir) => fs.existsSync(dir));
  if (!found) throw new Error('找不到 onnxruntime-web。请重新 npm install。');
  return found;
}

(async () => {
  await esbuild.build({
    entryPoints: {
      app: path.join(root, 'app.js'),
      'kokoro-client': path.join(root, 'kokoro-client.js'),
    },
    outdir: path.join(root, 'public'),
    entryNames: '[name]',
    bundle: true,
    format: 'esm',
    platform: 'browser',
    target: 'es2022',
    alias: { '@uzen/kokoro-js': kokoroEntry },
    logLevel: 'info',
    sourcemap: false,
  });
  const dist = findOrtDist();
  const target = path.join(root, 'public/ort');
  fs.mkdirSync(target, { recursive: true });
  const assets = fs.readdirSync(dist).filter((name) => /^ort-wasm.*\.(wasm|mjs)$/.test(name));
  for (const name of assets) fs.copyFileSync(path.join(dist, name), path.join(target, name));
  if (!assets.some((name) => name.includes('asyncify.wasm'))) throw new Error('Missing asyncify WASM');
  console.log('Bundled browser TTS from local node_modules. Runtime assets:', assets.join(', '));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
