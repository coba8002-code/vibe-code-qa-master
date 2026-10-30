# VIBE CODE QA MASTER

독립형 개발 품질관리 플랫폼의 안전한 MVP. 외부 GitHub에 쓰지 않고 로컬에서 실행한다.

**현재 상태: Windows Release Candidate (0.9.0-rc2).** rc4에서 실제 사용자 설치 및 비공개 GitHub 정적 검수를 확인했다. 0.9에서는 [자동 수정 및 실제 재검사](docs/AUTOFIX.md)를 추가했다. 전체 제품 출시 여부는 [Release checklist](docs/RELEASE_CHECKLIST.md)의 미완료 게이트와 구분한다.

## 시작

Python 3.11 이상:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export QA_ADMIN_TOKEN="$(openssl rand -hex 32)"
export QA_AGENT_TOKEN="$(openssl rand -hex 32)"
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

브라우저에서 http://127.0.0.1:8080 에 접속해 관리자 토큰을 입력한다. 개발 서버를 공용 인터넷에 직접 노출하지 말 것. 테스트는 `python -m pytest -q`.

## 가장 쉬운 검수 방법

1. 서버 실행 후 브라우저에서 관리자 토큰을 입력한다.
2. **GitHub 프로젝트**는 `https://github.com/소유자/저장소` 주소를 붙여넣고 **GitHub 1차 검수**를 클릭한다.
3. **PC 로컬 프로젝트**는 **폴더 선택** 후 **선택 폴더 1차 검수**를 클릭한다.
4. 의심 보안 패턴, 테스트 파일·CI·의존성 파일 유무 및 **미실행 검사**를 확인한다.

GitHub ZIP을 읽기 전용으로 가져오며 외부 저장소를 수정하지 않는다. 비공개 저장소는 `QA_GITHUB_TOKEN`에 읽기 권한만 있는 토큰을 지정한다. 로컬 폴더는 선택된 파일만 서버 메모리에서 검사한다. 1,500개 파일·파일당 1MB·총 24MB 제한이 있다. 빠른 **정적 패턴 점검**이며 테스트 실행·침투 테스트·부하 검사는 수행하지 않는다.

## GitHub 커밋 고정 검수 → AI 수정 요청서 → 패치 검토 (4차 MVP)

1. `QA_GITHUB_TOKEN`에 읽기 전용 토큰을 넣거나, 공개 저장소라면 별도 토큰 없이 시작한다.
2. **GitHub 프로젝트 관리**에서 `coba8002-code` 소유자의 `Webjux`, `Oneroom`을 각각 수동 등록한다. 자동 검색은 읽기 전용 토큰이 있을 때 가능하다.
3. 관리자가 프로젝트를 승인한다. 승인 이전에는 이력형 검수가 거부된다.
4. **GitHub 검수 이력 및 AI 수정 요청**에서 **커밋 고정 검수**를 실행한다. 최신 기본 브랜치의 SHA를 조회한 뒤 그 SHA의 ZIP만 읽어 분석하고, 결과와 버전을 로컬 SQLite에 기록한다.
5. 저장된 검사에서 발견 항목이 있다면 **Codex 요청서** 또는 **Claude 요청서**를 클릭하고 Markdown 파일로 다운로드한다.
6. 다운로드한 요청서를 선택한 AI 개발 환경의 **격리된 작업 공간**에 전달한다. 원본 브랜치 쓰기, PR 생성, 배포 권한은 별도로 승인하기 전까지 금지한다.
7. Codex·Claude에서 생성한 `git diff` 형식의 `.diff` 또는 `.patch` 파일을 **AI 수정 요청서 → 패치 등록**으로 업로드한다. 최대 300KB이며 바이너리 패치는 허용하지 않는다.
8. 검토자는 **AI 제안 패치 검토**에서 내용을 확인하고 승인·반려한다. 승인은 **수동 다운로드만 허용**하며 로컬 소스 자동 적용이나 GitHub PR 생성 권한은 아니다.
9. AI 개발 환경에서 수정을 마친 **별도의 로컬 프로젝트 폴더**를 웹 화면에서 선택한다. 저장된 기준 GitHub 검수 옆 **수정 후 재검수**를 누르면 규칙+파일 경로를 기준으로 해결 후보·잔여·신규 정적 패턴을 비교하고 로컬 DB에 저장한다. 파일 이름 변경이나 미검사 파일은 확인이 필요하며 이 결과를 기능 정상화나 보안 문제 해결의 확정 증거로 사용하지 않는다.
10. 재검수에서 잔여 또는 신규 문제가 있다면 **Codex 후속 요청** 또는 **Claude 후속 요청**을 눌러 `AI 후속 수정 요청서`를 만든다. 같은 재검수·AI 조합은 중복 생성하지 않으며, 각 AI별로 기준 검수당 최대 5차 요청서만 허용한다. 요청서는 다운로드 후 격리된 AI 개발 환경에 **수동 전달**한다. AI 프로세스를 자동 실행하거나 GitHub 소스를 수정하지 않는다.

현재 연동은 *read-only source retrieval + persistent audit + remediation draft generation*이다. AI 프로세스 자동 실행, 자동 수정, PR 생성, 브랜치 푸시, 가비아 TEST/PROD 배포는 연결하지 않았다. 공개 저장소도 GitHub API 호출 제한 또는 아카이브 크기 제한으로 검수에 실패할 수 있다. 테스트 결과는 정적 검사 증거로만 저장하고 **배포 PASS로 자동 승격시키지 않는다**.

상세 작업 지침: [docs/AI_HANDOFF.md](docs/AI_HANDOFF.md).

## Windows 설치형 프로그램 및 제한된 실행 테스트

Windows 10/11에서 Python 3.12, Inno Setup 6을 설치한 다음 PowerShell에서 `windows/build-windows.ps1`을 실행하면 `release/VibeCodeQAMaster-Setup.exe` 설치 파일을 빌드한다. 빌드된 설치 파일은 관리자 권한 없이 사용자별 설치가 가능하다. 현재 배포된 ZIP에는 **Windows에서 빌드할 소스와 설치 스크립트**가 들어 있다. 이 Linux 개발 환경에서는 Windows `.exe`를 빌드하거나 동작 검증하지 않았다.

빌드 순서: Python 의존성 설치 → 현재 자동테스트 전체 실행 → PyInstaller 실행 파일 생성 → 패키징된 UI·API 인증·임시 DB 검사(`VibeQAMaster.exe --self-check`) → Windows 실행 파일 6초 구동 테스트 → Inno Setup 설치 파일 생성 → 임시 폴더 무인 설치 → 설치된 프로그램의 `--self-check` 및 6초 구동 확인 → `SHA256SUMS.txt` 생성. 자동 스모크 테스트는 파일 포함 여부·API 기본 동작·GUI 프로세스 생존만 확인한다. 버튼 클릭, 실제 브라우저 연결, 실제 GitHub 읽기와 기능·부하 테스트를 검증한 것으로 간주하지 않는다. 설치 후 사용자가 첫 실행에서 **검수 화면 열기**를 직접 눌러 추가 확인해야 한다.

또는 소스를 본인이 승인한 GitHub 저장소에 올린 다음 Actions의 **Build Windows installer (manual)** 워크플로를 수동 실행하면 서명되지 않은 설치 파일을 artifact로 받을 수 있다. 이 패키지는 GitHub 저장소를 직접 수정하거나 워크플로를 실행하지 않는다.

1. 설치 프로그램 실행 → 바탕화면의 VIBE CODE QA MASTER 실행.
2. **검수 화면 열기** → **관리자 키 복사** → 웹 화면에서 붙여넣기.
3. 정적 검수는 주소 입력/폴더 선택만으로 가능.
4. 실제 기능 테스트를 하려면 Docker Desktop을 설치·실행하고, `docker pull python:3.12-slim` 또는 `docker pull node:22-alpine`을 **직접 승인 후** 1회 준비한다. 외부 네트워크가 필요한 패키지 다운로드를 QA MASTER가 자동 실행하지 않는다.
5. 데스크톱 창의 **실행 검사용 폴더 승인**에서 직접 테스트할 로컬 프로젝트 폴더를 선택하고 확인한다. 웹 화면에서 **대상 새로고침** → **기능·실행 테스트** 또는 **장시간 반복 테스트**를 선택한다.

실행 환경은 컨테이너 CPU 1코어, RAM 512MB, PID 64개, 네트워크 차단, 소스 읽기 전용, 5~600초 제한이다. 테스트 코드는 `python -m unittest discover -s tests -v` 또는 `node --test`로만 실행한다. 제3자 패키지가 필요한 테스트는 현재 이미지에서 실패할 수 있다. CPU·RAM은 **Docker 컨테이너에 대한 표본 최고값**이지 시스템 전체 사용량이 아니다. 반복 실행은 메모리 누수 의심 추세를 볼 보조 검사이며 누수 여부를 보증하지 않는다. 종료 전 컨테이너에 있던 프로세스는 제거되므로 지속성 검사가 아니다. 별도의 **로컬 TEST 서버 HTTP 부하 검사**는 사용자가 직접 실행한 `http://127.0.0.1:PORT` 엔드포인트에 동시 최대 4개, 총 100개의 GET 요청만 보내고 p50/p95 응답시간과 오류 수를 측정한다. 테스트 전 TEST 서버 URL을 확인해야 한다. GitHub URL만 입력해서 서버 코드를 자동 실행하거나 가비아 운영 서버를 테스트하지 않는다.

선택적으로 `QA_GITHUB_TOKEN` 환경 변수에 읽기 전용 GitHub 토큰을 지정하면 저장소 목록을 가져온다. 현재 MVP에서는 수동 등록도 지원한다.

## 구현됨

- 프로젝트 저장소 검색/등록 및 관리자 승인
- Codex / Claude Code 표준 이벤트 수집 API (중복 이벤트 차단, 메타데이터 허용목록)
- QA 범주별 증거 기록 및 미실행 항목을 포함한 JSON 리포트
- TEST/PRODUCTION 배포 *요청 및 승인 상태* 관리 (운영은 5개 범주 PASS 필요)
- 브라우저용 관리자 대시보드, SQLite 영속 저장, 기본 API 테스트

## 아직 구현되지 않음

- Codex/Claude Code PC 상주 수집기 및 중앙 작업 실행기
- 코드에 대한 실제 SAST/DAST/E2E/k6/메모리 검사 실행과 CI 연계
- 가비아 TEST/PROD 실제 배포·롤백, PostgreSQL, RBAC/SSO, MFA, 감사로그, 비밀금고

**현재 검사 결과 입력은 관리자 API를 신뢰하는 구조이다.** 실제 출시 전에 서명된 CI 증거와 커밋 출처 검증을 도입해야 한다. 이 버전은 운영 배포 판단용으로 사용하지 않는다.

상세 설계: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). 공통 스킬: [skills/vibe-code-qa-master/SKILL.md](skills/vibe-code-qa-master/SKILL.md).
