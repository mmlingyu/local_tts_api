const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'public');
const compareRoot=path.resolve(__dirname,'..','piper-zh-service','static');
const compareMap={'/piper-compare.html':'compare.html','/piper-compare.js':'compare.js','/piper-compare.css':'compare.css','/piper-compare-logic.mjs':'compare-logic.mjs'};
const port=Number(process.env.PORT||8787);
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.wasm':'application/wasm','.bin':'application/octet-stream','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8'};
const server=http.createServer((req,res)=>{
  res.setHeader('Cross-Origin-Opener-Policy','same-origin');res.setHeader('Cross-Origin-Embedder-Policy','require-corp');res.setHeader('Cross-Origin-Resource-Policy','same-origin');res.setHeader('X-Content-Type-Options','nosniff');
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);return res.end('Read-only static service');}
  if(!['127.0.0.1:'+port,'localhost:'+port].includes(req.headers.host)){res.writeHead(403);return res.end('Localhost only');}
  let name;try{name=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname)}catch{res.writeHead(400);return res.end('Bad URL')}
  const mapped=compareMap[name];
  if(mapped){
    const compareTarget=path.resolve(compareRoot, mapped);
    if(compareTarget!==path.join(compareRoot, mapped)){res.writeHead(403);return res.end('Forbidden')}
    fs.stat(compareTarget,(error,stat)=>{
      if(error||!stat.isFile()){res.writeHead(404);return res.end('Not found')}
      res.setHeader('Content-Type',mime[path.extname(compareTarget)]||'application/octet-stream');res.setHeader('Content-Length',stat.size);res.setHeader('Cache-Control','no-store');
      if(req.method==='HEAD')return res.end();fs.createReadStream(compareTarget).on('error',()=>res.destroy()).pipe(res);
    });
    return;
  }
  const target=path.resolve(root,'.'+(name==='/'?'/index.html':name));
  if(!target.startsWith(root+path.sep)){res.writeHead(403);return res.end('Forbidden')}
  fs.stat(target,(error,stat)=>{
    if(error||!stat.isFile()){res.writeHead(404);return res.end('Not found')}
    res.setHeader('Content-Type',mime[path.extname(target)]||'application/octet-stream');res.setHeader('Content-Length',stat.size);res.setHeader('Cache-Control','public, max-age=3600');
    if(req.method==='HEAD')return res.end();fs.createReadStream(target).on('error',()=>res.destroy()).pipe(res);
  });
});
server.listen(port,'127.0.0.1',()=>{
 const state={pid:process.pid,port,url:`http://127.0.0.1:${port}/`,started:new Date().toISOString()};
 fs.writeFileSync(path.join(__dirname,'service-state.json'),JSON.stringify(state,null,2));console.log(JSON.stringify(state));
});
server.on('error',e=>{console.error(e);process.exitCode=1});