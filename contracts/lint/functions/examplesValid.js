// 컴포넌트의 examples(JSON Schema 2020-12 의 표준 예시)가 자기 스키마를 만족해야 한다. 왜: Spectral 표준 규칙 oas3-valid-schema-example 은
// 단수 example 만 검증하고 OpenAPI 3.1 의 examples 배열은 검증하지 않아서, 예시가 틀려도 린트가 통과한다.
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
export default function examplesValid(schema, _opts, context) {
  const base = (context && context.path) ? context.path : [];
  if (!schema || typeof schema !== 'object' || !Array.isArray(schema.examples)) return [];
  const ajv = new Ajv2020({ strict: false, allErrors: true });
  addFormats(ajv);
  let validate;
  try { validate = ajv.compile({ ...schema, examples: undefined }); }
  catch (e) { return [{ message: `예시를 검증할 스키마를 만들지 못했다: ${e.message}` }]; }
  const out = [];
  schema.examples.forEach((ex, i) => {
    if (!validate(ex)) out.push({ message: `examples[${i}] 가 스키마를 어긴다: ${ajv.errorsText(validate.errors)}`, path: [...base, 'examples', i] });
  });
  return out;
}
