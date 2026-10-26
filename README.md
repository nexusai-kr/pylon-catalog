# pylon-catalog

**Pylon Grid** 에 설치할 수 있는 **MCP 서버**와 **플러그인** 목록입니다. 파일(`.mcpb`·`.zip`)은 각 저장소의 GitHub Release 에 있고, 이 저장소의 [`catalog.json`](catalog.json) 이 "무엇이 있고 어디서 받는지"를 알려 줍니다.

The list of **MCP servers** and **plugins** installable on **Pylon Grid**. Each item ships as a `.mcpb` (server) or `.zip` (plugin) bundle attached to a GitHub Release in its own repository; [`catalog.json`](catalog.json) tells Grid what exists, where to download it, and its SHA-256.

## 목록
`catalog.json` 의 `servers`(MCP 서버)와 `plugins`(플러그인)를 보세요. **지금은 두 목록이 모두 비어 있습니다** — 이전에 있던 항목은 비공개 카탈로그로 옮겼습니다. Grid 의 `pylon-grid-mcp` 는 `servers` 를, `pylon-grid-plugin` 은 `plugins` 를 읽고 나머지는 무시합니다.

## 사용하는 쪽 (Grid 관리자)
1. Grid 관리 화면 → **카탈로그** 에서 목록을 보고 **설치**를 누른다. 설치 직후에는 아무도 쓰지 못한다 — **권한**에서 사용자·그룹을 허용한다.
   - 플러그인은 설치하면 **승인 대기**로 들어간다. 구성물을 확인하고 승인해야 Station 에 나간다. `contains` 에 `hooks`·`tools` 가 있으면 기본 **비허용**이며, 허용 여부를 따로 정한다.
2. 카탈로그 기능이 없는 Grid 는 항목의 `download` 파일과 `sha256` 으로 직접 설치한다:
   ```bash
   curl -LO <download>
   echo "<sha256>  <파일명>" | sha256sum -c      # 반드시 확인
   ```
   → 서버: **MCP 서버 → 서버 추가 → mcpb 번들 업로드**, 플러그인: **플러그인 → 업로드**.
3. 서버 `requires.connection`(예: `google`)이 있으면 서버 상세의 **사용자별 외부 위임**에 provider 와 scope 를 넣는다. 사용자는 처음 쓸 때 동의(연결)를 한 번 한다. 플러그인 `requires.mcp` 에 적힌 서버는 먼저 등록돼 있어야 한다.

## catalog.json 형식 (schema_version 2)
공통 필드:

| 필드 | 설명 |
|---|---|
| `name` | Grid 이름(URL 경로·권한 키). mcpb `manifest.json` / 플러그인 `plugin.json` 의 `name` 과 같다 |
| `version` | 버전. `download` 파일명(`<name>-<버전>.mcpb\|zip`)에 들어 있어야 한다 |
| `repository` | 저장소 |
| `download` | 저장소 **Release** 의 파일 주소 (GitHub Release 만 허용) |
| `sha256` | 파일의 SHA-256. Grid 는 받은 뒤 반드시 대조한다 |

서버(`servers[]`) 전용: `platforms`(대상 환경), `requires`(`connection`·`scopes`: 사용자가 먼저 연결해야 하는 외부 서비스), `tools`(표시용).

플러그인(`plugins[]`) 전용:

| 필드 | 설명 |
|---|---|
| `components` | 묶음 안 스킬·에이전트 이름(표시용). 설치할 때 Grid 가 묶음을 다시 분석한다 |
| `contains` | 훅·tools·bin·mcpb 유무(표시용). **훅·tools 가 있으면 반드시 `true`** — CI 가 묶음과 대조한다 |
| `requires` | 먼저 있어야 하는 `mcp`(Grid MCP 서버 이름), `plugins` |

전체 규칙은 [`catalog.schema.json`](catalog.schema.json).

## 올리려면
1. 각 저장소에서 `vX.Y.Z` 태그를 push 하면 GitHub Actions 가 파일(`<name>-<버전>.mcpb` 또는 `.zip`)과 `.sha256` 을 Release 에 올린다. 플러그인 저장소는 `.claude-plugin/plugin.json` 이 있어야 한다.
2. 이 저장소에서 항목을 만든다 (gh CLI 필요). 서버인지 플러그인인지는 Release 파일로 알아낸다:
   ```bash
   uv sync
   uv run python scripts/update_catalog.py nexusai-kr/<서버 저장소> v0.1.0
   uv run python scripts/update_catalog.py nexusai-kr/pylon-plugin-news v1.0.0
   ```
3. 바뀐 `catalog.json` 을 **Pull Request** 로 올린다. CI 가 스키마·신뢰 소유자·URL 을 검사하고, 파일을 내려받아 sha256·이름·버전·구성물까지 확인한다.

## 안전
- 다운로드는 **신뢰하는 GitHub 소유자**(`scripts/catalog_lib.py` 의 `TRUSTED_OWNERS`)의 Release 만 허용한다.
- `main` 브랜치는 리뷰 없이 바꾸지 않는다. 항목의 sha256 이 바뀌면 설치되는 파일이 바뀌므로 변경마다 검토한다.
- 매주 CI 가 올라간 파일이 sha256 과 같은지 다시 확인한다.
- 플러그인의 훅·tools 는 Grid 에서 기본 비허용이다. 항목에 표시하지 않으면 CI 가 막는다.
- 비공개·계약용 항목은 이 카탈로그에 올리지 않는다 (별도로 파일을 전달).

## 라이선스
Apache License 2.0 — [LICENSE](LICENSE), [NOTICE](NOTICE).

## 커넥터 (connectors/)

외부 서비스(GitHub·Slack 등)에 사용자 계정으로 연결하는 **OAuth 커넥터**는 `catalog.json` 의 `connectors[]` 와 `connectors/<이름>/<이름>-<버전>.json` 파일로 올립니다. 옛 Grid 는 `connectors[]` 를 무시하므로 `schema_version` 은 2 그대로입니다.

- 파일 형식은 [`connector.schema.json`](connector.schema.json) 입니다. 한 파일에 Gate **provider 정의**(OAuth 주소·scope·토큰 경로, Client ID·Secret 제외), Grid **서버**(URL·위임·선택적 도구 스냅샷), 설치 화면이 받을 **입력 항목**(`client_id`, `client_secret`), 앱 만드는 **안내**(`provider.setup`)가 들어 있습니다.
- 앱을 직접 만들어야 하는 커넥터(Slack·GitHub·구글)는 `provider` 에 OAuth 주소를 적고 `fields` 로 Client ID·Secret 을 받습니다. **MCP 표준 OAuth 를 지원하는 서버(Notion·Atlassian·Linear 등)** 는 `provider.discovery: "mcp"` 와 `provider.resource`(MCP 서버 주소)만 적습니다. Gate 가 서버에서 인증 서버를 찾아 스스로 등록하므로 `fields` 는 비어 있고 관리자가 입력할 값이 없습니다 (예: `connectors/notion`).
- 관리자가 Pylon 관리 화면에서 설치합니다. 설치는 선택이며, 서버 접속·nginx·재시작 같은 시스템 설정이 필요 없습니다. 콜백 주소는 규칙(`<공개 주소>/<Gate 경로>/v1/connections/<이름>/callback`)으로 정해지므로 커넥터를 늘려도 그대로입니다.
- **Client Secret 은 정의의 `token_url` 로 전송됩니다.** 그래서 Gate 가 설치할 때 https·공개 호스트·알려진 필드만 받도록 다시 검증하고, 이 저장소의 CI 는 sha256·스키마·이름/버전 일치·정의에 Client ID/Secret 이 없는지 확인합니다.
- 새 커넥터를 올릴 때: 파일을 추가하고, `catalog.json` 의 `connectors[]` 에 항목(`path`, `sha256`)을 넣고, `uv run python scripts/validate.py` 로 확인합니다.
