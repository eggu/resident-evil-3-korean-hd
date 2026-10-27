# BIOHAZARD 3 Korean HD

Classic REbirth로 실행하는 **SourceNext 일본어판 BIOHAZARD 3 PC**에서 한글로 플레이할 수 있게 해 주는 모드입니다.

- 대사, 아이템, 파일 목록, 문서, 상태 화면, REbirth 메뉴(키 설정, 저장, 불러오기)가 한글로 나옵니다.
- HD 텍스처는 다음 글꼴로 그립니다.
  - 글자: Noto Sans KR
  - 상태 화면 라벨: Noto Sans KR Bold
  - 문서: Noto Serif KR SemiBold

## v1.0.2 변경

- 잘못 읽힌 HD 글자 대응표를 수정했습니다(`줄→좋`, `붙→불` 등으로 보이던 문제).
- 대사 36개 메시지의 오타·오역·어색한 표현을 다듬고 감시원 용어를 통일했습니다.
- 경고문, 도움말, 모니터 조정, 에필로그·엔딩 화면의 한글 HD를 추가했습니다. 엔딩 뉴스 HD는 실제 게임에서 적용을 확인했습니다.
- 오르골 화면의 그림이 사라지는 문제를 수정하고, 대사 말줄임표와 마인 스로어 개량형 이름을 정리했습니다.

대사 검수 범위와 남은 확인 항목은 [검수 기록](docs/dialogue-review-20261027.md)에 있습니다. 수정 대사의 실게임 줄 넘침·타이밍과 Steam 팩 실행은 아직 확인하지 않았습니다.

## 설치 (권장)

먼저 가지고 있는 판에 맞는 [Mulderland Enhancement Pack](https://www.mulderland.com/en/games/resident-evil-3-nemesis)을 설치합니다. Classic REbirth와 HD 텍스처가 함께 설치됩니다.

- **GOG판:** GOG에서 Resident Evil 3 Nemesis를 **일본어(Japanese)판**으로 받은 뒤 **GOG Enhancement Pack**을 설치합니다. 게임 폴더는 GOG 설치 폴더입니다.
- **Steam판:** **Steam Enhancement Pack**을 설치합니다. REbirth가 Steam 설치 폴더 안의 `rebirth` 폴더에 설치되며, 이 `rebirth` 폴더가 게임 폴더입니다.

팩을 설치할 때 "Graphical improvements"(HD 텍스처)는 켜고, 일본어 데이터를 지우는 "Free space" 옵션은 끕니다.

그다음 한글 모드를 설치합니다.

1. 게임을 끄고, [Releases](../../releases)의 `re3-korean-hd-<버전>.zip` 내용을 게임 폴더에 그대로 복사합니다. 게임 폴더는 `BIOHAZARD(R) 3 PC.exe`와 `ddraw.dll`이 있는 곳이며, 압축 파일 안의 `mod_korean_hd/`, `hires/`를 덮어씁니다.
2. `config.ini`의 `[DLL]`에서 `JapaneseEnable = 1`인지 확인합니다. 한글은 일본어 글꼴 경로로 출력됩니다. REbirth는 종료할 때 `config.ini`를 다시 쓰므로 게임이 꺼진 상태에서 바꿉니다.
3. 게임을 실행하고 REbirth 모드 목록에서 **BIOHAZARD 3 - Korean HD**를 고릅니다. 실행 옵션에 `-dev_korean_hd`를 넣으면 목록 없이 바로 시작합니다.

지원하는 실행 파일과 REbirth는 다음과 같습니다. 두 실행 파일은 PE 헤더의 4GB 플래그만 다르고 코드와 데이터가 같습니다.

| 항목 | 조건 |
|---|---|
| 게임 | SourceNext `BIOHAZARD(R) 3 PC.exe` (SHA256 `b5215af1…`), 또는 Mulderland 팩의 4GB 패치본 (`BH3Launcher.exe`, Steam 팩의 `BIOHAZARD(R) 3 PC.exe`, SHA256 `f36c3e47…`) |
| Classic REbirth | `ddraw.dll` 1.0.3 (SHA256 `8ef09511…`). 다른 버전은 [지원 추가 방법](docs/porting.md) 참고 |

GOG 팩에서는 실행을 확인했습니다. Steam 팩은 같은 실행 파일을 쓰지만 아직 실행해 보지 않았습니다.

**macOS(Wine, Sikarugir 등):** Wine 접두사 안의 게임 폴더(예: `.../drive_c/GOG Games/Resident Evil 3`)에 복사합니다.

## 제거

- 게임 폴더의 `mod_korean_hd/`를 지웁니다.
- `hires/`에 덮어쓴 HD 텍스처는 Enhancement Pack을 다시 설치해 되돌립니다.

## 문제 해결

게임 폴더의 `mod_korean_hd/korean_hd.log`를 확인합니다(실행할 때마다 새로 씁니다).

- **`REFUSED: unsupported Classic REbirth ddraw.dll`:** 지원하지 않는 REbirth 버전입니다.
- **`room unmatched`:** 번역을 찾지 못한 방입니다. 이슈로 알려 주세요.
- **SD로 보이는 글자:** `python tools/audit_glyphs.py --game <게임 폴더>`로 HD 글자표에서 빠진 토큰을 찾을 수 있습니다.

## 직접 빌드

번역은 `translation/`의 전용 데이터에서 빌드합니다.

```sh
python -m pip install -r requirements.txt
python tools/setup.py --game <게임 폴더>          # mod_korean_hd/와 HD 텍스처를 빌드해 설치
python tools/make_release.py --game <게임 폴더>   # DLL 빌드 + 설치 + 배포 zip
RE3_GAME=<게임 폴더> python -m unittest discover -s tests
```

빌드에는 게임 원본 파일(`Rofs*.dat`, `BIOHAZARD(R) 3 PC.exe`, `ddraw.dll`, `hires/`)과 mingw(`i686-w64-mingw32-gcc`)가 필요합니다. `setup.py`는 덮어쓰는 파일을 `work/backups/`에 먼저 복사합니다.

구성은 다음과 같습니다.

- `src/`: REbirth 모드 DLL입니다. 방 메시지 교체, 한글 폰트 VRAM 업로드, 실행 파일과 REbirth 문자열 교체, REbirth 메뉴 글자 처리를 합니다.
- `translation/text/`: 대사(`rooms.json`)와 실행 파일 문자열(`exe.json`)입니다. 글자는 그대로, 제어 코드와 빈칸 채움은 `{FA02}`, `{0000}`처럼 적습니다. `F6`은 공백, `FC`는 줄바꿈입니다. 대사는 길이를 바꿔도 되지만 실행 파일 문자열은 구간마다 바이트 길이가 같아야 합니다.
- `translation/graphics/`: 한글 그래픽(게임 파일별 픽셀 조각)과 한글 폰트 행입니다.
- `translation/`의 나머지: 글자 코드와 글자 대응표(스테이지별), REbirth 메뉴 번역, 문서 조판 데이터입니다.
- `tools/setup.py`: 빌드와 설치를 맡습니다. `install_hd.py`는 HD 텍스처, `audit_glyphs.py`는 HD 누락 글자 검사를 맡습니다.
- [docs/hd-assets.md](docs/hd-assets.md): HD 텍스처 키 계산 방식
- [docs/porting.md](docs/porting.md): 다른 REbirth 버전을 지원하는 방법

## 크레딧과 권리

- **[Classic REbirth](https://classicrebirth.com/):** Gemini. 모드 수명주기와 ROFS 형식은 [RE3-Mod-SDK](https://github.com/Gemini-Loboto3/RE3-Mod-SDK)를 참고했습니다.
- **글꼴:** Noto Sans KR, Noto Serif KR. SIL Open Font License이며 `assets/fonts/`에 라이선스가 함께 있습니다.
- **코드:** [LICENSE](LICENSE).
- **Enhancement Pack:** [Mulderland](https://www.mulderland.com/)
- **게임:** BIOHAZARD 3는 CAPCOM의 저작물입니다. 이 저장소에는 게임 전체 데이터가 포함되지 않습니다. 번역 그래픽 조각과 엔딩 텍스처 참조 이미지, 배포 zip의 한글 그래픽은 게임에서 파생한 자료입니다.
