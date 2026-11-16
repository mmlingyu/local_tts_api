import { KokoroTTS, env } from "@uzen/kokoro-js";

const MODEL = "onnx-community/Kokoro-82M-v1.1-zh-ONNX";
env.wasmPaths = new URL("/ort/", location.href).href;

const VOICES = new Set(["zf_001", "zf_002", "zm_009", "zm_010"]);
let tts = null;
let device = null;
let loading = null;

export async function loadKokoroModel() {
  if (tts) return { device };
  if (loading) return loading;
  loading = (async () => {
    const adapter = await navigator.gpu?.requestAdapter().catch(() => null);
    device = adapter ? "webgpu" : "wasm";
    const options = { dtype: "fp32", device, voicePath: "/kokoro/voices" };
    try {
      tts = await KokoroTTS.from_pretrained(MODEL, options);
    } catch (error) {
      if (device !== "webgpu") throw error;
      device = "wasm";
      tts = await KokoroTTS.from_pretrained(MODEL, { ...options, device });
    }
    return { device };
  })().catch((error) => {
    loading = null;
    throw error;
  });
  return loading;
}

export async function synthesizeKokoro(text, voice, speed = 1) {
  const cleaned = String(text || "").trim();
  if (!cleaned) throw new Error("请输入要朗读的文本。");
  if (cleaned.length > 1500) throw new Error("Kokoro 文本不能超过 1500 字。");
  if (!VOICES.has(voice)) throw new Error("这个对照页只使用现有的四个中文音色。");
  await loadKokoroModel();
  const started = performance.now();
  const audio = await tts.generate(cleaned, { voice, speed: Number(speed) });
  const samples = audio.audio;
  const sampleRate = audio.sampling_rate || 24000;
  if (!samples?.length) throw new Error("Kokoro 合成结果为空。");
  return { samples, sampleRate, synthMs: performance.now() - started, device };
}
