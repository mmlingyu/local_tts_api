import { KokoroTTS, env } from '@uzen/kokoro-js';
env.wasmPaths = new URL('/ort/', location.href).href;
const $=id=>document.getElementById(id), model='onnx-community/Kokoro-82M-v1.1-zh-ONNX';
const examples={zh:'你好，这是一段中文语音合成测试。',mix:'你好，欢迎使用 Chinese TTS。今天我们测试 WebGPU 本地语音合成。',en:'Hello, this is a local English speech synthesis test.'};
for(const key of Object.keys(examples)) $('example-'+key).onclick=()=>{$('text').value=examples[key];$('voice').value=key==='mix'?'zm_009':key==='en'?'af_maple':'zf_001'};
let tts,device,loading,objectURL,busy=false;
function status(s){$('status').textContent=s;}
async function loadModel(){
 if(tts)return tts;if(loading)return loading;
 loading=(async()=>{
  const adapter=await navigator.gpu?.requestAdapter().catch(()=>null);device=adapter?'webgpu':'wasm';
  status('加载模型中（'+device+' / fp32），首次约需下载数百 MB…');$('progress').hidden=false;
  const opts={dtype:'fp32',device,voicePath:'/kokoro/voices',progress_callback:p=>{if(p.status==='progress'){const n=Number(p.progress||0);$('progress').value=n;status(`加载模型：${p.file||''} ${n.toFixed(1)}%（${device}）`);}}};
  try{tts=await KokoroTTS.from_pretrained(model,opts)}catch(e){
   if(device!=='webgpu')throw e;console.warn('WebGPU initialization failed, falling back to WASM',e);device='wasm';status('WebGPU 初始化失败，正在回退 WASM…');tts=await KokoroTTS.from_pretrained(model,{...opts,device});
  }
  $('progress').hidden=true;return tts;
 })().catch(e=>{loading=null;throw e});return loading;
}
function wav(samples,rate){
 const buffer=new ArrayBuffer(44+samples.length*2),v=new DataView(buffer);const str=(o,s)=>{for(let i=0;i<s.length;i++)v.setUint8(o+i,s.charCodeAt(i))};
 str(0,'RIFF');v.setUint32(4,36+samples.length*2,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,samples.length*2,true);
 for(let i=0;i<samples.length;i++){const x=Math.max(-1,Math.min(1,samples[i]));v.setInt16(44+i*2,x<0?x*32768:x*32767,true)}return new Blob([buffer],{type:'audio/wav'});
}
async function synthesize(text,voice,speed=1){
 if(busy)throw Error('正在处理，请稍候');text=text.trim();if(!text)throw Error('请输入朗读文本');if(text.length>1500)throw Error('文本不能超过 1500 字');if(!['zf_001','zf_002','zm_009','zm_010','af_maple'].includes(voice))throw Error('无效音色');
 busy=true;$('generate').disabled=true;$('download').hidden=true;window.lastResult=null;const start=performance.now();
 try{
 const engine=await loadModel(),loaded=performance.now();status('合成中：'+voice+'（'+device+' / fp32）…');
 const audio=await engine.generate(text,{voice,speed:Number(speed)});const elapsed=performance.now();
 const samples=audio.audio,rate=audio.sampling_rate||24000;if(!samples?.length)throw Error('合成结果为空');
 let peak=0,sum=0,finite=true;for(const n of samples){if(!Number.isFinite(n))finite=false;peak=Math.max(peak,Math.abs(n));sum+=n*n;}
 if(!finite||peak===0)throw Error('波形无效或全零');
 const stats={text,voice,device,dtype:'fp32',sampleRate:rate,samples:samples.length,durationSeconds:samples.length/rate,loadMs:loaded-start,synthesisMs:elapsed-loaded,totalMs:elapsed-start,peak,rms:Math.sqrt(sum/samples.length),finite};
 const blob=wav(samples,rate);if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(blob);$('player').src=objectURL;$('download').href=objectURL;$('download').download=voice+'-'+Date.now()+'.wav';$('download').hidden=false;$('details').textContent=JSON.stringify(stats,null,2);status(`成功：${stats.durationSeconds.toFixed(2)} 秒音频，合成 ${(stats.synthesisMs/1000).toFixed(2)} 秒，总耗时 ${(stats.totalMs/1000).toFixed(2)} 秒（${device}）`);window.lastResult=stats;window.lastWav=blob;
 try{await $('player').play()}catch{status($('status').textContent+'；点击播放器播放。')}
 return stats;
 }catch(e){status('失败：'+(e.message||e));$('details').textContent=String(e.stack||e);throw e}finally{busy=false;$('generate').disabled=false;$('progress').hidden=true}
}
$('generate').onclick=()=>synthesize($('text').value,$('voice').value,$('speed').value).catch(console.error);
window.zhTts={synthesize,loadModel,examples};window.appReady=true;