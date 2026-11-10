// 계약 시험: 표준 JSON Schema 2020-12 검증기(ajv)로 "받아들여야 할 값"과 "거부해야 할 값"을 components.yaml 에서 확인한다.
// 왜: 린트는 구조(뜻, 범위, 주인)만 보고 스키마가 틀린 값을 실제로 거부하는지는 보지 못한다.
import { test } from 'node:test'; import assert from 'node:assert/strict';
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from 'node:fs'; import { gunzipSync } from 'node:zlib'; import { spawnSync } from 'node:child_process'; import path from 'node:path'; import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js'; import Ajv from 'ajv'; import addFormats from 'ajv-formats'; import { parse } from 'yaml';
const here = path.dirname(fileURLToPath(import.meta.url)); const root = path.resolve(here, '../..');
const doc = parse(readFileSync(path.join(root, 'components.yaml'), 'utf8'));
const ajv = new Ajv2020({ strict: false, allErrors: true }); addFormats(ajv);
const validators = new Map();
function v(name) {
  if (!validators.has(name)) validators.set(name, ajv.compile({ components: doc.components, $ref: `#/components/schemas/${name}` }));
  return validators.get(name);
}
const ok = (name, value, msg) => assert.equal(v(name)(value), true, `${msg ?? name} 는 받아야 한다: ${ajv.errorsText(v(name).errors)}`);
const no = (name, value, msg) => assert.equal(v(name)(value), false, `${msg ?? name} 는 거부해야 한다`);
const ops = [];
for (const f of readdirSync(path.join(root, 'openapi'))) {
  const d = parse(readFileSync(path.join(root, 'openapi', f), 'utf8'));
  for (const [p, item] of Object.entries(d.paths ?? {})) for (const [m, op] of Object.entries(item)) if (op && typeof op === 'object' && op.operationId) ops.push({ file: f, path: p, method: m, op });
}
const U = '3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90';
const val = (key, value, status = 'ANSWERED', save = true, precision = 'exact') => ({ key, value, status, save, precision });

test('모든 컴포넌트의 examples 가 스키마를 만족한다(린트와 같은 검증을 시험에서도)', () => {
  let n = 0;
  for (const [name, s] of Object.entries(doc.components.schemas)) if (Array.isArray(s.examples)) { n++; s.examples.forEach((e, i) => ok(name, e, `${name}.examples[${i}]`)); }
  assert.ok(n >= 130, `예시를 단 컴포넌트가 ${n}개뿐이다`);
});
test('Repr-Digest: RFC 9530 의 실제 예시를 받고 길이가 어긋난 값을 거부한다', () => {
  ok('ReprDigestValue', 'sha-256=:d435Qo+nKZ+gLcUHn7GQtQ72hiBVAgqoLsZnZPiTGPk=:');
  no('ReprDigestValue', 'sha-256=:d435Qo+nKZ+gLcUHn7GQtQ72hiBVAgqoLsZnZPiTGPk:');
  no('ReprDigestValue', 'sha-256=:d435Qo+nKZ+gLcUHn7GQtQ72hiBVAgqoLsZnZPiTGPk=:x');
});
test('시작 코드는 6자리 숫자만 받는다', () => { ok('StartCodeValue', '482910'); no('StartCodeValue', '48291'); no('StartCodeValue', '48291A'); });
test('FHIR QuestionnaireResponse 는 status 가 없으면 거부한다', () => {
  no('FhirQuestionnaireResponse', { resourceType: 'QuestionnaireResponse' });
  no('FhirQuestionnaireResponse', { resourceType: 'Patient', status: 'completed' });
  ok('FhirQuestionnaireResponse', { resourceType: 'QuestionnaireResponse', status: 'completed', item: [{ linkId: 'Q1.D01' }] });
});
test('FHIR OperationOutcome 은 issue 가 없거나 비어 있으면 거부한다', () => {
  no('FhirOperationOutcome', { resourceType: 'OperationOutcome' }); no('FhirOperationOutcome', { resourceType: 'OperationOutcome', issue: [] });
  ok('FhirOperationOutcome', { resourceType: 'OperationOutcome', issue: [{ severity: 'error', code: 'not-found' }] });
});
test('JWT 클레임은 RFC 9068 필수 클레임이 빠지면 거부하고 그 밖의 클레임은 허용한다', () => {
  const full = { iss: 'https://platform/realms/openit', sub: 'u1', aud: 'survey-service', exp: 1783684200, iat: 1783680600, jti: 'j1', client_id: 'admin-console', realm_access: { roles: ['staff'] } };
  ok('UserIdentityClaims', { ...full, scope: 'openid', azp: 'x' });
  for (const k of ['iat', 'jti', 'client_id', 'aud', 'exp', 'iss', 'sub']) { const c = { ...full }; delete c[k]; no('UserIdentityClaims', c, `${k} 없는 클레임`); }
  ok('UserIdentityClaims', { ...full, aud: ['survey-service', 'release-gate'] }); no('UserIdentityClaims', { ...full, aud: 'unknown-service' });
});
test('JOSE 헤더: typ 이 at+jwt 또는 application/at+jwt 가 아니거나 alg 가 none 이면 거부한다', () => {
  ok('AccessTokenHeader', { typ: 'at+jwt', alg: 'RS256', kid: 'k1' }); ok('AccessTokenHeader', { typ: 'application/at+jwt', alg: 'ES256' }); no('AccessTokenHeader', { typ: 'application/jwt', alg: 'RS256' }); no('AccessTokenHeader', { typ: 'JWT', alg: 'RS256' }); no('AccessTokenHeader', { typ: 'at+jwt', alg: 'none' });
});
const NEXT_B = { action: 'NEXT', known: '진단 받음, 지금 약 먹음', topic: '뇌졸중(중풍) 진단을 받았는지와 지금 약을 먹는지', user_utterance: '중풍 진단 받았고, 약도 먹고 있어예.', next: { type: 'NEXT', question_id: 'Q1.D02', text: '혹시 심근경색이나 협심증으로 진단받으셨거나 현재 약물 치료 중이신가요?' } };
test('ResponseRequest: 정본 행은 받고 행동별 필수·금지 키와 next 조합을 어기면 거부한다', () => {
  ok('ResponseRequest', NEXT_B);
  ok('ResponseRequest', { action: 'START', topic: NEXT_B.topic, next: NEXT_B.next });
  ok('ResponseRequest', { action: 'REASK', reason: 'MISSING', ask: '일주일에 며칠 하는지', known: '', topic: 't', user_utterance: 'x', next: { type: 'SAME', question_id: 'Q8_1', text: 'q' } });
  ok('ResponseRequest', { action: 'CONFIRM', reason: 'CONFLICT_WITH_PREVIOUS', ask: 'a', previous: '일주일에 3일', current: '일주일에 5일', known: '', topic: 't', user_utterance: 'x', next: { type: 'SAME', question_id: 'Q8_1', text: 'q' } });
  ok('ResponseRequest', { action: 'SKIP', reason: 'REFUSED', hold: '일반담배', known: '', topic: 't', user_utterance: 'x', next: { type: 'END' } });
  ok('ResponseRequest', { action: 'REDIRECT', reason: 'OUT_OF_SCHEMA', note: '손발이 저림', known: '', topic: 't', user_utterance: 'x', next: { type: 'SAME', question_id: 'Q1.D01', text: 'q' } });
  no('ResponseRequest', { ...NEXT_B, action: 'START' }, 'START 에 known');
  const { known, ...noKnown } = NEXT_B; no('ResponseRequest', noKnown, 'NEXT 에 known 없음');
  const { user_utterance, ...noUtt } = NEXT_B; no('ResponseRequest', noUtt, 'NEXT 에 user_utterance 없음');
  no('ResponseRequest', { ...NEXT_B, action: 'REASK', reason: 'MISSING', next: { type: 'SAME', question_id: 'Q8_1', text: 'q' } }, 'REASK 에 ask 없음');
  no('ResponseRequest', { ...NEXT_B, action: 'CONFIRM', reason: 'CONFLICT_WITH_PREVIOUS', ask: 'a', next: { type: 'SAME', question_id: 'Q8_1', text: 'q' } }, 'CONFIRM 에 previous·current 없음');
  no('ResponseRequest', { ...NEXT_B, ask: 'a' }, 'NEXT 에 ask');
  no('ResponseRequest', { ...NEXT_B, next: { type: 'SAME', question_id: 'Q1.D02', text: 'q' } }, 'NEXT 에 SAME');
  no('ResponseRequest', { action: 'REASK', reason: 'MISSING', ask: 'a', known: '', topic: 't', user_utterance: 'x', next: { type: 'NEXT', question_id: 'Q8_1', text: 'q' } }, 'REASK 에 NEXT');
  no('ResponseRequest', { ...NEXT_B, next: { type: 'END', question_id: 'Q1.D02' } }, 'END 에 question_id');
  no('ResponseRequest', { ...NEXT_B, next: { type: 'NEXT' } }, 'NEXT 에 question_id·text 없음');
});
test('ActionExtraction: 정본 행은 받고 행동별 reason·targets·note 규칙을 어기면 거부한다', () => {
  const v1 = val('Q1.D01.diagnosed', true), v2 = val('Q1.D01.on_medication', true);
  ok('ActionExtraction', { action: 'NEXT', next_item: 'Q1.D02', values: [v1, v2] });
  ok('ActionExtraction', { action: 'REASK', reason: 'MISSING', next_item: 'Q8_1', values: [val('Q8_1.days', null, 'MISSING', false, 'unspecified')], targets: ['Q8_1.days'] });
  ok('ActionExtraction', { action: 'REDIRECT', reason: 'OUT_OF_SCHEMA', note: '손발이 저림', next_item: 'Q1.D01', values: [] });
  no('ActionExtraction', { action: 'NEXT', reason: 'MISSING', next_item: 'Q1.D02', values: [v1] }, 'NEXT 에 reason');
  no('ActionExtraction', { action: 'REASK', next_item: 'Q8_1', values: [] }, 'REASK 에 reason·targets 없음');
  no('ActionExtraction', { action: 'REDIRECT', reason: 'OFF_TOPIC', note: 'x', next_item: 'Q1.D01', values: [] }, 'OFF_TOPIC 에 note');
  no('ActionExtraction', { action: 'REDIRECT', reason: 'OUT_OF_SCHEMA', next_item: 'Q1.D01', values: [] }, 'OUT_OF_SCHEMA 에 note 없음');
  no('ActionExtraction', { action: 'NEXT', next_item: 'Q1.D02', values: [v1], extra: 1 }, '모르는 칸');
});
test('ExtractedValue: save 와 status, 값 없음과 precision 의 관계를 어기면 거부한다', () => {
  no('ExtractedValue', val('Q1.D01.diagnosed', true, 'ANSWERED', false)); no('ExtractedValue', val('Q1.D01.diagnosed', null, 'UNKNOWN', true, 'unspecified'));
  no('ExtractedValue', val('Q1.D01.diagnosed', null, 'UNKNOWN', false, 'exact')); no('ExtractedValue', val('Q1.D01.diagnosed', true, 'ANSWERED', true, 'unspecified'));
  ok('ExtractedValue', val('Q7_1[soju].amount', 2, 'CORRECTION')); ok('ExtractedValue', val('Q1.D01.diagnosed', null, 'UNKNOWN', false, 'unspecified'));
});
test('모델 패키지: LORA_A 와 LORA_B 가 하나씩이 아니면 거부한다', () => {
  const ref = { artifact_id: U, sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', size_bytes: 10 };
  const ad = (role) => ({ role, weights: ref, system_prompt: ref, serving_config: { max_new_tokens: 512, temperature: 0, constrained_decoding: true } });
  const m = (adapters) => ({ model_package_id: U, base_model: 'Qwen/Qwen3-8B', runtime_contract_version: 1, model_io_version: 'model-io-v2', model_runtime_version: '0.11.10', adapters, lineage: { dataset_version_id: U, base_model: 'Qwen/Qwen3-8B', training_run_ids: [U] }, evaluation: { dataset_version_id: U, metrics: [], created_at: '2026-11-10T09:30:00+09:00' }, created_at: '2026-11-10T09:30:00+09:00' });
  ok('ModelPackageManifest', m([ad('LORA_A'), ad('LORA_B')]));
  no('ModelPackageManifest', m([ad('LORA_A'), ad('LORA_A')]), 'A 둘'); no('ModelPackageManifest', m([]), '빈 배열'); no('ModelPackageManifest', m([ad('LORA_A')]), 'A 하나');
  no('ModelPackageManifest', { ...m([ad('LORA_A'), ad('LORA_B')]), model_io_version: 'model-io-v3' }, 'v3 는 활성이 아니다');
});
test('학습 결과: 성공인데 어댑터나 실행 기록이 없으면 거부한다', () => {
  const ref = { artifact_id: U, sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', size_bytes: 10 };
  const base = { training_run_id: U, finished_at: '2026-11-10T09:30:00+09:00' };
  ok('TrainingRunResult', { ...base, outcome: 'SUCCEEDED', adapter: ref, run_record: ref }); ok('TrainingRunResult', { ...base, outcome: 'FAILED' });
  no('TrainingRunResult', { ...base, outcome: 'SUCCEEDED' }); no('TrainingRunResult', { ...base, outcome: 'SUCCEEDED', run_record: ref });
});
test('실패 사례: 기계 독자용 모양에는 발화 원문이 없고, CONFIRMED 에는 기대 출력이 있어야 한다', () => {
  const base = { case_id: U, case_version: 1, kind: 'EXTRACT_FAILED', questionnaire_id: 'national-health', item_id: 'Q1.D01', created_at: '2026-11-10T09:30:00+09:00' };
  const exp = { action: 'NEXT', next_item: 'Q1.D02', values: [] };
  ok('FailureCaseExport', { ...base, review_status: 'UNREVIEWED' }); ok('FailureCaseExport', { ...base, review_status: 'CONFIRMED', expected: exp, reviewed_input: '중풍 진단 받았어요' });
  no('FailureCaseExport', { ...base, review_status: 'CONFIRMED' }, 'CONFIRMED 에 expected 없음');
  no('FailureCaseExport', { ...base, review_status: 'UNREVIEWED', utterance: '원문' }, '원문 칸'); no('FailureCaseExport', { ...base, review_status: 'UNREVIEWED', model_output: exp }, '모델 출력 칸');
  no('FailureCase', { ...base, review_status: 'CONFIRMED' }, '검토자용도 CONFIRMED 에 expected 필요');
  no('CaseReview', { review_status: 'CONFIRMED', base_case_version: 1 }); no('CaseReview', { review_status: 'DISMISSED' }); ok('CaseReview', { review_status: 'DISMISSED', base_case_version: 1 });
});
test('지표: 비율 단위의 값은 1 을 넘으면 거부한다', () => {
  ok('EvaluationMetric', { name: 'value_precision', value: 0.93, unit: 'ratio', sample_count: 400 }); no('EvaluationMetric', { name: 'value_precision', value: 1.2, unit: 'ratio', sample_count: 400 });
  ok('EvaluationMetric', { name: 'length_p95_ms', value: 1800, unit: 'milliseconds', sample_count: 400 });
  no('MetricComparison', { name: 'value_recall', unit: 'ratio', candidate_value: 1.5 }); ok('MetricComparison', { name: 'value_recall', unit: 'ratio', candidate_value: 0.9, active_value: 0.8 });
});
test('업무 로그: event_id 가 없거나 필요한 행위자가 없으면 거부한다', () => {
  const e = { event_id: U, kind: 'SESSION_STARTED', session_id: U, occurred_at: '2026-11-10T09:30:00+09:00' };
  ok('BusinessLogEntry', e); const { event_id, ...noId } = e; no('BusinessLogEntry', noId);
  no('BusinessLogEntry', { ...e, kind: 'RESULT_PULLED' }, '당겨 감에 actor_client 없음'); ok('BusinessLogEntry', { ...e, kind: 'RESULT_PULLED', actor_client: 'hospital-his' });
  no('BusinessLogEntry', { event_id: U, kind: 'SESSION_ENDED', occurred_at: '2026-11-10T09:30:00+09:00' }, '세션 사건에 session_id 없음');
  no('TraceDelivery', {}); ok('TraceDelivery', { business_logs: [e] });
});
test('결과 빈칸은 반복 키까지 칸을 가린다', () => {
  ok('ResultBlank', { item_id: 'Q7_1', key: 'Q7_1[soju].amount', reason: 'REASK_LIMIT' }); ok('ResultBlank', { item_id: 'Q9_2', reason: 'NOT_ASKED' }); no('ResultBlank', { item_id: 'Q7_1', key: 'Q7_1[soju].amount' });
});
test('구조의 숫자가 서로 맞는다(같은 구조에서 산출)', () => {
  const S = doc.components.schemas;
  const envMax = Math.max(...Object.entries(S).filter(([n]) => /Env$/.test(n)).map(([, s]) => Object.keys(s.properties).length));
  assert.ok(S.ContainerInputs.properties.env.maxItems >= envMax, `환경 입력 선언 상한 ${S.ContainerInputs.properties.env.maxItems} < 환경 입력 칸 수 ${envMax}`);
  assert.equal(S.DatasetImport.properties.pending_artifact_ids.maxItems, S.DatasetFiles.maxItems);
  assert.deepEqual(S.Exposure.properties.egress.items, { $ref: '#/components/schemas/EgressTarget' }); assert.equal(S.Exposure.properties.egress.maxItems, 32);
  for (const [n, s] of Object.entries(S)) if (s.format === 'uuid') assert.ok(s.pattern && s.maxLength === 36, `${n}: uuid 에 pattern 과 maxLength 가 없다`);
});
test('보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다', () => {
  for (const { file, path: p, method, op } of ops) for (const req of op.security ?? []) for (const [scheme, roles] of Object.entries(req)) {
    if (scheme === 'oidc' || scheme === 'machine_token') assert.ok(roles.length <= 1, `${file} ${method} ${p}: ${scheme} 요구에 역할이 둘 이상이다(AND 로 읽힘)`);
  }
  for (const id of ['listFailureCases', 'getFailureCase', 'getDeidentifiedTrace']) {
    const o = ops.find((x) => x.op.operationId === id).op; assert.ok(o.security.every((r) => !('machine_token' in r)), `${id} 에 기계 토큰이 있다`);
  }
  const rb = ops.find((x) => x.op.operationId === 'createRollbackRequest').op;
  assert.ok(rb.security.some((r) => r.oidc?.[0] === 'reviewer') && rb.security.some((r) => r.oidc?.[0] === 'operator') && rb.security.some((r) => r.machine_token?.[0] === 'rollback-requester'));
  assert.ok(!ops.some((x) => 'x-required-roles' in x.op), 'x-required-roles 가 남아 있다');
});
test('작업: 역할을 요구하면 403 이 있고 401 에는 WWW-Authenticate 가 있다', () => {
  for (const { file, path: p, method, op } of ops) {
    const roles = (op.security ?? []).some((r) => Object.values(r).some((a) => a.length > 0));
    if (roles) assert.ok(op.responses['403'], `${file} ${method} ${p}: 403 없음`);
  }
  assert.ok(doc.components.responses.Unauthorized.headers['WWW-Authenticate']); assert.ok(doc.components.responses.FhirUnauthorized.headers['WWW-Authenticate']); assert.ok(doc.components.responses.FhirUnavailable.headers['Retry-After']);
});
test('작업: 멱등 키는 필요한 작업에만 있고 위험 신호는 자연 키를 쓴다', () => {
  const has = (id) => (ops.find((x) => x.op.operationId === id).op.parameters ?? []).some((q) => q.$ref?.endsWith('parameters/IdempotencyKey'));
  for (const id of ['issueStartCode', 'createSubmission', 'createRollbackRequest', 'createDatasetImport']) assert.ok(has(id), `${id} 에 Idempotency-Key 가 없다`);
  assert.ok(!has('receiveRiskSignal'));
});
test('작업: 업로드에는 Repr-Digest 와 413 이 있다', () => {
  for (const id of ['uploadDatasetFile', 'uploadTrainingArtifact']) { const o = ops.find((x) => x.op.operationId === id).op; assert.ok((o.parameters ?? []).some((q) => q.$ref?.endsWith('parameters/ReprDigest')), id); assert.ok(o.responses['413'], id); }
});
test('모델 입출력 v3 의존 기능은 v3 이상에서만 켜진다고 표로 정의한다', () => {
  ok('ModelIoFeatureRequirements', [{ feature: 'CONFIRMING_STATE', minimum_model_io_version: 'model-io-v3' }, { feature: 'MEANING_ASKED_EXEMPTION', minimum_model_io_version: 'model-io-v3' }, { feature: 'STAFF_HELP_AFTER_EXPLAIN', minimum_model_io_version: 'model-io-v3' }]);
  no('ModelIoFeatureRequirement', { feature: 'CONFIRMING_STATE', minimum_model_io_version: 'model-io-v2' });
});

test('시각: 소수 초는 9자리까지이고 오프셋이 있어야 한다(10자리 거부)', () => {
  ok('Timestamp', '2026-11-10T09:30:00.123456789+09:00'); ok('Timestamp', '2026-11-10T00:00:00Z'); ok('Timestamp', '2026-11-10T09:30:00.5Z');
  no('Timestamp', '2026-11-10T09:30:00.1234567890Z', '소수 10자리'); no('Timestamp', '2026-11-10T09:30:00', '오프셋 없음'); no('Timestamp', '2026-11-10 09:30:00Z', '공백 구분');
});
test('v3 의존 기능 표: 기능마다 정확히 하나이고 중복과 누락을 거부한다', () => {
  const f = (feature) => ({ feature, minimum_model_io_version: 'model-io-v3' });
  ok('ModelIoFeatureRequirements', [f('CONFIRMING_STATE'), f('MEANING_ASKED_EXEMPTION'), f('STAFF_HELP_AFTER_EXPLAIN')]);
  no('ModelIoFeatureRequirements', [f('CONFIRMING_STATE'), f('CONFIRMING_STATE'), f('STAFF_HELP_AFTER_EXPLAIN')], '중복');
  no('ModelIoFeatureRequirements', [f('CONFIRMING_STATE'), f('MEANING_ASKED_EXEMPTION')], '누락(길이 2)');
  no('ModelIoFeatureRequirements', [f('CONFIRMING_STATE'), f('MEANING_ASKED_EXEMPTION'), f('MEANING_ASKED_EXEMPTION')], '하나 누락과 중복');
});
test('지표 slice 는 기준=값 표기만 받고 위반 코드는 정본에 이름이 있는 것만 받는다', () => {
  ok('MetricSlice', 'action=REASK'); ok('MetricSlice', 'violation_code=OUT_OF_CURRENT_ITEM'); ok('MetricSlice', 'constrained_decoding=on');
  no('MetricSlice', 'Q8_1.days'); no('MetricSlice', 'color=red'); no('MetricSlice', 'action=');
  ok('ViolationCode', 'UNKNOWN_ITEM'); no('ViolationCode', 'MADE_UP_CODE');
});
test('예시가 스키마를 어기면 린트가 실패하고 위치(경로)를 알린다', () => {
  const dir = path.join(root, 'build/contract-tests'); mkdirSync(dir, { recursive: true });
  const bad = `openapi: 3.1.0\ninfo: { title: t, version: 1.0.0, contact: { name: head } }\nservers: [ { url: "https://example.invalid" } ]\npaths: {}\ncomponents:\n  schemas:\n    Code: { type: string, pattern: "^[0-9]{6}$", maxLength: 6, examples: [ "482910", "48291A" ], description: 시험용 코드, x-owner: head, x-basis: 시험 }\n`;
  const f = path.join(dir, 'bad-example.yaml'); writeFileSync(f, bad);
  const r = spawnSync(path.join(root, 'node_modules/.bin/spectral'), ['lint', '-r', path.join(root, 'lint/ruleset.yaml'), '-f', 'json', '--fail-severity', 'error', f], { encoding: 'utf8' });
  assert.equal(r.status, 1, `rc=${r.status}`);
  const d = JSON.parse(r.stdout).filter((x) => x.code === 'openit-examples-valid');
  assert.equal(d.length, 1); assert.deepEqual(d[0].path, ['components', 'schemas', 'Code', 'examples', '1']);
});
// ---- FHIR R4: HL7 공식 JSON Schema(draft-06, CC0)로 전체 검증 (lint/tests/fixtures/fhir/README.md)
const fhir = JSON.parse(gunzipSync(readFileSync(path.join(here, 'fixtures/fhir/fhir.schema.json.gz'))).toString('utf8'));
delete fhir.$schema; delete fhir.id; delete fhir.oneOf; delete fhir.discriminator;
const fajv = new Ajv({ strict: false, allErrors: true });
fajv.addMetaSchema(JSON.parse(readFileSync(path.join(root, 'node_modules/ajv/dist/refs/json-schema-draft-06.json'), 'utf8')));
const fv = (name) => fajv.compile({ definitions: fhir.definitions, $ref: `#/definitions/${name}` });
const qr = (extra = {}) => ({ resourceType: 'QuestionnaireResponse', status: 'completed', questionnaire: 'https://example.org/fhir/Questionnaire/national-health', subject: { identifier: { value: 'subj-000123' } }, authored: '2026-11-10T09:30:00+09:00',
  item: [{ linkId: 'Q1.D01', item: [{ linkId: 'Q1.D01.diagnosed', answer: [{ valueBoolean: true }] }, { linkId: 'Q1.D01.on_medication', answer: [{ valueBoolean: true }] }] },
    { linkId: 'Q8_1', item: [{ linkId: 'Q8_1.days', answer: [{ valueInteger: 3 }] }] },
    { linkId: 'Q7_1', item: [{ linkId: 'Q7_1[soju].amount', extension: [{ url: 'http://hl7.org/fhir/StructureDefinition/data-absent-reason', valueCode: 'asked-declined' }] }] }], ...extra });
test('FHIR R4 공식 스키마: 우리 대응 규칙대로 만든 QuestionnaireResponse 는 받고 계약 스키마와도 맞는다', () => {
  const val = fv('QuestionnaireResponse'); assert.equal(val(qr()), true, JSON.stringify(val.errors?.slice(0, 3)));
  ok('FhirQuestionnaireResponse', qr());
});
test('FHIR R4 공식 스키마: 자료형이 틀린 답과 잘못된 코드를 거부한다', () => {
  const val = fv('QuestionnaireResponse');
  assert.equal(val(qr({ item: [{ linkId: 'Q8_1', answer: [{ valueInteger: 'a' }] }] })), false, 'valueInteger 문자열');
  assert.equal(val(qr({ status: 'finished' })), false, '없는 status 코드');
  assert.equal(val(qr({ item: [{ linkId: 'Q1', answer: [{ valueBoolean: 'yes' }] }] })), false, 'valueBoolean 문자열');
});
test('FHIR R4: 공식 JSON Schema 는 필수 칸(1..1)을 강제하지 않으므로 계약 스키마의 필수 칸이 더한다', () => {
  const val = fv('QuestionnaireResponse');
  assert.equal(val({ resourceType: 'QuestionnaireResponse' }), true, '공식 스키마는 status 없음을 받는다(한계)');
  no('FhirQuestionnaireResponse', { resourceType: 'QuestionnaireResponse' }, '계약 스키마는 status 없음을 거부한다');
  const o = fv('OperationOutcome');
  assert.equal(o({ resourceType: 'OperationOutcome', issue: [{ severity: 'error' }] }), true, '공식 스키마는 code 없음을 받는다(한계)');
  no('FhirOperationOutcome', { resourceType: 'OperationOutcome', issue: [{ severity: 'error' }] }, '계약 스키마는 code 없음을 거부한다');
});
test('FHIR R4 공식 스키마: OperationOutcome 예시를 받고 계약 스키마와도 맞다', () => {
  const val = fv('OperationOutcome'); const oo = { resourceType: 'OperationOutcome', issue: [{ severity: 'error', code: 'not-found', diagnostics: '결과가 없다' }] };
  assert.equal(val(oo), true, JSON.stringify(val.errors?.slice(0, 3))); ok('FhirOperationOutcome', oo);
  assert.equal(val({ resourceType: 'OperationOutcome', issue: [{ severity: 'bad', code: 'not-found' }] }), false, '없는 severity 코드');
  assert.equal(val({ resourceType: 'OperationOutcome' }), false, 'issue 없음');
});
