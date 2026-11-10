import type { components } from "../../contract/platform";

type HealthReport = components["schemas"]["HealthReport"];
type ProblemDetails = components["schemas"]["ProblemDetails"];

interface Props {
  readyz: HealthReport | ProblemDetails | undefined;
  isLoading: boolean;
  isError: boolean;
}

/** 서버 준비 상태를 한 줄로 보여 준다. 데이터는 props 로 받는다(서버 호출은 link 의 일). */
export function HealthBadge({ readyz, isLoading, isError }: Props) {
  if (isLoading) return <p role="status">상태 확인 중</p>;
  if (isError || readyz === undefined) return <p role="alert">상태를 읽지 못했다</p>;
  // 왜 status 의 종류로 가른다: HealthReport.status 는 글자(pass·warn·fail), ProblemDetails.status 는 HTTP 상태 코드(숫자)다
  if (typeof readyz.status === "number") return <p role="alert">{readyz.detail ?? readyz.title}</p>;
  if (readyz.status === "pass") return <p role="status">준비됨</p>;
  return <p role="alert">준비 안 됨: {readyz.status}</p>;
}
