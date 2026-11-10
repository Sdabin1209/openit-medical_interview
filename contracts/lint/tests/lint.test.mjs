// 린트 규칙 자체 시험: 정상 문서는 통과(rc=0), 위반 문서는 기대한 규칙 코드로 실패해야 한다.
import { test } from 'node:test'; import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process'; import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url'; import path from 'node:path';
const here = path.dirname(fileURLToPath(import.meta.url)); const root = path.resolve(here, '../..');
const ruleset = path.join(root, 'lint/ruleset.yaml'); const spectral = path.join(root, 'node_modules/.bin/spectral');
const tmp = path.join(root, 'build/lint-tests'); mkdirSync(tmp, { recursive: true });
const good = readFileSync(path.join(here, 'fixtures/good.yaml'), 'utf8');
function lint(text, name) {
  const f = path.join(tmp, name + '.yaml'); writeFileSync(f, text);
  const r = spawnSync(spectral, ['lint', '-r', ruleset, '-f', 'json', '--fail-severity', 'error', f], { encoding: 'utf8' });
  let codes = []; try { codes = JSON.parse(r.stdout).filter(d => d.severity === 0).map(d => d.code); } catch {}
  return { rc: r.status, codes };
}
test('정상 문서는 통과', () => { const r = lint(good, 'good'); assert.equal(r.rc, 0, JSON.stringify(r.codes)); });
const cases = {
  'openit-schema-meaning': [/TurnCount: \{ type: integer, minimum: 0, maximum: 500, description: 세션의 턴 수,/, 'TurnCount: { type: integer, minimum: 0, maximum: 500,'],
  'openit-schema-owner-basis': [/, x-owner: kiosk-frontend, x-basis: 시험 \}/, ', x-owner: kiosk-frontend }'],
  'openit-owner-area': [/x-owner: kiosk-frontend/, 'x-owner: nobody'],
  'openit-property-meaning': [/, description: 이번 턴의 발화 \}/, ' }'],
  'openit-property-ref': [/utterance: \{ \$ref: "#\/components\/schemas\/UserUtterance", description: 이번 턴의 발화 \}/, 'utterance: { type: string, maxLength: 5, description: 이번 턴의 발화 }'],
  'openit-string-range': [/minLength: 1, maxLength: 1000,/, 'minLength: 1,'],
  'openit-number-range': [/minimum: 0, maximum: 500,/, 'minimum: 0,'],
  'openit-array-range': [/Utterances: \{ type: array, maxItems: 10,/, 'Utterances: { type: array,'],
  'openit-object-closed': [/      additionalProperties: false\n/, ''],
  'openit-enum-meanings': [/x-enum-descriptions: \{ NEXT: 다음 문항, REASK: 다시 묻기 \}/, 'x-enum-descriptions: { NEXT: 다음 문항 }'],
  'openit-unique-meaning': [/description: 세션의 턴 수/, 'description: 턴 요청'],
  'openit-body-ref': [/requestBody:\n        required: true\n        content: \{ application\/json: \{ schema: \{ \$ref: "#\/components\/schemas\/TurnRequest" \} \} \}/, 'requestBody:\n        required: true\n        content: { application/json: { schema: { type: object } } }'],
  'openit-operation-owner': [/      x-owner: survey-service\n      requestBody/, '      requestBody'],
};
for (const [code, [re, rep]] of Object.entries(cases)) {
  test(`위반: ${code}`, () => {
    assert.match(good, re, `고칠 자리를 찾지 못함: ${code}`);
    const r = lint(good.replace(re, rep), code);
    assert.equal(r.rc, 1, `${code}: rc=${r.rc}`); assert.ok(r.codes.includes(code), `${code} 가 안 나옴: ${r.codes}`);
  });
}
test('규칙의 영역 목록 = areas.yaml', () => {
  const areas = readFileSync(path.join(root, 'areas.yaml'), 'utf8').match(/areas: \[(.*)\]/)[1].split(',').map(s => s.trim());
  const rs = readFileSync(ruleset, 'utf8'); const m = rs.match(/openit-owner-area:[\s\S]*?values: \[(.*)\]/);
  assert.deepEqual(m[1].split(',').map(s => s.trim()), areas);
});
