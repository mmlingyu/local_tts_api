const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('D:/aispace/chickadee/extension/node_modules/playwright');
const output=path.join(__dirname,'test-output');fs.mkdirSync(output,{recursive:true});
const results=[];let context;
function checkWav(file){
 const b=fs.readFileSync(file);if(b.toString('ascii',0,4)!=='RIFF'||b.toString('ascii',8,12)!=='WAVE')throw Error('Invalid WAV header');
 const rate=b.readUInt32LE(24),length=b.readUInt32LE(40);let peak=0,sum=0,nonzero=0;
 for(let p=44;p<44+length;p+=2){const n=b.readInt16LE(p)/32768;peak=Math.max(peak,Math.abs(n));sum+=n*n;if(n!==0)nonzero++}
 const duration=length/2/rate;if(!(duration>.5&&duration<120&&peak>0&&nonzero>0))throw Error('Invalid waveform');
 return {rate,samples:length/2,durationSeconds:duration,peak,rms:Math.sqrt(sum/(length/2)),nonzero,valid:true};
}
(async()=>{
 context=await chromium.launchPersistentContext('D:/aispace/chickadee/extension/test-output/browser-profile',{channel:'msedge',headless:false,acceptDownloads:true,downloadsPath:output,viewport:{width:1120,height:960},args:['--autoplay-policy=no-user-gesture-required'],timeout:60000});
 const page=await context.newPage();page.setDefaultTimeout(60000);
 page.on('console',msg=>fs.appendFileSync(path.join(output,'browser.log'),msg.type()+': '+msg.text()+'\n'));
 page.on('pageerror',err=>fs.appendFileSync(path.join(output,'browser.log'),'PAGEERROR: '+err.stack+'\n'));
 page.on('requestfailed',req=>fs.appendFileSync(path.join(output,'browser.log'),'FAILED: '+req.url()+' '+req.failure()?.errorText+'\n'));
 const foreign=[];page.on('request',r=>{if(r.url().startsWith('http')&&!r.url().startsWith('http://127.0.0.1:8787/'))foreign.push(r.url())});
 const response=await page.goto('http://127.0.0.1:8787/',{waitUntil:'domcontentloaded'});console.log('HTTP',response.status(),'COOP',response.headers()['cross-origin-opener-policy'],'COEP',response.headers()['cross-origin-embedder-policy']);
 await page.waitForFunction(()=>window.appReady===true);
 console.log('Browser capabilities',JSON.stringify(await page.evaluate(()=>({crossOriginIsolated,gpu:!!navigator.gpu,userAgent:navigator.userAgent}))));
 async function test(name,text,voice){
  console.log('START',name,text,voice,new Date().toISOString());
  await page.locator('#text').fill(text);await page.locator('#voice').selectOption(voice);await page.locator('#generate').click();
  await page.waitForFunction(()=>window.lastResult||document.querySelector('#status').textContent.startsWith('失败'),{},{timeout:1200000,polling:1000});
  const stats=await page.evaluate(()=>window.lastResult);if(!stats)throw Error(await page.locator('#details').innerText());
  const d=page.waitForEvent('download');await page.locator('#download').click();const download=await d;const file=path.join(output,name+'.wav');await download.saveAs(file);
  const check=checkWav(file);const result={name,...stats,wav:file,wavCheck:check};results.push(result);fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));
  await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});console.log('PASS',JSON.stringify(result));
 }
 await test('chinese-female','你好，这是一段中文语音合成测试。','zf_001');
 await test('mixed-male','你好，欢迎使用 Chinese TTS。今天我们测试 WebGPU 本地语音合成。','zm_009');
 await test('english-female','Hello, this is a local English speech synthesis test.','af_maple');
 console.log('Blocking all external HTTP(S) requests for cached-model offline simulation');
 await context.route('**/*',route=>{const u=new URL(route.request().url());if(['http:','https:'].includes(u.protocol)&&u.hostname!=='127.0.0.1'&&u.hostname!=='localhost')return route.abort('internetdisconnected');return route.continue()});
 await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.appReady===true);
 await test('offline-chinese','模型缓存后，这段中文语音在禁止外网连接时生成。','zf_002');
 fs.writeFileSync(path.join(output,'network-origins.json'),JSON.stringify([...new Set(foreign.map(u=>new URL(u).origin))],null,2));
 console.log('ALL TESTS PASSED');
})().catch(async e=>{console.error(e);fs.writeFileSync(path.join(output,'failure.txt'),String(e.stack||e));try{await context?.pages().at(-1)?.screenshot({path:path.join(output,'failure.png'),fullPage:true})}catch{}process.exitCode=1}).finally(async()=>{await context?.close()});