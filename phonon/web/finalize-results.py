import pathlib,json,re
root=pathlib.Path(r'D:\aispace\phonon');p=root/'test-output/compare/results.json';rows=json.loads(p.read_text(encoding='utf-8'))
for r in rows:
 if r['engine']=='kokoro':
  m=re.search(r'\{\s*"text".*?\n\}',r['pageStatus'],re.S);assert m
  status=json.loads(m.group());r['clickToReadySeconds']=r['synthSeconds'];r['pageModelLoadSeconds']=status['loadMs']/1000;r['pageTotalSeconds']=status['totalMs']/1000;r['synthSeconds']=status['synthesisMs']/1000;r['rtf']=r['synthSeconds']/r['duration'];r['timingScope']='Page-reported WebGPU FP32 synthesis only; model initialization separate';r['device']=status['device'];r['dtype']=status['dtype']
p.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
p=root/'web/build-compare.py';s=p.read_text(encoding='utf-8-sig');s=s.replace("('页面首次点击到音频就绪，含浏览器/模型初始化' if sid=='q1' else '页面点击到音频就绪，模型已预热')","('页面实测 WebGPU FP32 纯合成；模型加载 ' + format(r.get('pageModelLoadSeconds',0), '.3f') + ' 秒')")
s=s.replace('实测耗时','合成耗时')
s=s.replace('Kokoro 是浏览器页面点击至音频就绪，第一句含初始化，因此这些时间不是严格同条件性能基准。','Kokoro 是页面报告的 WebGPU FP32 纯合成耗时，模型初始化单列（首次约 296 秒）；Phonon 是 CPU q8，运行设备和精度不同，因此这些时间不是严格同条件性能基准。')
p.write_text(s,encoding='utf-8')
print(json.dumps([{k:v for k,v in r.items() if k not in ['pageStatus','timingScope']} for r in rows],indent=2,ensure_ascii=False))
