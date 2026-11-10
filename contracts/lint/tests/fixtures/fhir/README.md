# HL7 FHIR R4 JSON Schema (시험용 사본)

- 파일: `fhir.schema.json.gz` (gzip 으로 압축한 `fhir.schema.json`, 내용은 바꾸지 않았다)
- 출처: https://hl7.org/fhir/R4/fhir.schema.json.zip (HL7 FHIR R4 4.0.1 공식 JSON Schema, JSON Schema draft-06)
- 원본 `fhir.schema.json` 의 SHA-256: `2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01`
- 라이선스: FHIR 사양은 CC0 1.0(Creative Commons No Rights Reserved)이다(https://hl7.org/fhir/R4/license.html). 허용형이다.
- 쓰임: `../../contract.test.mjs` 가 `QuestionnaireResponse` 와 `OperationOutcome` 예시와 부정 사례를 표준 스키마로 검증한다. 계약의 `FhirQuestionnaireResponse`, `FhirOperationOutcome` 은 필수 칸만 정의하고 전체 검증은 이 스키마와 FHIR 검증기가 맡는다.
