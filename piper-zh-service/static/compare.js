import {
  FIRST_AUDIO_NOTE,
  PRESETS,
  RTF_DEFINITION,
  categories,
  formatSeconds,
  kokoroAvailableHere,
  parseWavPcm16,
  rtf,
} from "./piper-compare-logic.mjs";

const $ = (id) => document.getElementById(id);
const PIPER_API = "http://127.0.0.1:8791";
let stopRequested = false;
let running = false;
let kokoroModule = null;

$("rtf-definition").textContent = RTF_DEFINITION;
if (!kokoroAvailableHere(location)) {
  $("kokoro-where").textContent =
    "当前不是 8787 上的中文服务页面，Kokoro 选项会直接说明原因，不会去加载模型。Piper 仍可在本页测试。对照页地址：http://127.0.0.1:8787/piper-compare.html";
}

function renderPresets() {
  const root = $("presets");
  for (const category of categories()) {
    for (const preset of PRESETS.filter((item) => item.category === category)) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${preset.category} · ${preset.label}`;
      button.addEventListener("click", () => {
        $("text").value = preset.text;
      });
      root.append(button);
    }
  }
}

function setBusy(value) {
  running = value;
  $("run-one").disabled = value;
  $("run-all").disabled = value;
  $("stop").disabled = !value;
  $("engine").disabled = value;
}

async function refreshHealth() {
  const box = $("health");
  try {
    const response = await fetch(`${PIPER_API}/api/health`, { cache: "no-store" });
    const data = await response.json();
    const ready = data.modelReady === true;
    const title = document.createElement("strong");
    title.className = ready ? "ok" : "warn";
    title.textContent = ready
      ? `Piper 已加载 ${data.modelId || "模型"}（${data.configuredDevice || "cpu"}）`
      : "Piper 进程可访问，但模型还没准备好";
    const detail = document.createElement("span");
    const parts = [
      data.piperVersion ? `piper-tts ${data.piperVersion}` : "还没读到 piper-tts 版本",
      data.phonemeType ? `音素 ${data.phonemeType}` : "",
      data.g2p || "",
      data.error || "",
      data.deviceNote || "不探测本机硬件。",
    ].filter(Boolean);
    detail.textContent = parts.join(" · ");
    const license = data.license && data.license.attribution;
    if (license) $("license-text").textContent = license;
    box.replaceChildren(title, detail);
  } catch (error) {
    const title = document.createElement("strong");
    title.className = "bad";
    title.textContent = "Piper 服务没有响应";
    const detail = document.createElement("span");
    detail.textContent = `请先在 piper-zh-service 启动 python -m piper_zh。这只说明 127.0.0.1:8791 连不上，不是电脑硬件检测。${error.message || ""}`;
    box.replaceChildren(title, detail);
  }
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const write = (offset, text) => {
    for (let index = 0; index < text.length; index += 1) view.setUint8(offset + index, text.charCodeAt(index));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index += 1) {
    const value = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, value < 0 ? value * 32768 : value * 32767, true);
  }
  return buffer;
}

function metric(label, value) {
  const wrap = document.createElement("div");
  const name = document.createElement("span");
  name.textContent = label;
  wrap.append(name, document.createTextNode(value));
  return wrap;
}

function renderResult(record) {
  const card = document.createElement("article");
  card.className = "result";
  const title = document.createElement("h3");
  title.textContent = `${record.engineLabel} · ${record.label}`;
  const status = document.createElement("p");
  status.className = record.ok ? "ok" : "bad";
  status.textContent = record.ok ? "自动测量：成功" : `自动测量：失败。${record.error || ""}`;
  const metrics = document.createElement("div");
  metrics.className = "metrics";
  metrics.append(
    metric("整段合成耗时", record.synthSeconds == null ? "—" : `${formatSeconds(record.synthSeconds)} 秒`),
    metric("音频时长", record.durationSeconds == null ? "—" : `${formatSeconds(record.durationSeconds)} 秒`),
    metric("RTF", record.rtfValue == null ? "—" : record.rtfValue.toFixed(3)),
    metric("请求往返", record.roundTripSeconds == null ? "—" : `${formatSeconds(record.roundTripSeconds)} 秒`),
    metric("首音时间", FIRST_AUDIO_NOTE),
  );
  card.append(title, status, metrics);
  if (record.text) {
    const sample = document.createElement("p");
    sample.textContent = record.text;
    card.append(sample);
  }
  if (record.wavUrl) {
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = record.wavUrl;
    const link = document.createElement("a");
    link.href = record.wavUrl;
    link.download = record.downloadName;
    link.textContent = "下载 WAV";
    card.append(audio, document.createElement("br"), link);
  }
  const human = document.createElement("div");
  human.className = "human";
  const humanLabel = document.createElement("label");
  humanLabel.textContent = "人工音质（不参与自动结论）";
  const select = document.createElement("select");
  for (const option of ["未评价", "1 差", "2 较差", "3 一般", "4 较好", "5 好"]) {
    const node = document.createElement("option");
    node.value = option;
    node.textContent = option;
    select.append(node);
  }
  const note = document.createElement("input");
  note.type = "text";
  note.placeholder = "听感备注，只留在本页";
  humanLabel.append(select);
  human.append(humanLabel, note);
  card.append(human);
  $("results").prepend(card);
}

async function runPiper(text) {
  const started = performance.now();
  const response = await fetch(`${PIPER_API}/api/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const roundTripSeconds = (performance.now() - started) / 1000;
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data && data.error) message = data.error;
    } catch {
      /* 保留 HTTP 状态 */
    }
    return { ok: false, error: message, roundTripSeconds };
  }
  const synthSeconds = Number(response.headers.get("X-Synth-Seconds"));
  const streaming = response.headers.get("X-Streaming");
  if (streaming && streaming !== "full-wav") {
    return { ok: false, error: `响应声明了非预期的流式模式：${streaming}`, roundTripSeconds };
  }
  const buffer = await response.arrayBuffer();
  const parsed = parseWavPcm16(buffer);
  const value = rtf(synthSeconds, parsed.durationSeconds);
  const blob = new Blob([buffer], { type: "audio/wav" });
  return {
    ok: true,
    synthSeconds,
    durationSeconds: parsed.durationSeconds,
    rtfValue: value,
    roundTripSeconds,
    wavUrl: URL.createObjectURL(blob),
    sampleRate: parsed.sampleRate,
  };
}

async function runKokoro(text) {
  if (!kokoroAvailableHere(location)) {
    throw new Error("这个页面不在 8787 上，没有加载 Kokoro。请打开 http://127.0.0.1:8787/piper-compare.html。");
  }
  if (!$("kokoro-optin").checked) {
    throw new Error("还没有确认加载 Kokoro，因此没有访问 Hugging Face，也没有开始合成。");
  }
  if (!kokoroModule) {
    kokoroModule = await import("/kokoro-client.js");
  }
  const voice = $("kokoro-voice").value;
  const started = performance.now();
  const audio = await kokoroModule.synthesizeKokoro(text, voice, 1);
  const roundTripSeconds = (performance.now() - started) / 1000;
  const wav = encodeWav(audio.samples, audio.sampleRate);
  const parsed = parseWavPcm16(wav);
  return {
    ok: true,
    synthSeconds: audio.synthMs / 1000,
    durationSeconds: parsed.durationSeconds,
    rtfValue: rtf(audio.synthMs / 1000, parsed.durationSeconds),
    roundTripSeconds,
    wavUrl: URL.createObjectURL(new Blob([wav], { type: "audio/wav" })),
    sampleRate: parsed.sampleRate,
    engineDetail: audio.device,
  };
}

async function runItem(item) {
  const engine = $("engine").value;
  const record = {
    engineLabel: engine === "piper" ? "Piper" : `Kokoro ${$("kokoro-voice").value}`,
    label: item.label,
    text: item.text,
    downloadName: `${engine}-${item.id}.wav`,
  };
  try {
    const outcome = engine === "piper" ? await runPiper(item.text) : await runKokoro(item.text);
    Object.assign(record, outcome);
  } catch (error) {
    record.ok = false;
    record.error = error && error.message ? error.message : String(error);
  }
  renderResult(record);
  return record.ok !== false && record.ok !== undefined ? record.ok : false;
}

async function runOne() {
  if (running) return;
  const text = $("text").value.trim();
  if (!text) {
    renderResult({ engineLabel: $("engine").value, label: "当前文本", text: "", ok: false, error: "请输入文本。" });
    return;
  }
  setBusy(true);
  stopRequested = false;
  try {
    await runItem({ id: "manual", label: "当前文本", text });
  } finally {
    setBusy(false);
    refreshHealth();
  }
}

async function runAll() {
  if (running) return;
  setBusy(true);
  stopRequested = false;
  try {
    for (const preset of PRESETS) {
      if (stopRequested) break;
      $("text").value = preset.text;
      await runItem(preset);
    }
  } finally {
    setBusy(false);
    refreshHealth();
  }
}

$("run-one").addEventListener("click", () => runOne());
$("run-all").addEventListener("click", () => runAll());
$("stop").addEventListener("click", () => {
  stopRequested = true;
});
renderPresets();
refreshHealth();
