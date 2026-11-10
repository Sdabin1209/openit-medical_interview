// enum 값마다 뜻이 있어야 한다: x-enum-descriptions 가 enum 의 모든 값을 덮어야 한다. 왜: 값의 뜻이 없으면 무엇을 넣을지 모른다.
export default function enumMeanings(schema) {
  if (!schema || !Array.isArray(schema.enum)) return [];
  const d = schema['x-enum-descriptions'];
  if (!d || typeof d !== 'object') return [{ message: 'enum 에 x-enum-descriptions(값: 뜻)가 없다' }];
  const miss = schema.enum.filter(v => typeof d[String(v)] !== 'string' || !d[String(v)].trim());
  return miss.length ? [{ message: `뜻이 없는 enum 값: ${miss.join(', ')}` }] : [];
}
