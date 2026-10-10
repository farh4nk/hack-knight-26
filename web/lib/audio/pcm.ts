export const TARGET_SAMPLE_RATE = 16000;

export function float32ToInt16(input: Float32Array): Int16Array {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output;
}

export function int16ToFloat32(input: Int16Array): Float32Array {
  const output = new Float32Array(input.length);
  for (let i = 0; i < input.length; i++) {
    output[i] = input[i] < 0 ? input[i] / 0x8000 : input[i] / 0x7fff;
  }
  return output;
}

export function resampleLinear(
  input: Float32Array,
  fromRate: number,
  toRate: number = TARGET_SAMPLE_RATE,
): Float32Array {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const outputLength = Math.round(input.length / ratio);
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i * ratio;
    const i0 = Math.floor(srcIndex);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const t = srcIndex - i0;
    output[i] = input[i0] * (1 - t) + input[i1] * t;
  }
  return output;
}

export function resampleTo16kHz(input: Float32Array, fromRate: number): Float32Array {
  return resampleLinear(input, fromRate, TARGET_SAMPLE_RATE);
}

export function resampleFrom16kHz(input: Float32Array, toRate: number): Float32Array {
  return resampleLinear(input, TARGET_SAMPLE_RATE, toRate);
}