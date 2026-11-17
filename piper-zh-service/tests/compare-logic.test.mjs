import assert from "node:assert/strict";
import test from "node:test";
import { FIRST_AUDIO_NOTE, LEGACY_PIPER_MESSAGE, LOCAL_PIPER_8800, POCKET_NON_ENGLISH, POCKET_VOICES, PRESETS, RTF_DEFINITION, isLoopbackHttp, kokoroAllowedFor, kokoroAvailableHere, parseWavPcm16, piperApiBase, piperSupportsLanguageFields, pocketCompareAllowed, pocketRequest, pocketVoiceError, presetsFor, rtf, ttsPayload } from "../static/compare-logic.mjs";

test("RTF is full-utterance time divided by audio duration", () => {
  assert.equal(rtf(0.5, 2), 0.25);
  assert.equal(rtf(Number.NaN, 2), null);
  assert.equal(rtf(1, 0), null);
  assert.match(RTF_DEFINITION, /整段合成耗时/);
  assert.match(FIRST_AUDIO_NOTE, /未测量/);
  assert.doesNotMatch(RTF_DEFINITION, /首音时间是/);
});

test("presets cover the required Chinese cases and stay within the server limit", () => {
  const categories = new Set(PRESETS.map((item) => item.category));
  for (const name of ["多音字", "数字日期", "金额", "中英混读", "变调轻声", "儿化", "标点", "长文本"]) {
    assert.equal(categories.has(name), true, name);
  }
  assert.ok(PRESETS.every((item) => item.text.length > 0 && item.text.length <= 2000));
  assert.equal(new Set(PRESETS.map((item) => item.id)).size, PRESETS.length);
});

test("Piper endpoint stays on loopback and can leave 8791", () => {
  assert.equal(isLoopbackHttp("http://127.0.0.1:8800"), true);
  assert.equal(isLoopbackHttp("http://127.0.0.1:8791"), true);
  assert.equal(isLoopbackHttp("https://127.0.0.1:8800"), false);
  assert.equal(isLoopbackHttp("http://example.com:8800"), false);
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8787", protocol: "http:" }, ""), LOCAL_PIPER_8800);
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8787", protocol: "http:" }, "http://127.0.0.1:8800"), "http://127.0.0.1:8800");
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8791", protocol: "http:" }, ""), "http://127.0.0.1:8791");
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8800", protocol: "http:" }, ""), "http://127.0.0.1:8800");
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8787", protocol: "http:" }, "http://127.0.0.1:8791"), "http://127.0.0.1:8791");
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8800", protocol: "http:" }, "http://evil.example:8800"), "http://127.0.0.1:8800");
});

test("old Piper is recognized and is not sent language fields", () => {
  const oldHealth = { serviceVersion: "1.0.0", modelReady: true };
  assert.equal(piperSupportsLanguageFields(oldHealth, false), false);
  assert.equal(piperSupportsLanguageFields(oldHealth, true), false);
  assert.equal(piperSupportsLanguageFields({ serviceVersion: "1.1.0" }, false), false);
  assert.equal(piperSupportsLanguageFields({ serviceVersion: "1.1.0", voices: [] }, true), true);
  const blocked = ttsPayload("你好。", { language: "zh", voice: "zh_CN-chaowen-medium" }, false);
  assert.equal(blocked, null);
  assert.equal(JSON.stringify(blocked || {}).includes("language"), false);
  const sent = ttsPayload("你好。", { language: "zh", voice: "zh_CN-chaowen-medium" }, true);
  assert.deepEqual(sent, { text: "你好。", language: "zh", voice: "zh_CN-chaowen-medium" });
  assert.equal(LEGACY_PIPER_MESSAGE, "当前连接旧版Piper，请连接本机8800或升级服务");
  assert.equal(LOCAL_PIPER_8800, "http://127.0.0.1:8800");
  assert.equal(pocketRequest("Hello.", "english", "alba", false), null);
  assert.deepEqual(pocketRequest("Hello.", "english", "alba", true), {
    engine: "pocket",
    text: "Hello.",
    language: "english",
    voice: "alba",
    variant: "english_18m_2026-10",
  });
  assert.equal(POCKET_VOICES.length, 27);
  assert.equal(new Set(POCKET_VOICES).size, 27);
  assert.equal(POCKET_VOICES.includes("alba"), true);
  assert.equal(POCKET_VOICES.includes("daan"), true);
  assert.equal(POCKET_VOICES.includes("estelle"), true);
  assert.equal(pocketCompareAllowed("en"), true);
  assert.equal(pocketCompareAllowed("zh"), false);
  assert.equal(pocketCompareAllowed("fr"), false);
  assert.equal(pocketRequest("银行行长到了重庆。", "zh", "alba", true), null);
  assert.equal(pocketRequest("Bonjour.", "fr", "estelle", true), null);
  assert.equal(pocketVoiceError("zh", "alba", true), POCKET_NON_ENGLISH);
  assert.match(pocketVoiceError("en", "marius", false), /还没准备/);
  assert.equal(pocketVoiceError("en", "alba", true), null);
  assert.equal(pocketRequest("Hello.", "en", "marius", true).voice, "marius");
  assert.equal(pocketRequest("Hello.", "en", "hf://kyutai/pocket-tts/x", true), null);
});

test("Kokoro stays on Chinese and other languages have their own lines", () => {
  assert.equal(kokoroAllowedFor("zh"), true);
  for (const language of ["en", "ja", "ko", "fr"]) {
    assert.equal(kokoroAllowedFor(language), false);
    assert.ok(presetsFor(language).length > 0);
    assert.ok(presetsFor(language).every((item) => item.text.length <= 2000));
  }
  assert.equal(presetsFor("zh").length, PRESETS.length);
});

test("Kokoro is only offered on the existing Chinese page origin", () => {
  assert.equal(kokoroAvailableHere({ hostname: "127.0.0.1", port: "8787" }), true);
  assert.equal(kokoroAvailableHere({ hostname: "127.0.0.1", port: "8791" }), false);
  assert.equal(kokoroAvailableHere({ hostname: "example.com", port: "8787" }), false);
});

test("WAV parser reads a 16-bit mono file", () => {
  const rate = 22050;
  const samples = 2205;
  const buffer = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(buffer);
  const write = (offset, text) => {
    for (let index = 0; index < text.length; index += 1) view.setUint8(offset + index, text.charCodeAt(index));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + samples * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples * 2, true);
  view.setInt16(44, 16000, true);
  const parsed = parseWavPcm16(buffer);
  assert.equal(parsed.sampleRate, rate);
  assert.equal(parsed.durationSeconds, 0.1);
  assert.ok(parsed.peak > 0);
});
