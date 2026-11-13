const fs = require('node:fs');
const path = require('node:path');
const base = 'D:/aispace/chickadee/extension/node_modules';
const kokoro = path.join(base, '@uzen/kokoro-js');
const esbuild = require(path.join(base, 'esbuild'));
(async () => {
  await esbuild.build({entryPoints:[path.join(__dirname,'app.js')],outfile:path.join(__dirname,'public/app.js'),bundle:true,format:'esm',platform:'browser',target:'es2022',nodePaths:[path.join(kokoro,'node_modules'),base],logLevel:'info',sourcemap:false});
  const dist=path.join(kokoro,'node_modules/onnxruntime-web/dist');
  fs.mkdirSync(path.join(__dirname,'public/ort'),{recursive:true});
  const assets=fs.readdirSync(dist).filter(n=>/^ort-wasm.*\.(wasm|mjs)$/.test(n));
  for(const name of assets) fs.copyFileSync(path.join(dist,name),path.join(__dirname,'public/ort',name));
  if(!assets.some(n=>n.includes('asyncify.wasm'))) throw Error('Missing asyncify WASM');
  console.log('Bundled browser-only TTS; runtime assets:',assets.join(', '));
})().catch(e=>{console.error(e);process.exitCode=1});