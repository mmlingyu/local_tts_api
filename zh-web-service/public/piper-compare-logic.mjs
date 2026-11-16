/** Pure helpers for the Piper / Kokoro comparison page. No network and no model. */

export const RTF_DEFINITION =
  "RTF = 服务端整段合成耗时（秒）÷ WAV 音频时长（秒）。小于 1 表示整段合成比实时播放更快。这不是流式首音时间；接口一次返回完整 WAV，首音时间未测量。";

export const FIRST_AUDIO_NOTE = "未测量。响应是整段 WAV，播放要等整段返回之后才能开始，不能把它写成流式首音。";

export const PRESETS = [
  {
    id: "poly-bank",
    category: "多音字",
    label: "银行 / 行长 / 重庆",
    text: "银行行长到了重庆。",
  },
  {
    id: "poly-title",
    category: "多音字",
    label: "这位行长（应读 háng）",
    text: "这位行长来了。",
  },
  {
    id: "poly-grow",
    category: "多音字",
    label: "长",
    text: "他长大后想长成大人。",
  },
  {
    id: "poly-music",
    category: "多音字",
    label: "音乐",
    text: "这首音乐很好听。",
  },
  {
    id: "poly-return",
    category: "多音字",
    label: "还",
    text: "钱还没还。",
  },
  {
    id: "num-date",
    category: "数字日期",
    label: "日期时间",
    text: "2026年11月16日12:30开会。",
  },
  {
    id: "num-percent",
    category: "数字日期",
    label: "百分数",
    text: "完成了98.76%。",
  },
  {
    id: "num-temp",
    category: "数字日期",
    label: "温度",
    text: "气温是-7°C。",
  },
  {
    id: "num-money",
    category: "金额",
    label: "金额",
    text: "报价是12.50元，约3.2万元。",
  },
  {
    id: "mix-web",
    category: "中英混读",
    label: "产品名",
    text: "请打开 WebGPU，模型是 Kokoro-82M。",
  },
  {
    id: "mix-version",
    category: "中英混读",
    label: "版本号",
    text: "版本号是 GPT-4o。",
  },
  {
    id: "tone-boss",
    category: "变调轻声",
    label: "三声",
    text: "老板很好。",
  },
  {
    id: "tone-book",
    category: "变调轻声",
    label: "一",
    text: "我买了一本书。",
  },
  {
    id: "tone-not",
    category: "变调轻声",
    label: "不",
    text: "我今天不去。",
  },
  {
    id: "tone-look",
    category: "变调轻声",
    label: "看一看",
    text: "看一看。",
  },
  {
    id: "tone-table",
    category: "变调轻声",
    label: "轻声",
    text: "这是一张桌子。好吧。",
  },
  {
    id: "er-yard",
    category: "儿化",
    label: "小院儿",
    text: "小院儿很安静。",
  },
  {
    id: "er-flower",
    category: "儿化",
    label: "花儿",
    text: "花儿开了。",
  },
  {
    id: "er-daughter",
    category: "儿化",
    label: "女儿",
    text: "她有一个女儿。",
  },
  {
    id: "punct",
    category: "标点",
    label: "停顿",
    text: "你好。你好！你好？你好，世界、朋友。",
  },
  {
    id: "long",
    category: "长文本",
    label: "整段",
    text: "今天下午三点，项目组在三楼会议室讨论本地语音。银行客户要听清楚日期、金额和门牌，例如2026年11月16日还款12.50元，利率大约是3.25%。请把 WebGPU 和 CPU 两条路径分开记录，不要把整段耗时说成首音时间。小院儿里很安静，桌子上有一本书。老板说今天不去现场，音乐可以先关掉。这段文字用来观察长句的整段合成耗时、音频时长和 RTF，不代表已经做过人工音质评分。",
  },
];

export function categories() {
  const seen = [];
  for (const preset of PRESETS) {
    if (!seen.includes(preset.category)) seen.push(preset.category);
  }
  return seen;
}

export function rtf(synthSeconds, durationSeconds) {
  if (!Number.isFinite(synthSeconds) || synthSeconds < 0) return null;
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) return null;
  return synthSeconds / durationSeconds;
}

export function parseWavPcm16(buffer) {
  const bytes = buffer instanceof ArrayBuffer ? new Uint8Array(buffer) : new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const ascii = (offset, length) => String.fromCharCode(...bytes.subarray(offset, offset + length));
  if (bytes.byteLength < 44 || ascii(0, 4) !== "RIFF" || ascii(8, 4) !== "WAVE") {
    throw new Error("返回的不是 WAV。");
  }
  let offset = 12;
  let sampleRate = 0;
  let channels = 0;
  let bits = 0;
  let dataOffset = -1;
  let dataSize = 0;
  while (offset + 8 <= bytes.byteLength) {
    const id = ascii(offset, 4);
    const size = view.getUint32(offset + 4, true);
    const start = offset + 8;
    if (start + size > bytes.byteLength) throw new Error("WAV 被截断。");
    if (id === "fmt ") {
      channels = view.getUint16(start + 2, true);
      sampleRate = view.getUint32(start + 4, true);
      bits = view.getUint16(start + 14, true);
    } else if (id === "data") {
      dataOffset = start;
      dataSize = size;
      break;
    }
    offset = start + size + (size % 2);
  }
  if (bits !== 16 || channels !== 1 || sampleRate <= 0 || dataOffset < 0 || dataSize < 2) {
    throw new Error("只接受 16-bit 单声道 WAV。");
  }
  const samples = dataSize / 2;
  let peak = 0;
  for (let index = 0; index < samples; index += 1) {
    peak = Math.max(peak, Math.abs(view.getInt16(dataOffset + index * 2, true)) / 32768);
  }
  if (peak === 0) throw new Error("WAV 是静音。");
  return {
    sampleRate,
    samples,
    durationSeconds: samples / sampleRate,
    peak,
  };
}

export function formatSeconds(value) {
  return Number.isFinite(value) ? value.toFixed(3) : "—";
}

export function kokoroAvailableHere(locationLike) {
  const port = String(locationLike.port || "");
  const host = locationLike.hostname;
  return (host === "127.0.0.1" || host === "localhost") && port === "8787";
}
