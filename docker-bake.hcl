# Docker Buildx Bake(ADR 0004). 서비스·잡·화면 이미지를 모두 여기서 정의한다.
# 목록은 tools/new-area 가 고치고, tools/checks 가 services/·web/ 폴더와 같은지 점검한다.
# 왜 목록인가: HCL 에는 폴더 glob 이 없다. 폴더와 어긋나면 점검이 잡는다.

// BEGIN SERVICES
variable "SERVICES" {
  default = ["_example", "model-runtime", "survey-service"]
}
// END SERVICES

// BEGIN JOB_AREAS
variable "JOB_AREAS" {
  default = ["_example-job"]
}
// END JOB_AREAS

// BEGIN WEBS
variable "WEBS" {
  default = ["_example", "admin-console", "kiosk-frontend"]
}
// END WEBS

# 기반 이미지 digest 는 각 Dockerfile 의 ARG 기본값이다(ADR 0006). 여기서 덮어쓰지 않는다.

# 아래 넷은 `deploy/deploy build` 가 git 에서 읽어 환경 변수로 넣는다. 비어 있으면 빌드를 막는다.
variable "REVISION" {
  default = ""
  validation {
    condition     = REVISION != ""
    error_message = "REVISION 이 비었다. deploy/deploy build 로 빌드한다."
  }
}
variable "CONTRACTS_VERSION" {
  default = ""
  validation {
    condition     = CONTRACTS_VERSION != ""
    error_message = "CONTRACTS_VERSION 이 비었다. deploy/deploy build 로 빌드한다."
  }
}
variable "SOURCE_URL" {
  default = ""
  validation {
    condition     = SOURCE_URL != ""
    error_message = "SOURCE_URL 이 비었다. deploy/deploy build 로 빌드한다."
  }
}
variable "VERSION" {
  default = ""
  validation {
    condition     = VERSION != ""
    error_message = "VERSION 이 비었다. deploy/deploy build 로 빌드한다."
  }
}

# 영역 이름 -> JobsDeclaration. deploy/deploy build 가 jobs/<영역>/jobs.json 에서 만든다
variable "JOB_DECLARATIONS" {
  default = "{}"
}

group "default" {
  targets = concat(SERVICES, JOB_AREAS, WEBS)
}

target "service" {
  matrix = { area = SERVICES }
  name       = area
  context    = "services/${area}"
  dockerfile = "Dockerfile"
  # 왜: libs/ 의 공유 라이브러리를 경로 의존으로 쓰는 영역이 이미지에 넣는다. 컨텍스트는 영역 폴더 그대로다(ADR 0006, 0020)
  contexts = { libs = "libs" }
  # 왜 trimprefix: 이미지 이름은 밑줄로 시작할 수 없다(_example 은 템플릿 시험 영역)
  tags = ["openit/${trimprefix(area, "_")}:local"]
  args = {
    REVISION          = REVISION
    VERSION           = VERSION
    CONTRACTS_VERSION = CONTRACTS_VERSION
    SOURCE_URL        = SOURCE_URL
    SERVICE           = trimprefix(area, "_")
  }
}

target "job" {
  matrix = { area = JOB_AREAS }
  name       = area
  context    = "jobs/${area}"
  dockerfile = "Dockerfile"
  contexts   = { libs = "libs" }
  tags       = ["openit/${trimprefix(area, "_")}:local"]
  args = {
    REVISION          = REVISION
    VERSION           = VERSION
    CONTRACTS_VERSION = CONTRACTS_VERSION
    SOURCE_URL        = SOURCE_URL
    SERVICE           = trimprefix(area, "_")
    # 왜: io.openit.jobs 라벨(JobsDeclaration)의 원본은 영역의 jobs.json 하나다. HCL 에는 파일 읽기 함수가 없어
    # deploy/deploy build 가 모든 jobs/<영역>/jobs.json 을 한 줄 JSON 으로 모아 JOB_DECLARATIONS 로 넣는다
    JOBS = jsonencode(jsondecode(JOB_DECLARATIONS)[area])
  }
}

target "web" {
  matrix = { area = WEBS }
  name       = "web-${trimprefix(area, "_")}"
  context    = "web/${area}"
  dockerfile = "Dockerfile"
  tags       = ["openit/web-${trimprefix(area, "_")}:local"]
  args = {
    REVISION          = REVISION
    VERSION           = VERSION
    CONTRACTS_VERSION = CONTRACTS_VERSION
    SOURCE_URL        = SOURCE_URL
    SERVICE           = "web-${trimprefix(area, "_")}"
  }
}
