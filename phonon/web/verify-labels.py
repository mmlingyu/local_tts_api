from playwright.sync_api import sync_playwright
import pathlib,json
root=pathlib.Path(r'D:\aispace\phonon')
with sync_playwright() as p:
 b=p.chromium.launch(channel='msedge',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
 page=b.new_page();page.goto('http://127.0.0.1:8790/compare.html',wait_until='networkidle')
 labels=page.locator('h3').all_text_contents()
 expected=['Phonon 31m \u00b7 default','\u672c\u5730 TTS \u00b7 Kokoro af_maple']*5
 assert labels==expected,(labels,expected)
 page.locator('.sequence').first.click()
 page.wait_for_function('() => document.querySelectorAll("audio")[1].currentTime > 0.1',timeout=15000)
 print(json.dumps({'labelsExactMatch':True,'firstPairSequentialPlaybackPassed':True,'labels':labels},ensure_ascii=True))
 b.close()
rows=json.loads((root/'test-output/compare/results.json').read_text(encoding='utf-8'))
lines=['# English comparison verification','', 'URL: http://127.0.0.1:8790/compare.html','', 'Both engines generated all five texts independently. Phonon: official 31m q8 CPU, default. Kokoro: existing page af_maple, speed 1, WebGPU FP32.','All 10 HTTP WAV requests returned 200; all 10 audio elements loaded without error. All waveforms are finite and nonzero, PCM16 mono 24000 Hz.','Exact visible labels and first-pair sequential browser playback verified. No human listening/MOS conducted.','First Kokoro model initialization: 295.746235 seconds (excluded from synthesis times below).','Phonon timing includes child process startup/model loading; Kokoro timing is page-reported synthesis only, so not a strict same-condition benchmark.','', '| ID | Engine | Duration s | Peak | RMS | Synthesis s | RTF |','|---|---|---:|---:|---:|---:|---:|']
for sid in ['q1','q2','q3','q4','q5']:
 for r in [x for x in rows if x['id']==sid]:lines.append(f"| {sid} | {r['engine']} | {r['duration']:.3f} | {r['peak']:.6f} | {r['rms']:.6f} | {r['synthSeconds']:.6f} | {r['rtf']:.6f} |")
lines+=['','Raw WAV paths: D:\\aispace\\phonon\\test-output\\compare\\q{1..5}-{phonon|kokoro}.wav','Screenshot: comparison-page.png (saved; not visually reviewed by assistant).','Detailed metadata: results.json; HTTP/browser metadata verification: verification.json.','Services left running: Kokoro 127.0.0.1:8787 PID 20348; Phonon 127.0.0.1:8790 PID 32120.','Kokoro source files were not read or modified. Only its running rendered page was automated.']
(root/'test-output/compare/TEST-RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
