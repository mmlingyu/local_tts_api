import assert from "node:assert/strict";
import test from "node:test";
import { FIRST_AUDIO_NOTE, PRESETS, RTF_DEFINITION, isLoopbackHttp, kokoroAvailableHere, parseWavPcm16, piperApiBase, rtf } from "../static/compare-logic.mjs";

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
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8787", protocol: "http:" }, ""), "http://127.0.0.1:8791");
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8787", protocol: "http:" }, "http://127.0.0.1:8800"), "http://127.0.0.1:8800");
  assert.equal(piperApiBase({ hostname: "127.0.0.1", port: "8800", protocol: "http:" }, "http://evil.example:8800"), "http://127.0.0.1:8800");
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
