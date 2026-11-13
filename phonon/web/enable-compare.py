from pathlib import Path
p=Path(r'D:\aispace\phonon\web\server.cjs')
s=p.read_text(encoding='utf-8-sig')
anchor="  if(req.method==='GET' && req.url==='/api/health')"
assert anchor in s
route="""  if(req.method==='GET' && (req.url==='/compare.html'||req.url==='/compare'||req.url==='/compare.js'||/^\\/compare-audio\\/q[1-5]-(phonon|kokoro)\\.wav$/.test(req.url))){
    const relative=(req.url==='/compare'||req.url==='/compare.html')?'compare.html':req.url.slice(1);
    const file=path.join(__dirname,relative);
    if(!fs.existsSync(file))return json(res,404,{error:'Comparison audio not available'});
    const type=relative.endsWith('.wav')?'audio/wav':relative.endsWith('.js')?'text/javascript; charset=utf-8':'text/html; charset=utf-8';
    res.writeHead(200,{'Content-Type':type,'Content-Length':fs.statSync(file).size,'Cache-Control':'no-store'});return fs.createReadStream(file).pipe(res);
  }
"""
if "Comparison audio not available" not in s:s=s.replace(anchor,route+anchor)
p.write_text(s,encoding='utf-8')
p=Path(r'D:\aispace\phonon\README.zh-CN.md')
with p.open('a',encoding='utf-8') as f:f.write('\n## 英语同文案试听对比\n\n打开 http://127.0.0.1:8790/compare.html 。每句分别标注 Phonon 31m · default 和本地 TTS · Kokoro af_maple，使用预生成 WAV；朗读内容不包含模型名称。原始音频与实测数据位于 test-output\\compare。页面显示实际耗时及初始化口径，不能当作严格同条件性能基准。\n')
