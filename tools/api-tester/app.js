const HAN = /[\u3400-\u9fff]/;
const state = {
  piper: [],
  phonon: [],
  controller: null,
  objectUrl: "",
  downloadName: "speech.wav",
};

const $ = (id) => document.getElementById(id);

document.getElementById("local-origin").textContent = location.origin;

function tokenValue() {
  return $("token").value;
}

function setBanner(kind, text) {
  const node = $("banner");
  node.className = "banner" + (text ? " show " + kind : "");
  node.textContent = text || "";
}

function redact(value) {
  const token = tokenValue();
  let text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  text = text.replace(/bearer\s+\S+/gi, "Bearer [redacted]");
  if (token) text = text.split(token).join("[redacted]");
  return text;
}

function showDetail(value) {
  $("detail").textContent = redact(value);
}

function releaseAudio() {
  if (state.objectUrl) {
    URL.revokeObjectURL(state.objectUrl);
    state.objectUrl = "";
  }
  $("player").removeAttribute("src");
  $("player").load();
}

function statusHint(status) {
  if (status === 401) return "401：令牌缺失或不对。不会自动重试。";
  if (status === 403) return "403：来源或 Host 不被接受。公网网页不能直接调用，请继续用本机页面。";
  if (status === 429) return "429：已有一段合成未结束。请串行等待，不要并发。";
  if (status === 503) return "503：目标服务报告未就绪。这不是页面假数据。";
  if (status === 504) return "504：等待超时。停止等待不能取消服务端可能仍在进行的合成。";
  return "";
}

async function proxy(method, path, query, body) {
  const response = await fetch("/proxy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      base: $("base").value.trim(),
      token: tokenValue(),
      method,
      path,
      query: query || null,
      body: body || null,
    }),
    signal: state.controller ? state.controller.signal : undefined,
  });
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.error || "本地代理拒绝了请求。");
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function fillLanguages() {
  const engine = $("engine").value;
  const language = $("language");
  language.replaceChildren();
  const rows = engine === "phonon" ? state.phonon : state.piper;
  const languages = [];
  rows.forEach((row) => {
    const name = row.language;
    if (name && !languages.includes(name)) languages.push(name);
  });
  if (!languages.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "请先加载音色";
    language.append(option);
    fillVoices();
    return;
  }
  languages.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    language.append(option);
  });
  if (engine === "piper" && languages.includes("zh")) language.value = "zh";
  if (engine === "phonon" && languages.includes("en")) language.value = "en";
  fillVoices();
}

function fillVoices() {
  const engine = $("engine").value;
  const language = $("language").value;
  const voice = $("voice");
  voice.replaceChildren();
  const rows = (engine === "phonon" ? state.phonon : state.piper).filter((row) => !language || row.language === language);
  if (!rows.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "没有音色";
    voice.append(option);
    fillSpeaker();
    return;
  }
  rows.forEach((row) => {
    const option = document.createElement("option");
    option.value = engine === "phonon" ? row.voice || row.name || row.id : row.voice;
    option.textContent = engine === "phonon" ? (row.label || row.voice) : row.voice;
    option.dataset.raw = JSON.stringify(row);
    voice.append(option);
  });
  fillSpeaker();
}

function selectedVoice() {
  const option = $("voice").selectedOptions[0];
  if (!option || !option.dataset.raw) return null;
  return JSON.parse(option.dataset.raw);
}

function fillSpeaker() {
  const row = selectedVoice();
  const label = $("speaker-label");
  const speaker = $("speaker");
  speaker.replaceChildren();
  const speakers = row && row.speakers && Object.keys(row.speakers).length ? row.speakers : null;
  if ($("engine").value !== "piper" || !speakers) {
    label.hidden = true;
    return;
  }
  label.hidden = false;
  Object.keys(speakers).forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name + "（" + speakers[name] + "）";
    speaker.append(option);
  });
}

function updateCounter() {
  const text = $("text").value;
  const engine = $("engine").value;
  const limit = engine === "phonon" ? 1000 : 2000;
  const count = engine === "phonon" ? text.length : text.trim().length;
  let note = count + " / " + limit;
  if (engine === "phonon" && HAN.test(text)) note += "。Phonon 不接受汉字。";
  if (count > limit) note += "。超过上限。";
  $("counter").textContent = note;
}

function payloadFromForm() {
  const engine = $("engine").value;
  const text = $("text").value;
  const voice = $("voice").value;
  if (!voice) throw new Error("请先加载并选择音色。");
  const body = { engine, text, voice };
  if (engine === "piper") body.language = $("language").value;
  if (engine === "phonon") body.language = "en";
  if (! $("speaker-label").hidden) body.speaker = $("speaker").value;
  return body;
}

function setMetrics(upstream) {
  const headers = upstream && upstream.headers ? upstream.headers : {};
  const find = (name) => headers[name] || headers[name.toLowerCase()] || "—";
  $("metric-status").textContent = upstream ? String(upstream.status) : "—";
  $("metric-engine").textContent = find("X-Engine");
  $("metric-rate").textContent = find("X-Sample-Rate");
  $("metric-duration").textContent = find("X-Audio-Duration");
  $("metric-synth").textContent = find("X-Synth-Seconds");
}

async function checkHealth() {
  setBanner("", "");
  $("connection-state").textContent = "正在请求健康检查";
  const upstream = await proxy("GET", "/api/health", null, null);
  showDetail(upstream);
  $("metric-status").textContent = String(upstream.status);
  if (upstream.status === 200) {
    $("connection-state").textContent = "健康检查已返回";
    setBanner("ok", "已收到健康检查。Phonon 的 inferenceReady 为 false 只表示进程没有常驻。");
  } else {
    $("connection-state").textContent = "健康检查未成功";
    setBanner(upstream.status === 401 || upstream.status === 403 ? "bad" : "warn", statusHint(upstream.status) || ("HTTP " + upstream.status));
  }
}

async function loadVoices() {
  setBanner("", "");
  const piper = await proxy("GET", "/api/voices", null, null);
  const phonon = await proxy("GET", "/api/voices", { engine: "phonon" }, null);
  if (piper.status !== 200 || phonon.status !== 200) {
    showDetail({ piper, phonon });
    setBanner("bad", statusHint(piper.status) || statusHint(phonon.status) || "音色清单没有成功返回。");
    return;
  }
  state.piper = piper.json && piper.json.voices ? piper.json.voices : [];
  state.phonon = phonon.json && phonon.json.voices ? phonon.json.voices : [];
  fillLanguages();
  showDetail({ piperCount: state.piper.length, phononCount: state.phonon.length });
  setBanner("ok", "已加载 Piper " + state.piper.length + " 条、Phonon " + state.phonon.length + " 条。");
}

async function speak() {
  releaseAudio();
  $("download").disabled = true;
  setMetrics(null);
  $("result-state").textContent = "正在等待整段 WAV";
  setBanner("", "");
  const body = payloadFromForm();
  state.controller = new AbortController();
  $("cancel").disabled = false;
  const timer = setTimeout(() => state.controller.abort(), 200000);
  try {
    const upstream = await proxy("POST", "/api/tts", null, body);
    setMetrics(upstream);
    showDetail({
      status: upstream.status,
      contentType: upstream.contentType,
      headers: upstream.headers,
      json: upstream.json,
      errorText: upstream.errorText,
    });
    if (upstream.status !== 200 || !String(upstream.contentType || "").startsWith("audio/wav") || !upstream.bodyBase64) {
      $("result-state").textContent = "没有得到 WAV";
      setBanner(upstream.status === 401 || upstream.status === 403 ? "bad" : "warn", statusHint(upstream.status) || ("HTTP " + upstream.status));
      return;
    }
    const binary = atob(upstream.bodyBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    if (bytes.length < 12 || String.fromCharCode(...bytes.slice(0, 4)) !== "RIFF") {
      throw new Error("响应不是 WAV。");
    }
    const blob = new Blob([bytes], { type: "audio/wav" });
    state.objectUrl = URL.createObjectURL(blob);
    $("player").src = state.objectUrl;
    state.downloadName = ($("engine").value + "-" + ($("voice").value || "voice") + ".wav").replace(/[^\w.\-]+/g, "_");
    $("download").disabled = false;
    $("result-state").textContent = "已收到整段 WAV";
    setBanner("ok", "可以播放或下载。这是本次响应，不是预先放好的音频。");
  } catch (error) {
    if (error.name === "AbortError") {
      $("result-state").textContent = "已停止等待";
      setBanner("warn", "已停止等待本次响应。服务端可能仍在合成，这个操作不能取消服务器上的推理。");
    } else {
      $("result-state").textContent = "请求没有完成";
      setBanner("bad", error.message || "请求失败。");
      showDetail({ error: error.message, status: error.status || null });
    }
  } finally {
    clearTimeout(timer);
    state.controller = null;
    $("cancel").disabled = true;
  }
}

$("toggle-token").addEventListener("click", () => {
  const input = $("token");
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  $("toggle-token").textContent = show ? "隐藏" : "显示";
});
$("clear-token").addEventListener("click", () => {
  $("token").value = "";
  $("token").type = "password";
  $("toggle-token").textContent = "显示";
});
$("check-health").addEventListener("click", () => {
  checkHealth().catch((error) => setBanner("bad", error.message));
});
$("load-voices").addEventListener("click", () => {
  loadVoices().catch((error) => setBanner("bad", error.message));
});
$("engine").addEventListener("change", () => {
  fillLanguages();
  updateCounter();
});
$("language").addEventListener("change", fillVoices);
$("voice").addEventListener("change", fillSpeaker);
$("text").addEventListener("input", updateCounter);
$("speak").addEventListener("click", () => {
  speak().catch((error) => setBanner("bad", error.message));
});
$("cancel").addEventListener("click", () => {
  if (state.controller) state.controller.abort();
});
$("download").addEventListener("click", () => {
  if (!state.objectUrl) return;
  const link = document.createElement("a");
  link.href = state.objectUrl;
  link.download = state.downloadName;
  link.click();
});
window.addEventListener("pagehide", releaseAudio);
fillLanguages();
updateCounter();
