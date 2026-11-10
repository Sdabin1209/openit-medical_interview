import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";

import type { components } from "../../contract/survey-service";

type QuestionSetVersion = components["schemas"]["QuestionSetVersion"];
type QuestionSetUpload = components["schemas"]["QuestionSetUpload"];
type ActiveQuestionSet = components["schemas"]["ActiveQuestionSet"];
type ProblemDetails = components["schemas"]["ProblemDetails"];

interface Props {
  versions: QuestionSetVersion[];
  loading: boolean;
  listError: string | undefined;
  hasMore: boolean;
  uploading: boolean;
  uploadProblem: ProblemDetails | undefined;
  uploaded: QuestionSetVersion | undefined;
  activating: boolean;
  activated: ActiveQuestionSet | undefined;
  activateError: string | undefined;
  onUpload: (upload: QuestionSetUpload) => void;
  onActivate: (versionId: string) => void;
  onLoadMore: () => void;
}

/** 문항 세트 올리기(JSON 파일)와 버전 목록, 활성화. 내용 검증은 서버가 한다(받아들이는 조건은 계약에 있다). */
export function QuestionSetView(props: Props) {
  const [fileError, setFileError] = useState<string>();
  const [target, setTarget] = useState<QuestionSetVersion | null>(null);

  async function onFile(file: File | undefined) {
    setFileError(undefined);
    if (file === undefined) return;
    try {
      // 형식 검사가 아니라 JSON 글자인지만 본다. 구조 검사는 서버가 한다
      props.onUpload(JSON.parse(await file.text()) as QuestionSetUpload);
    } catch {
      setFileError("JSON 파일을 읽지 못했다");
    }
  }

  return (
    <section aria-labelledby="qs-title">
      <h1 id="qs-title">문항 세트</h1>
      <h2>올리기</h2>
      <label htmlFor="qs-file">문항 세트 파일(JSON)</label>
      <input id="qs-file" type="file" accept="application/json,.json" disabled={props.uploading} onChange={(event) => void onFile(event.target.files?.[0])} />
      {fileError ? <p role="alert">{fileError}</p> : null}
      {props.uploadProblem ? (
        <div role="alert">
          <p>{props.uploadProblem.title}</p>
          {props.uploadProblem.detail ? <p>{props.uploadProblem.detail}</p> : null}
          {props.uploadProblem.errors?.map((e) => (
            <p key={e.pointer}>
              {e.pointer}: {e.detail}
            </p>
          ))}
        </div>
      ) : null}
      {props.uploaded ? (
        <p role="status">
          {props.uploaded.content.title} 버전 {props.uploaded.version_number} 을(를) 저장했다(아직 활성이 아니다)
        </p>
      ) : null}
      <h2>버전</h2>
      {props.listError ? <p role="alert">{props.listError}</p> : null}
      {props.activateError ? <p role="alert">{props.activateError}</p> : null}
      {props.activated ? (
        <p role="status">
          {props.activated.questionnaire_id} 의 활성 버전을 {props.activated.question_set_version_id} 로 바꿨다
        </p>
      ) : null}
      {props.loading ? <p>불러오는 중</p> : null}
      {!props.loading && props.versions.length === 0 ? <p>올린 문항 세트가 없다</p> : null}
      <table>
        <thead>
          <tr>
            <th scope="col">문진표</th>
            <th scope="col">버전</th>
            <th scope="col">제목</th>
            <th scope="col">문항 수</th>
            <th scope="col">올린 사람</th>
            <th scope="col">올린 때</th>
            <th scope="col">활성 여부</th>
            <th scope="col">활성화</th>
          </tr>
        </thead>
        <tbody>
          {props.versions.map((v) => (
            <tr key={v.question_set_version_id}>
              <td>{v.questionnaire_id}</td>
              <td>{v.version_number}</td>
              <td>{v.content.title}</td>
              <td>{v.content.bank.items.length}</td>
              <td>{v.uploaded_by}</td>
              <td>{new Date(v.created_at).toLocaleString("ko-KR")}</td>
              <td>{v.is_active ? "활성" : "비활성"}</td>
              <td>
                {/* 이미 활성인 버전은 막는다(계약은 멱등이라 해는 없지만 같은 일을 다시 시키지 않는다) */}
                <button type="button" disabled={props.activating || v.is_active} onClick={() => { setTarget(v); }}>
                  {`${v.questionnaire_id} 버전 ${String(v.version_number)} 활성화`}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {props.hasMore ? (
        <button type="button" onClick={props.onLoadMore}>
          더 보기
        </button>
      ) : null}
      <Dialog.Root open={target !== null} onOpenChange={(next) => { if (!next) setTarget(null); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog">
            <Dialog.Title>문항 세트 활성화</Dialog.Title>
            <Dialog.Description>
              {target ? `${target.questionnaire_id} 버전 ${String(target.version_number)} 을(를) 활성으로 만든다. 새 세션부터 이 버전을 쓰고, 진행 중인 세션은 시작할 때의 버전을 그대로 쓴다.` : ""}
            </Dialog.Description>
            <button
              type="button"
              onClick={() => {
                if (target) props.onActivate(target.question_set_version_id);
                setTarget(null);
              }}
            >
              활성화
            </button>
            <Dialog.Close asChild>
              <button type="button">취소</button>
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
