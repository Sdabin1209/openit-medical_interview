import { ApiError } from "./link/http";

/** 화면에 보일 오류 글. 서버의 Problem Details 가 있으면 그 제목과 설명을 쓴다. */
export function errorText(error: unknown): string | undefined {
  if (error === null || error === undefined) return undefined;
  if (error instanceof ApiError) return error.problem?.detail ? `${error.problem.title}: ${error.problem.detail}` : error.message;
  return error instanceof Error ? error.message : "알 수 없는 오류";
}

export function problemOf(error: unknown) {
  return error instanceof ApiError ? error.problem : undefined;
}
