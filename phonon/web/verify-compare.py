import pathlib,urllib.request,json,io,wave,array,math
from playwright.sync_api import sync_playwright
root=pathlib.Path(r'D:\aispace\phonon');p=root/'web/index.html';s=p.read_text(encoding='utf-8-sig')
if '/compare.html' not in s:s=s.replace('<footer>','<footer><a href="/compare.html">英语同文案对比：Phonon vs Kokoro ↗</a><br>')
p.write_text(s,encoding='utf-8')
base='http://127.0.0.1:8790';report={}
with urllib.request.urlopen(base+'/compare.html') as r:
 body=r.read().decode('utf-8');report['pageStatus']=r.status;assert 'Phonon 31m · default' in body and '本地 TTS · Kokoro af_maple' in body
report['audio']=[]
for sid in ['q1','q2','q3','q4','q5']:
 for engine in ['phonon','kokoro']:
  url=f'{base}/compare-audio/{sid}-{engine}.wav'
  with urllib.request.urlopen(url) as r: b=r.read();status=r.status
  with wave.open(io.BytesIO(b)) as w:
   assert w.getframerate()==24000;a=array.array('h',w.readframes(w.getnframes()));assert any(a) and all(math.isfinite(x) for x in a)
  report['audio'].append(dict(url=url,status=status,bytes=len(b),finite=True,nonzero=True))
with urllib.request.urlopen('http://127.0.0.1:8787/') as r:report['kokoroPageStatus']=r.status
with urllib.request.urlopen(base+'/api/health') as r:report['phononHealth']=json.loads(r.read())
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge',headless=True)
 page=browser.new_page(viewport={'width':1280,'height':1000})
 page.goto(base+'/compare.html',wait_until='networkidle')
 page.wait_for_function('Array.from(document.querySelectorAll("audio")).length===10 && Array.from(document.querySelectorAll("audio")).every(a=>a.readyState>=1 && a.duration>0)',timeout=30000)
 report['browserAudioMetadata']=page.locator('audio').evaluate_all('(nodes)=>nodes.map(a=>({src:a.src,duration:a.duration,readyState:a.readyState,error:a.error?.message||null}))')
 page.screenshot(path=str(root/'test-output/compare/comparison-page.png'),full_page=True)
 print('BROWSER_LABELS',page.locator('h3').all_text_contents())
 browser.close()
(root/'test-output/compare/verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(report,indent=2,ensure_ascii=False))
