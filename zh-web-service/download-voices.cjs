const fs=require('node:fs'),path=require('node:path');
(async()=>{
 const repo='onnx-community/Kokoro-82M-v1.1-zh-ONNX';
 const response=await fetch('https://huggingface.co/api/models/'+repo,{signal:AbortSignal.timeout(60000)});if(!response.ok)throw Error('Model metadata: '+response.status);const meta=await response.json();
 const revision=meta.sha;console.log('Pinned voice revision:',revision);
 const voices=['zf_001','zf_002','zm_009','zm_010','af_maple'];
 for(const voice of voices){const url=`https://huggingface.co/${repo}/resolve/${revision}/voices/${voice}.bin`;const res=await fetch(url,{signal:AbortSignal.timeout(180000)});if(!res.ok)throw Error(voice+': '+res.status);const bytes=Buffer.from(await res.arrayBuffer());if(bytes.length%4!==0||bytes.length<1000)throw Error('Invalid voice '+voice);fs.writeFileSync(path.join(__dirname,'public/kokoro/voices',voice+'.bin'),bytes);console.log(voice,bytes.length)}
 fs.writeFileSync(path.join(__dirname,'voice-manifest.json'),JSON.stringify({repository:repo,revision,voices},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});