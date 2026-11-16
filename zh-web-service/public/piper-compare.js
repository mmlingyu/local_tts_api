import {
  FIRST_AUDIO_NOTE,
  LEGACY_PIPER_MESSAGE,
  LOCAL_PIPER_8800,
  RTF_DEFINITION,
  formatSeconds,
  isLoopbackHttp,
  kokoroAllowedFor,
  kokoroAvailableHere,
  parseWavPcm16,
  piperApiBase,
  piperSupportsLanguageFields,
  presetsFor,
  rtf,
  ttsPayload,
} from "./piper-compare-logic.mjs?v=20261116b";

const GENDER_LABEL = { female: "女", male: "男", unknown: "性别未知", multiple: "男女声在同一模型" };
const FALLBACK_VOICES = [
  { voice: "zh_CN-chaowen-medium", language: "zh", numSpeakers: 1, speakers: {}, gender: "unknown", licenseClass: "attribution", datasetLicense: "CC0", defaultForLanguage: true, downloaded: false, loaded: false, frontendReady: false, pronunciationReviewed: false },
  { voice: "zh_CN-xiao_ya-medium", language: "zh", numSpeakers: 1, speakers: {}, gender: "female", licenseClass: "noncommercial", datasetLicense: "Non-commercial", defaultForLanguage: false, downloaded: false, loaded: false, frontendReady: false, pronunciationReviewed: false },
  { voice: "en_US-joe-medium", language: "en", numSpeakers: 1, speakers: {}, gender: "unknown", licenseClass: "permissive", datasetLicense: "CC0", defaultForLanguage: true, downloaded: false, loaded: false, frontendReady: false, pronunciationReviewed: false },
  { voice: "en_US-ljspeech-medium", language: "en", numSpeakers: 1, speakers: {}, gender: "female", licenseClass: "permissive", datasetLicense: "public domain", defaultForLanguage: false, downloaded: false, loaded: false, frontendReady: false, pronunciationReviewed: false },
  { voice: "en_US-norman-medium", language: "en", numSpeakers: 1, speakers: {}, gender: "male", licenseClass: "permissive", datasetLicense: "public domain", defaultForLanguage: false, downloaded: false, loaded: false, frontendReady: false, pronunciationReviewed: false },
  { voice: "ja_JP-hi_fi_captain-medium", language: "ja", numSpeakers: 2, speakers: { female: 0, male: 1 }, speakerGenders: { female: "female", male: "male" }, gender: "multiple", licenseClass: "noncommercial", datasetLicense: "CC BY-NC-SA 4.0", defaultForLanguage: true, downloaded: false, loaded: false, frontendReady: false, pronunciationReviewed: false },
  { voice: "ko_KR-kss-medium", language: "ko", numSpeakers: 1, speakers: {}, gender: "female", licenseClass: "noncommercial", datasetLicense: "CC BY-NC-SA 4.0", defaultForLanguage: true, downloaded: false, loaded: false, frontendReady: false, pronunciationReviewed: false },
  { voice: "fr_FR-siwis-medium", language: "fr", numSpeakers: 1, speakers: {}, gender: "unknown", licenseClass: "attribution", datasetLicense: "CC BY 4.0", defaultForLanguage: true, downloaded: false, loaded: false, frontendReady: false, pronunciationReviewed: false },
];
let voiceCatalog = FALLBACK_VOICES;
let languageCatalog = [];
let languageFields = false;
let piperState = "pending";

const $ = (id) => document.getElementById(id);
let piperApi = piperApiBase(location, window.localStorage.getItem("piperApiBase"));
let stopRequested = false;
let running = false;
let kokoroModule = null;

$("piper-base").value = piperApi;
$("piper-base-save").addEventListener("click", () => {
  const next = $("piper-base").value.trim();
  if (!isLoopbackHttp(next)) {
    $("health").textContent = "Piper 地址只能是 http://127.0.0.1:端口 或 http://localhost:端口。不会改用 8791 以外的任意网站。";
    return;
  }
  piperApi = next.replace(/\/$/, "");
  window.localStorage.setItem("piperApiBase", piperApi);
  refreshHealth();
});
$("use-local-8800").addEventListener("click", () => {
  piperApi = LOCAL_PIPER_8800;
  $("piper-base").value = piperApi;
  window.localStorage.setItem("piperApiBase", piperApi);
  refreshHealth();
});
$("rtf-definition").textContent = RTF_DEFINITION;
if (!kokoroAvailableHere(location)) {
  $("kokoro-where").textContent =
    "当前不是 8787 上的中文服务页面，Kokoro 选项会直接说明原因，不会去加载模型。Piper 仍可在本页测试。对照页地址：http://127.0.0.1:8787/piper-compare.html";
}

function currentLanguage() {
  return $("piper-language").value;
}

function voicesForLanguage(language) {
  return voiceCatalog.filter((item) => item.language === language);
}

let renderingVoices = false;

function renderVoiceChoices() {
  if (renderingVoices) return;
  renderingVoices = true;
  const language = currentLanguage();
  const voices = voicesForLanguage(language);
  const select = $("piper-voice");
  const previous = select.value;
  select.replaceChildren();
  for (const voice of voices) {
    const option = document.createElement("option");
    option.value = voice.voice;
    const flags = [
      voice.downloaded ? "已下载" : "未下载",
      voice.loaded ? "已加载" : "未加载",
      voice.frontendReady ? "前端就绪" : "前端未就绪",
      voice.pronunciationReviewed ? "已听审" : "未做人工听审",
    ];
    const gender = GENDER_LABEL[voice.gender] || "性别未知";
    option.textContent = `${voice.voice} · ${gender} · ${voice.datasetLicense || ""} · ${voice.licenseClass || ""} · ${flags.join(" / ")}`;
    select.append(option);
  }
  if (voices.some((item) => item.voice === previous)) select.value = previous;
  const chosen = voices.find((item) => item.voice === select.value) || voices[0];
  const speakerLabel = $("piper-speaker-label");
  const speaker = $("piper-speaker");
  speaker.replaceChildren();
  if (chosen && chosen.numSpeakers > 1) {
    speakerLabel.hidden = false;
    const entries = Object.keys(chosen.speakers || {}).length
      ? Object.entries(chosen.speakers)
      : [["0", 0]];
    for (const [name, id] of entries) {
      const option = document.createElement("option");
      option.value = String(id);
      option.textContent = `${name} (${id})`;
      speaker.append(option);
    }
  } else {
    speakerLabel.hidden = true;
  }
  const kokoro = $("engine").querySelector('option[value="kokoro"]');
  const allowed = kokoroAllowedFor(language);
  kokoro.disabled = !allowed;
  if (!allowed && $("engine").value === "kokoro") $("engine").value = "piper";
  $("preset-note").textContent = allowed
    ? "中文可以对照 Kokoro。其他语言只走 Piper 白名单，不会用中文 Kokoro 音色冒充日语、韩语、法语或英语。"
    : "当前语言不使用 Kokoro。中文 Kokoro 音色不能用来冒充这个语言。";
  renderingVoices = false;
}

function renderPresets() {
  const root = $("presets");
  root.replaceChildren();
  for (const preset of presetsFor(currentLanguage())) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${preset.category} · ${preset.label}`;
    button.addEventListener("click", () => {
      $("text").value = preset.text;
    });
    root.append(button);
  }
}

function setBusy(value) {
  running = value;
  $("run-one").disabled = value;
  $("run-all").disabled = value;
  $("stop").disabled = !value;
  $("engine").disabled = value;
}

function renderEndpoint(health) {
  const version = health && health.serviceVersion ? health.serviceVersion : "未报告";
  const capability = languageFields ? "可传 language/voice" : piperState === "down" ? "未连上" : piperState === "pending" ? "正在确认" : "只接受 text";
  $("piper-endpoint").textContent = `当前地址 ${piperApi} · 服务 ${version} · ${capability}`;
  $("use-local-8800").hidden = piperState !== "legacy";
}

async function refreshHealth() {
  const box = $("health");
  let health = null;
  let healthReached = false;
  try {
    const response = await fetch(`${piperApi}/api/health`, { cache: "no-store" });
    healthReached = response.ok;
    if (response.ok) health = await response.json();
  } catch {
    healthReached = false;
  }
  const voicesOk = await refreshVoices();
  languageFields = piperSupportsLanguageFields(health, voicesOk);
  piperState = !healthReached ? "down" : languageFields ? "current" : "legacy";
  renderEndpoint(health);
  if (!healthReached) {
    const title = document.createElement("strong");
    title.className = "bad";
    title.textContent = "Piper 服务没有响应";
    const detail = document.createElement("span");
    detail.textContent = `请先启动 Piper：python -m piper_zh --host 127.0.0.1 --port <空闲端口> --device cpu。这只说明 ${piperApi} 连不上，不是电脑硬件检测。`;
    box.replaceChildren(title, detail);
    return;
  }
  const data = health;
  const ready = data.modelReady === true;
  const title = document.createElement("strong");
  title.className = piperState === "legacy" ? "warn" : ready ? "ok" : "warn";
  const loaded = Array.isArray(data.loadedVoiceIds) ? data.loadedVoiceIds.join(", ") : "";
  title.textContent = piperState === "legacy"
    ? LEGACY_PIPER_MESSAGE
    : ready
      ? `默认中文音色文件已在本机（${data.configuredDevice || "cpu"}）${loaded ? "；内存中：" + loaded : "；尚未全部常驻内存"}`
      : "Piper 进程可访问，但默认中文音色还没准备好";
  const detail = document.createElement("span");
  const parts = [
    data.piperVersion ? `piper-tts ${data.piperVersion}` : "还没读到 piper-tts 版本",
    data.serviceVersion ? `接口 ${data.serviceVersion}` : "",
    data.phonemeType ? `音素 ${data.phonemeType}` : "",
    data.g2p || "",
    data.error || "",
    data.deviceNote || "不探测本机硬件。",
  ].filter(Boolean);
  detail.textContent = parts.join(" · ");
  const license = data.license && data.license.attribution;
  if (license) $("license-text").textContent = license;
  box.replaceChildren(title, detail);
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
  title.textContent = `${record.engineLabel}${record.engineDetail ? " · " + record.engineDetail : ""} · ${record.label}`;
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
  const selection = { language: currentLanguage(), voice: $("piper-voice").value };
  if (!$("piper-speaker-label").hidden && $("piper-speaker").value !== "") {
    selection.speaker = Number($("piper-speaker").value);
  }
  const body = ttsPayload(text, selection, languageFields);
  if (!body) {
    const error = piperState === "down"
      ? "Piper 服务没有响应"
      : piperState === "pending"
        ? "正在确认 Piper 版本，还没有发送合成请求。"
        : LEGACY_PIPER_MESSAGE;
    return { ok: false, error, roundTripSeconds: 0 };
  }
  const response = await fetch(`${piperApi}/api/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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
  if (!kokoroAllowedFor(currentLanguage())) {
    throw new Error("Kokoro 只保留给中文对照。不会用中文音色合成当前语言。");
  }
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

async function refreshVoices() {
  let voicesOk = false;
  try {
    const response = await fetch(`${piperApi}/api/voices`, { cache: "no-store" });
    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data.voices) && data.voices.length) {
        voiceCatalog = data.voices;
        voicesOk = true;
      }
      if (Array.isArray(data.languages)) languageCatalog = data.languages;
    }
  } catch {
    voicesOk = false;
  }
  if (!voicesOk) voiceCatalog = FALLBACK_VOICES;
  renderVoiceChoices();
  renderPresets();
  updateGenderCoverage();
  return voicesOk;
}

function updateGenderCoverage() {
  const coverage = $("gender-coverage");
  if (coverage) {
    const row = languageCatalog.find((item) => item.language === currentLanguage());
    if (!row) {
      coverage.textContent = "还没有读到性别覆盖。gender 不是请求字段，只能在上面的音色列表里选择。";
    } else {
      const verified = (row.verifiedGenders || []).map((item) => GENDER_LABEL[item] || item).join("、") || "无";
      const missing = (row.missingGenders || []).map((item) => GENDER_LABEL[item] || item).join("、") || "无";
      coverage.textContent = `已核实：${verified}。仍缺：${missing}。${row.gap || ""} 自动合成不代表听感正确。`;
    }
  }
}

async function runAll() {
  if (running) return;
  setBusy(true);
  stopRequested = false;
  try {
    for (const preset of presetsFor(currentLanguage())) {
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
$("piper-language").addEventListener("change", () => {
  renderVoiceChoices();
  renderPresets();
  updateGenderCoverage();
  const first = presetsFor(currentLanguage())[0];
  if (first) $("text").value = first.text;
});
$("piper-voice").addEventListener("change", renderVoiceChoices);
renderVoiceChoices();
renderPresets();
renderEndpoint(null);
refreshHealth();
