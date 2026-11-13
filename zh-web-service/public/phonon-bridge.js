const $ = (id) => document.getElementById(id);
const endpoint = "http://127.0.0.1:8790/api/tts";
const voicesUrl = "http://127.0.0.1:8790/api/voices";
const hasHan = (text) => /\p{Script=Han}/u.test(text);
const startHint = "powershell -ExecutionPolicy Bypass -File D:\\aispace\\phonon\\start-phonon-web.ps1";

let languageClass = hasHan($("text").value);
let lastObjectURL = null;
let running = false;

function phononName() {
  const opt = $("phonon-voice").selectedOptions[0];
  return (opt && (opt.dataset.name || opt.textContent)) || "default";
}

function renderEngine() {
  const phonon = $("engine").value === "phonon";
  $("voice").disabled = phonon || running;
  $("phonon-voice").disabled = !phonon || running;
  $("speed").disabled = phonon;
  $("engine-note").textContent = phonon
    ? `已选 Phonon 31m · ${phononName()} · 仅英文 · 固定语速 1× · 请在下方绿色框选择官方音色（共 ${$("phonon-voice").options.length} 个）`
    : "已选 Kokoro · 中文 / 混合 / 英文 · 浏览器 WebGPU 或 WASM";
}

function applyDefault(force = false) {
  const current = hasHan($("text").value);
  if (force || current !== languageClass) {
    $("engine").value = current ? "kokoro" : "phonon";
    if (!current) $("voice").value = "af_maple";
  }
  languageClass = current;
  renderEngine();
}

$("text").addEventListener("input", () => applyDefault());
$("engine").addEventListener("change", () => {
  if ($("engine").value === "kokoro" && !hasHan($("text").value)) $("voice").value = "af_maple";
  renderEngine();
});
$("phonon-voice").addEventListener("change", renderEngine);
for (const id of ["example-zh", "example-mix", "example-en"]) {
  $(id).addEventListener("click", () => queueMicrotask(() => applyDefault(true)));
}
applyDefault(true);

function warn(message) {
  $("status").textContent = message;
}

function groupOf(v) {
  if (v.id === "default") return "默认";
  if (v.locale === "character") return "角色";
  const region = v.locale === "en-GB" ? "英式" : "美式";
  if (v.gender === "female") return region + "女声";
  if (v.gender === "male") return region + "男声";
  return region;
}

function fillPhononVoices(voices) {
  if (!Array.isArray(voices) || voices.length < 2) return;
  const sel = $("phonon-voice");
  const current = sel.value || "default";
  const groups = new Map();
  sel.replaceChildren();
  for (const v of voices) {
    const g = groupOf(v);
    if (!groups.has(g)) {
      const og = document.createElement("optgroup");
      og.label = g;
      sel.append(og);
      groups.set(g, og);
    }
    const o = document.createElement("option");
    o.value = v.id;
    o.textContent = v.label || v.name;
    o.dataset.name = v.name;
    groups.get(g).append(o);
  }
  sel.value = [...sel.options].some((o) => o.value === current) ? current : "default";
  renderEngine();
}

fetch(voicesUrl, { cache: "no-store", signal: AbortSignal.timeout(8000) })
  .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
  .then((data) => { if (data && data.voices) fillPhononVoices(data.voices); })
  .catch(() => { /* 页面已内置 38 个音色，接口失败时仍可选择 */ });

$("generate").onclick = async () => {
  if (running) return;
  const text = $("text").value.trim();
  if (!text) { warn("请输入要朗读的文本。"); return; }
  const phonon = $("engine").value === "phonon";
  if (phonon && hasHan(text)) {
    warn("引擎：Phonon 31m\nPhonon 目前只有英文模型，中文或中英混合请改用 Kokoro。");
    return;
  }
  if (phonon && text.length > 1000) {
    warn("引擎：Phonon 31m\n文本超过 1000 字，请缩短后再试。");
    return;
  }
  running = true;
  $("generate").disabled = true;
  $("engine").disabled = true;
  renderEngine();
  try {
    if (phonon) {
      const chosenId = $("phonon-voice").value || "default";
      const chosenName = phononName();
      const activeLabel = "引擎：Phonon 31m · " + chosenName;
      $("status").textContent = activeLabel + "\n正在合成…";
      let response;
      try {
        response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, voice: chosenId }),
        });
      } catch (err) {
        throw new Error("无法连接本机 Phonon 服务（127.0.0.1:8790）。请先运行：\n" + startHint + "\n" + (err && err.message ? err.message : ""));
      }
      if (!response.ok) {
        let detail = "合成失败 HTTP " + response.status;
        try { const data = await response.json(); if (data && data.error) detail = data.error; } catch {}
        throw new Error(detail);
      }
      const blob = await response.blob();
      if (lastObjectURL) URL.revokeObjectURL(lastObjectURL);
      lastObjectURL = URL.createObjectURL(blob);
      $("player").src = lastObjectURL;
      $("download").href = lastObjectURL;
      $("download").download = "phonon-" + String(chosenName).replaceAll(" ", "-") + ".wav";
      $("download").hidden = false;
      const info = {
        engine: "Phonon 31m",
        voice: response.headers.get("X-Voice") || chosenName,
        voiceId: response.headers.get("X-Voice-ID") || chosenId,
        language: "en",
        device: "cpu",
        quant: "q8",
        durationSeconds: Number(response.headers.get("X-Audio-Duration")),
        synthesisSeconds: Number(response.headers.get("X-Synth-Seconds")),
        rtf: Number(response.headers.get("X-RTF")),
        sampleRate: Number(response.headers.get("X-Sample-Rate")),
        peak: Number(response.headers.get("X-Audio-Peak")),
      };
      const label = "引擎：Phonon 31m · " + info.voice;
      const dur = Number.isFinite(info.durationSeconds) ? info.durationSeconds.toFixed(2) : "—";
      const syn = Number.isFinite(info.synthesisSeconds) ? info.synthesisSeconds.toFixed(2) : "—";
      const rtf = Number.isFinite(info.rtf) ? info.rtf.toFixed(3) : "—";
      $("status").textContent = label + `\n成功：${dur} 秒音频 · 合成 ${syn} 秒 · RTF ${rtf}`;
      $("details").textContent = label + "\n" + JSON.stringify(info, null, 2);
      try { await $("player").play(); } catch { $("status").textContent += "\n请点击播放器播放。"; }
    } else {
      if (!window.zhTts || typeof window.zhTts.synthesize !== "function") {
        throw new Error("Kokoro 尚未就绪，请稍候再试。");
      }
      $("status").textContent = "引擎：Kokoro · " + $("voice").value + "\n正在合成…";
      await window.zhTts.synthesize($("text").value, $("voice").value, $("speed").value);
      const details = $("details");
      if (details && !details.textContent.includes("引擎：")) {
        details.textContent = "引擎：Kokoro · " + $("voice").value + "\n" + details.textContent;
      }
      if (!$("status").textContent.includes("引擎：")) {
        $("status").textContent = "引擎：Kokoro · " + $("voice").value + "\n" + $("status").textContent;
      }
    }
  } catch (err) {
    warn(( $("engine").value === "phonon" ? ("引擎：Phonon 31m · " + phononName() + "\n") : "引擎：Kokoro\n") + "错误：" + (err && err.message ? err.message : String(err)));
  } finally {
    running = false;
    $("generate").disabled = false;
    $("engine").disabled = false;
    renderEngine();
  }
};

window.phononBridgeReady = true;
window.phononBridgeVersion = 18;
