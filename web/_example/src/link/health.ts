// 영역 밖(서버) 통신은 이 폴더에서만 한다(ADR 0003). 같은 출처(게이트웨이 뒤)의 상대 경로를 쓴다.
import { useQuery } from "@tanstack/react-query";

import type { components } from "../contract/platform";

export type HealthReport = components["schemas"]["HealthReport"];
export type ProblemDetails = components["schemas"]["ProblemDetails"];
/** /readyz 의 응답: 200 은 HealthReport, 503 은 ProblemDetails(계약 platform.yaml). */
export type Readyz = HealthReport | ProblemDetails;

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isHealthReport(value: unknown): value is HealthReport {
  return (
    isRecord(value) &&
    (value["status"] === "pass" || value["status"] === "warn" || value["status"] === "fail") &&
    typeof value["service"] === "string"
  );
}

function isProblemDetails(value: unknown): value is ProblemDetails {
  return isRecord(value) && typeof value["status"] === "number" && typeof value["title"] === "string";
}

/** /readyz 를 읽는다. 503 도 계약이 정한 응답(ProblemDetails)이므로 본문을 돌려준다. */
export async function fetchReadyz(signal?: AbortSignal): Promise<Readyz> {
  const response = await fetch("/readyz", signal ? { signal } : {});
  if (response.status !== 200 && response.status !== 503) {
    throw new HttpError(response.status, `/readyz 응답 코드 ${String(response.status)}`);
  }
  const body: unknown = await response.json();
  const ok = response.status === 200 ? isHealthReport(body) : isProblemDetails(body);
  if (!ok) throw new HttpError(response.status, "/readyz 응답이 계약과 다르다");
  return body as Readyz;
}

export function useReadyz() {
  // 왜 refetchInterval: 상태 표시는 사람이 새로고침하지 않아도 갱신되어야 한다. 값은 측정 없이 정한 임시 값이 아니라
  // react-query 의 기본 동작(창이 다시 보일 때 갱신)에 맡기고 주기 갱신은 두지 않는다.
  return useQuery({ queryKey: ["readyz"], queryFn: ({ signal }) => fetchReadyz(signal) });
}
