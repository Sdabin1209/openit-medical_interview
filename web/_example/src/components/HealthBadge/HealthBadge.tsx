import type { components } from "../../contract/health";

type Readyz = components["schemas"]["Readyz"];

interface Props {
  readyz: Readyz | undefined;
  isLoading: boolean;
  isError: boolean;
}

/** 서버 준비 상태를 한 줄로 보여 준다. 데이터는 props 로 받는다(서버 호출은 link 의 일). */
export function HealthBadge({ readyz, isLoading, isError }: Props) {
  if (isLoading) return <p role="status">상태 확인 중</p>;
  if (isError || readyz === undefined) return <p role="alert">상태를 읽지 못했다</p>;
  if (readyz.status === "ready") return <p role="status">준비됨</p>;
  return <p role="alert">준비 안 됨: {readyz.failed.join(", ")}</p>;
}
