// 영역 밖(서버) 통신은 이 폴더에서만 한다(ADR 0003). 같은 출처(게이트웨이 뒤)의 상대 경로를 쓴다.
import { useQuery } from "@tanstack/react-query";

import type { components } from "../contract/health";

export type Readyz = components["schemas"]["Readyz"];

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

function isReadyz(value: unknown): value is Readyz {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    (record["status"] === "ready" || record["status"] === "not_ready") &&
    Array.isArray(record["failed"]) &&
    record["failed"].every((item) => typeof item === "string")
  );
}

/** /readyz 를 읽는다. 503 도 계약이 정한 응답(not_ready)이므로 본문을 돌려준다. */
export async function fetchReadyz(signal?: AbortSignal): Promise<Readyz> {
  const response = await fetch("/readyz", signal ? { signal } : {});
  if (response.status !== 200 && response.status !== 503) {
    throw new HttpError(response.status, `/readyz 응답 코드 ${String(response.status)}`);
  }
  const body: unknown = await response.json();
  if (!isReadyz(body)) throw new HttpError(response.status, "/readyz 응답이 계약과 다르다");
  return body;
}

export function useReadyz() {
  // 왜 refetchInterval: 상태 표시는 사람이 새로고침하지 않아도 갱신되어야 한다. 값은 측정 없이 정한 임시 값이 아니라
  // react-query 의 기본 동작(창이 다시 보일 때 갱신)에 맡기고 주기 갱신은 두지 않는다.
  return useQuery({ queryKey: ["readyz"], queryFn: ({ signal }) => fetchReadyz(signal) });
}
