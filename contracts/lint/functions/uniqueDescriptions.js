// 같은 뜻(description)을 가진 컴포넌트 스키마가 둘 이상이면 위반. 왜: 같은 개념을 두 번 정의하는 것을 막는다(D117).
export default function uniqueDescriptions(schemas) {
  if (!schemas || typeof schemas !== 'object') return [];
  const seen = new Map(); const out = [];
  for (const [name, s] of Object.entries(schemas)) {
    const d = (s && typeof s.description === 'string') ? s.description.trim() : '';
    if (!d) continue;
    if (seen.has(d)) out.push({ message: `'${name}' 와 '${seen.get(d)}' 의 뜻이 같다(같은 개념을 두 번 정의)`, path: [name, 'description'] });
    else seen.set(d, name);
  }
  return out;
}
