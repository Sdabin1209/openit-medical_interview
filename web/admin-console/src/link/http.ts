// 영역 밖(서버) 통신의 바탕. survey-service 와 model-runtime 의 작업을 계약 타입(openapi-typescript)으로 부른다.
// 왜 openapi-fetch: openapi-typescript 와 같은 팀의 표준 짝(MIT)이다. 경로·본문·응답 타입이 계약에서 나와 손으로 옮기지 않는다(ADR 0020).
// 왜 상대 경로(같은 출처): 브라우저는 영역 게이트웨이 뒤의 한 출처만 알고, 토큰은 oauth2-proxy 가 요청에 싣는다(ADR 0002).
import createClient, { type Middleware } from "openapi-fetch";

import type { paths as ModelPaths } from "../contract/model-runtime";
import type { components, paths as SurveyPaths } from "../contract/survey-service";
import { redirectToSignIn } from "./session";

export type ProblemDetails = components["schemas"]["ProblemDetails"];

/** 서버가 RFC 9457 Problem Details 로 낸 오류(계약의 모든 오류 응답 형식). */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: ProblemDetails | undefined,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isProblem(value: unknown): value is ProblemDetails {
  return typeof value === "object" && value !== null && "status" in value && "title" in value;
}

// 왜 401 에서 로그인으로 보낸다: 세션 쿠키가 끝나면 oauth2-proxy 는 401 을 낸다. 다시 로그인하는 것이 표준 흐름이다.
const unauthorized: Middleware = {
  onResponse({ response }) {
    if (response.status === 401) redirectToSignIn();
    return undefined;
  },
};

// 왜 fetch 를 감싼다: 시험이 전역 fetch 를 바꿔 끼울 수 있어야 한다. 기본값은 만들 때 한 번 잡힌다.
function makeClient<P extends object>() {
  const client = createClient<P>({ baseUrl: globalThis.location.origin, fetch: (request) => globalThis.fetch(request) });
  client.use(unauthorized);
  return client;
}

export const survey = makeClient<SurveyPaths>();
export const model = makeClient<ModelPaths>();

type Result<D, E> = { data: D; error?: never; response: Response } | { data?: never; error: E; response: Response };

/** 성공이면 본문을, 아니면 ApiError 를 던진다. */
export function unwrap<D, E>(result: Result<D, E>): D {
  if (result.error === undefined) return result.data as D;
  const problem = isProblem(result.error) ? result.error : undefined;
  throw new ApiError(result.response.status, problem, problem?.title ?? `응답 코드 ${String(result.response.status)}`);
}

/** 같은 요청을 다시 보낼 때 같은 값을 보내는 키(계약 IdempotencyKey, UUID). */
export function newIdempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}
