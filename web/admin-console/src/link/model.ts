// link_model: model-runtime 호출(N07). 적재 상태, 모델 패키지(평가 보고서) 읽기, 활성화 승인, 롤백.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "../contract/model-runtime";
import { model, unwrap } from "./http";

type Schemas = components["schemas"];
export type ModelStatus = Schemas["ModelStatus"];
export type ModelPackageManifest = Schemas["ModelPackageManifest"];
export type EvaluationReport = Schemas["EvaluationReport"];

// 왜 3000ms: 적재가 끝났는지 getModelStatus 로 본다(계약). 적재 시간은 측정하지 않았다. 사람이 화면을 보며 기다리는 시간 단위(초)로 정한 값이고 ADR 0004 에 적었다.
const STATUS_POLL_MS = 3000;

export function useModelStatus() {
  return useQuery({
    queryKey: ["model-status"],
    queryFn: async ({ signal }) => unwrap(await model.GET("/v1/model-status", { signal })),
    // 적재 중(LOADING)에만 다시 읽는다. 끝나면(READY, FAILED) 멈춘다.
    refetchInterval: (query) => (query.state.data?.state === "LOADING" ? STATUS_POLL_MS : false),
  });
}

/** 승인자가 활성화하기 전에 패키지의 목록표와 평가 보고서를 읽는다. 패키지를 적재하거나 활성화하지 않는다(계약). */
export function useModelPackage(digest: string | undefined) {
  return useQuery({
    queryKey: ["model-package", digest],
    enabled: digest !== undefined,
    retry: false,
    queryFn: async ({ signal }) => {
      if (digest === undefined) throw new Error("digest 가 없다");
      return unwrap(await model.GET("/v1/model-packages/{package_digest}", { params: { path: { package_digest: digest } }, signal }));
    },
  });
}

export function useActivateModelPackage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { packageDigest: string; reason: string }) =>
      unwrap(await model.POST("/v1/model-activations", { body: { package_digest: input.packageDigest, reason: input.reason } })),
    onSuccess: (status) => {
      queryClient.setQueryData(["model-status"], status);
      return queryClient.invalidateQueries({ queryKey: ["model-status"] });
    },
  });
}

export function useRollbackModelPackage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { targetPackageDigest: string; reason: string }) =>
      unwrap(await model.POST("/v1/model-rollbacks", { body: { target_package_digest: input.targetPackageDigest, reason: input.reason } })),
    onSuccess: (status) => {
      queryClient.setQueryData(["model-status"], status);
      return queryClient.invalidateQueries({ queryKey: ["model-status"] });
    },
  });
}
