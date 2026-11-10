// 가짜 survey-service·model-runtime·oauth2-proxy(메모리 구현). 응답 값은 계약 생성 타입으로 만들어 계약과 어긋나면 tsc 가 막는다.
// 같은 가짜를 Vitest(전역 fetch 대신 끼움)와 Playwright(page.route)가 쓴다(ADR 0012: 이웃 영역 없이 혼자 시험).
import type { components as Model } from "../../src/contract/model-runtime";
import type { components as Survey } from "../../src/contract/survey-service";

type S = Survey["schemas"];
type M = Model["schemas"];

export interface FakeRequest {
  method: string;
  path: string;
  query: URLSearchParams;
  headers: Headers;
  body: unknown;
}
export interface FakeResponse {
  status: number;
  contentType: string;
  body: string;
}

const UUID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const DIGEST_A = `sha256:${"a".repeat(64)}`;
const DIGEST_B = `sha256:${"b".repeat(64)}`;
export const DIGESTS = { active: DIGEST_A, candidate: DIGEST_B };
const NOW = "2026-11-10T09:00:00Z";

function json(status: number, body: unknown): FakeResponse {
  return { status, contentType: "application/json", body: JSON.stringify(body) };
}
export function problem(status: number, title: string, extra: Partial<S["ProblemDetails"]> = {}): FakeResponse {
  return {
    status,
    contentType: "application/problem+json",
    body: JSON.stringify({ type: "about:blank", title, status, ...extra } satisfies S["ProblemDetails"]),
  };
}

const fieldValues: S["ExtractedValues"] = [{ key: "Q1.answer", value: "yes", precision: "exact", status: "ANSWERED", save: true }];
const extraction: S["ActionExtraction"] = { action: "NEXT", next_item: "Q2", values: fieldValues };

const ROLE_RULES: [RegExp, string, string[]][] = [
  [/^\/v1\/questionnaires$/, "GET", ["staff"]],
  [/^\/v1\/start-codes$/, "POST", ["staff"]],
  [/^\/v1\/staff-alerts(\/stream)?$/, "GET", ["staff", "clinician"]],
  [/^\/v1\/push-(config|subscriptions)$/, "*", ["staff", "clinician"]],
  [/^\/v1\/sessions\/[^/]+\/intervention$/, "POST", ["staff"]],
  [/^\/v1\/results(\/.*)?$/, "*", ["clinician"]],
  [/^\/v1\/question-set-versions(\/.*)?$/, "*", ["author"]],
  [/^\/v1\/(cases|deidentified-traces)(\/.*)?$/, "*", ["reviewer"]],
  [/^\/v1\/model-status$/, "GET", ["operator", "release-approver"]],
  [/^\/v1\/model-packages(\/.*)?$/, "GET", ["operator", "release-approver"]],
  [/^\/v1\/model-activations$/, "POST", ["release-approver"]],
  [/^\/v1\/model-rollbacks$/, "POST", ["operator", "release-approver"]],
];

export interface FakeOptions {
  roles?: string[];
  userName?: string;
}

export function createFakeBackend(options: FakeOptions = {}) {
  const roles = options.roles ?? ["staff", "clinician", "author", "reviewer", "release-approver"];
  const calls: { method: string; path: string; body: unknown }[] = [];
  const startCodesByKey = new Map<string, S["StartCode"]>();
  let codeSeq = 482910;
  let sseSequence = 1;

  const results: S["SessionResult"][] = [
    {
      session_id: UUID(1),
      status: "ENDED_COMPLETE",
      questionnaire_id: "national-health",
      questionnaire_title: "국가건강검진 문진표",
      question_set_version_id: UUID(11),
      subject_ref: "subj-000123",
      answers: [
        { key: "Q1.answer", value: true, precision: "exact" },
        { key: "Q7_1.drink_days", value: 3, precision: "approximate" },
      ],
      blanks: [{ item_id: "Q5", reason: "REJECTED" }],
      started_at: "2026-11-10T08:00:00Z",
      ended_at: "2026-11-10T08:10:00Z",
    },
    {
      session_id: UUID(2),
      status: "ENDED_PARTIAL",
      questionnaire_id: "national-health",
      question_set_version_id: UUID(11),
      subject_ref: "subj-000124",
      answers: [],
      blanks: [],
      started_at: "2026-11-10T08:20:00Z",
    },
  ];

  const alerts: S["StaffAlert"][] = [
    { alert_id: UUID(21), kind: "CALL_STAFF", session_id: UUID(3), device_id: "kiosk-01", questionnaire_title: "국가건강검진 문진표", raised_at: "2026-11-10T08:30:00Z" },
    { alert_id: UUID(22), kind: "RESULT_READY", session_id: UUID(1), raised_at: "2026-11-10T08:10:00Z", resolved_at: "2026-11-10T08:12:00Z" },
  ];

  const questionSets: S["QuestionSetVersion"][] = [
    {
      question_set_version_id: UUID(11),
      questionnaire_id: "national-health",
      version_number: 1,
      runtime_contract_version: 1,
      content: { title: "국가건강검진 문진표", bank: { items: [], }, flow: { start_item: "Q1", rules: [] } },
      content_hash: "c".repeat(64),
      uploaded_by: "author-1",
      created_at: NOW,
      is_active: true,
    },
  ];

  const cases: S["FailureCase"][] = [
    {
      case_id: UUID(31),
      case_version: 1,
      kind: "EXTRACT_FAILED",
      review_status: "UNREVIEWED",
      questionnaire_id: "national-health",
      item_id: "Q7_1",
      utterance: "가끔 한잔 정도",
      model_output: extraction,
      created_at: NOW,
    },
  ];

  let model: M["ModelStatus"] = { state: "READY", package_digest: DIGEST_A, runtime_contract_version: 1, model_io_version: "model-io-v2", activated_by: "approver-0", activated_at: NOW, loaded_at: NOW };

  const manifest: M["ModelPackageManifest"] = {
    base_model: "Qwen/Qwen3-4B",
    runtime_contract_version: 1,
    model_io_version: "model-io-v2",
    model_runtime_version: "1.0.0",
    adapters: [
      {
        role: "LORA_A",
        weights: { mediaType: "application/vnd.openit.model.adapter.weights.v1", digest: `sha256:${"1".repeat(64)}`, size: 1024 },
        system_prompt: { mediaType: "application/vnd.openit.model.adapter.system-prompt.v1", digest: `sha256:${"2".repeat(64)}`, size: 128 },
        serving_config: { max_new_tokens: 256, temperature: 0, constrained_decoding: true },
      },
    ],
    lineage: { dataset_version_id: UUID(41), base_model: "Qwen/Qwen3-4B", training_run_ids: [UUID(42)] },
    evaluation: {
      dataset_version_id: UUID(43),
      metrics: [
        { name: "next_item_accuracy", group: "ACCURACY", value: 0.97, unit: "ratio", sample_count: 2000 },
        { name: "semantic_violation_rate", group: "SAFETY", slice: "action=REASK", value: 0.01, unit: "ratio", sample_count: 300 },
      ],
      created_at: NOW,
    },
    created_at: NOW,
  };

  function userinfo(): FakeResponse {
    return json(200, { user: "u-1", email: "user@example.org", preferredUsername: options.userName ?? "직원 김", groups: roles });
  }

  function pageOf<T>(items: T[]) {
    return { items };
  }

  function handle(req: FakeRequest): FakeResponse {
    calls.push({ method: req.method, path: req.path, body: req.body });
    if (req.path === "/oauth2/userinfo") return userinfo();
    for (const [pattern, method, allowedRoles] of ROLE_RULES) {
      if (pattern.test(req.path) && (method === "*" || method === req.method) && !allowedRoles.some((r) => roles.includes(r))) {
        return problem(403, "권한이 없다", { detail: `필요한 역할: ${allowedRoles.join(", ")}` });
      }
    }
    const body = req.body as Record<string, unknown> | undefined;
    const match = (re: RegExp) => re.exec(req.path);

    if (req.path === "/v1/questionnaires") return json(200, { questionnaires: [{ questionnaire_id: "national-health", title: "국가건강검진 문진표" }] } satisfies S["ActiveQuestionnaireList"]);
    if (req.path === "/v1/start-codes" && req.method === "POST") {
      const key = req.headers.get("Idempotency-Key") ?? "";
      const known = startCodesByKey.get(key);
      if (known) return json(201, known);
      if (typeof body?.["subject_ref"] !== "string" || !/^[A-Za-z0-9.-]{1,64}$/.test(body["subject_ref"])) {
        return problem(400, "요청이 계약과 다르다", { errors: [{ pointer: "/subject_ref", detail: "대상자 참조값 형식이 아니다" }] });
      }
      const code: S["StartCode"] = { code: String(codeSeq++), ...(typeof body["questionnaire_id"] === "string" ? { questionnaire_id: body["questionnaire_id"] } : {}), issued_at: NOW, expires_at: "2026-11-10T09:10:00Z" };
      startCodesByKey.set(key, code);
      return json(201, code);
    }
    if (req.path === "/v1/staff-alerts") return json(200, pageOf(alerts));
    if (req.path === "/v1/staff-alerts/stream") {
      const event: S["StaffAlert"] = { alert_id: UUID(23), kind: "RISK", session_id: UUID(4), device_id: "kiosk-02", raised_at: "2026-11-10T08:40:00Z" };
      const data = JSON.stringify({ event: "alert", sequence: sseSequence, alert: event });
      const text = `retry: 600000\nid: ${String(sseSequence++)}\nevent: alert\ndata: ${data}\n\n`;
      return { status: 200, contentType: "text/event-stream", body: text };
    }
    const intervention = match(/^\/v1\/sessions\/([^/]+)\/intervention$/);
    if (intervention) {
      const action = body?.["action"];
      return json(200, { session_id: intervention[1] ?? "", status: action === "RESUME" ? "ACTIVE" : "PAUSED" } satisfies S["SessionState"]);
    }
    if (req.path === "/v1/push-config") return json(200, { vapid_public_key: "B".repeat(87) } satisfies S["PushConfig"]);
    if (req.path === "/v1/push-subscriptions") return json(201, { push_subscription_id: UUID(51), registered_at: NOW } satisfies S["PushSubscriptionRegistered"]);

    if (req.path === "/v1/results") {
      const status = req.query.get("status");
      return json(200, pageOf(results.filter((r) => status === null || r.status === status)));
    }
    const ack = match(/^\/v1\/results\/([^/]+)\/acknowledgements$/);
    if (ack) {
      const result = results.find((r) => r.session_id === ack[1]);
      if (!result) return problem(404, "없다");
      result.acknowledged_by ??= "doctor-1";
      result.acknowledged_at ??= NOW;
      return json(200, { session_id: result.session_id, acknowledged_by: result.acknowledged_by, acknowledged_at: result.acknowledged_at } satisfies S["ResultAcknowledgement"]);
    }
    const result = match(/^\/v1\/results\/([^/]+)$/);
    if (result) {
      const found = results.find((r) => r.session_id === result[1]);
      return found ? json(200, found) : problem(404, "없다");
    }

    if (req.path === "/v1/question-set-versions" && req.method === "GET") return json(200, pageOf(questionSets));
    if (req.path === "/v1/question-set-versions" && req.method === "POST") {
      if (typeof body?.["questionnaire_id"] !== "string") return problem(400, "요청이 계약과 다르다", { errors: [{ pointer: "/questionnaire_id", detail: "필요하다" }] });
      const upload = body as unknown as S["QuestionSetUpload"];
      const version: S["QuestionSetVersion"] = { question_set_version_id: UUID(12 + questionSets.length), questionnaire_id: upload.questionnaire_id, version_number: questionSets.length + 1, runtime_contract_version: upload.runtime_contract_version, content: upload.content, content_hash: "d".repeat(64), uploaded_by: "author-1", created_at: NOW, is_active: false };
      questionSets.unshift(version);
      return json(201, version);
    }
    const activation = match(/^\/v1\/question-set-versions\/([^/]+)\/activation$/);
    if (activation) {
      const v = questionSets.find((q) => q.question_set_version_id === activation[1]);
      if (v) for (const q of questionSets) if (q.questionnaire_id === v.questionnaire_id) q.is_active = q === v;
      return v ? json(200, { questionnaire_id: v.questionnaire_id, question_set_version_id: v.question_set_version_id, runtime_contract_version: v.runtime_contract_version, activated_by: "author-1", activated_at: NOW } satisfies S["ActiveQuestionSet"]) : problem(404, "없다");
    }

    if (req.path === "/v1/cases") {
      const status = req.query.get("review_status");
      return json(200, pageOf(cases.filter((c) => status === null || c.review_status === status)));
    }
    const review = match(/^\/v1\/cases\/([^/]+)\/reviews$/);
    if (review) {
      const c = cases.find((x) => x.case_id === review[1]);
      if (!c) return problem(404, "없다");
      const input = body as unknown as S["CaseReview"];
      if (input.base_case_version !== c.case_version) return problem(409, "다른 검토가 먼저 게시됐다", { reason: "CASE_VERSION_MISMATCH" });
      c.case_version += 1;
      c.review_status = input.review_status;
      if (input.expected) c.expected = input.expected;
      if (input.reviewed_input !== undefined) c.reviewed_input = input.reviewed_input;
      c.reviewed_by = "reviewer-1";
      c.reviewed_at = NOW;
      return json(201, c);
    }
    const trace = match(/^\/v1\/deidentified-traces\/([^/]+)$/);
    if (trace) return json(200, { case_id: trace[1] ?? "", utterance: "가끔 한잔 정도", extract_output: extraction, occurred_at: NOW } satisfies S["DeidentifiedTrace"]);
    const one = match(/^\/v1\/cases\/([^/]+)$/);
    if (one) {
      const c = cases.find((x) => x.case_id === one[1]);
      return c ? json(200, c) : problem(404, "없다");
    }

    if (req.path === "/v1/model-status") return json(200, model);
    if (req.path === "/v1/model-packages") {
      // 활성 여부는 지금 적재 상태의 패키지다(계약 ModelPackageSummary.is_active). 쪽 나누기는 limit 1 이면 첫 쪽만 주고 next_cursor 를 준다
      const all: M["ModelPackageSummary"][] = [DIGEST_B, DIGEST_A].map((d) => ({ package_digest: d, published_at: NOW, is_active: d === model.package_digest }));
      const cursor = req.query.get("cursor");
      const size = Number(req.query.get("limit") ?? all.length);
      const start = cursor === null ? 0 : Number(cursor);
      const items = all.slice(start, start + size);
      return json(200, { items, ...(start + size < all.length ? { next_cursor: String(start + size) } : {}) } satisfies M["ModelPackageList"]);
    }
    const pkg = match(/^\/v1\/model-packages\/(.+)$/);
    if (pkg) return pkg[1] === DIGEST_B ? json(200, manifest) : problem(404, "패키지가 없다");
    if (req.path === "/v1/model-activations") {
      const input = body as unknown as M["ActivationRequest"];
      if (input.package_digest === model.package_digest) return json(200, model);
      model = { state: "LOADING", package_digest: input.package_digest, previous_package_digest: model.package_digest ?? "", runtime_contract_version: 1, model_io_version: "model-io-v2", activated_by: "approver-1", activated_at: NOW };
      // 다음 읽기에서 적재가 끝난다
      setTimeout(() => {
        model = { ...model, state: "READY", loaded_at: NOW };
      }, 50);
      return json(202, model);
    }
    if (req.path === "/v1/model-rollbacks") {
      const input = body as unknown as M["RollbackCommand"];
      if (input.target_package_digest !== model.previous_package_digest) return problem(409, "되돌아갈 수 없다", { reason: "ROLLBACK_TARGET_INVALID" });
      model = { state: "LOADING", package_digest: input.target_package_digest, previous_package_digest: model.package_digest ?? "", runtime_contract_version: 1, model_io_version: "model-io-v2", activated_by: "approver-1", activated_at: NOW };
      setTimeout(() => {
        model = { ...model, state: "READY", loaded_at: NOW };
      }, 50);
      return json(202, model);
    }
    return problem(404, "가짜 서버에 없는 경로", { detail: req.path });
  }

  return { handle, calls, manifest };
}

export type FakeBackend = ReturnType<typeof createFakeBackend>;

/** 전역 fetch 자리에 끼우는 함수(Vitest). */
export function fakeFetch(backend: FakeBackend) {
  return async (input: Request | string | URL, init?: RequestInit): Promise<Response> => {
    // 상대 경로는 브라우저처럼 지금 출처를 기준으로 푼다(Node 의 Request 는 상대 경로를 받지 않는다)
    const request = input instanceof Request ? input : new Request(new URL(input, globalThis.location.origin), init);
    const url = new URL(request.url);
    const text = request.method === "GET" || request.method === "HEAD" ? "" : await request.text();
    const response = backend.handle({ method: request.method, path: decodeURIComponent(url.pathname), query: url.searchParams, headers: request.headers, body: text === "" ? undefined : (JSON.parse(text) as unknown) });
    return new Response(response.body, { status: response.status, headers: { "content-type": response.contentType } });
  };
}
