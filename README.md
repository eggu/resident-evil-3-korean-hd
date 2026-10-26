# BIOHAZARD 3 Korean HD

Classic REbirth로 실행하는 **SourceNext 일본어판 BIOHAZARD 3 PC**에서 한글로 플레이할 수 있게 해 주는 모드입니다. Steam판 한글 패치 v1.0.15의 번역을 이 실행 파일로 옮겼고, 글자·상태 화면·문서를 HD로 다시 그렸습니다.

- 대사, 아이템, 파일 목록, 문서, 상태 화면, REbirth 메뉴(키 설정, 저장, 불러오기)가 한글로 나옵니다.
- HD 텍스처 팩(RE:Enhance)을 쓰면 다음 셋을 고해상도로 바꿉니다.
  - 글자: Noto Sans KR
  - 상태 화면 라벨: Noto Sans KR Bold
  - 문서: Noto Serif KR SemiBold
- 대사·아이템·폰트 데이터는 이 저장소에 없습니다. 설치 스크립트가 직접 받아 둔 한글 패치 설치 파일에서 추출합니다. 문서 HD를 다시 조판하는 데 쓰는 문서 문장(`translation/documents-reviewed.json`)만 들어 있습니다.

## 준비물

| 항목 | 조건 |
|---|---|
| 게임 | SourceNext `BIOHAZARD(R) 3 PC.exe` (SHA256 `b5215af1…`) |
| Classic REbirth | `ddraw.dll` 1.0.3 (SHA256 `8ef09511…`). 다른 버전은 [지원 추가 방법](docs/porting.md) 참고 |
| 한글 패치 | `BIOHAZARD3_Korean_Patch.exe` v1.0.15 (Steam판 한글 패치 설치 파일) |
| HD (선택) | RE:Enhance HD 텍스처 팩(`hires/` 폴더). 없으면 한글만 설치됩니다 |
| Python | 3.10 이상, `pip install -r requirements.txt` |

`config.ini`의 `[DLL]`에서 `JapaneseEnable = 1`로 둬야 합니다. 한글은 일본어 글꼴 경로로 출력됩니다.

## 설치

1. [Releases](../../releases)에서 `re3-korean-hd-<버전>.zip`을 받아 압축을 풉니다. 미리 빌드한 `bin/korean_hd.dll`이 들어 있습니다.
2. 게임을 끄고 다음을 실행합니다.

   ```sh
   python -m pip install -r requirements.txt
   python tools/setup.py --game "C:\경로\Resident Evil 3" --patch "C:\경로\BIOHAZARD3_Korean_Patch.exe"
   ```

3. 게임을 실행하고 REbirth 모드 목록에서 **BIOHAZARD 3 - Korean HD**를 고릅니다. 실행 옵션에 `-dev_korean_hd`를 넣으면 목록 없이 바로 시작합니다.

설치 스크립트가 하는 일은 다음과 같습니다.
- 게임 폴더에 `mod_korean_hd/`를 만듭니다.
- `hires/`가 있으면 그 안에 HD 텍스처를 넣습니다.
- 덮어쓰는 파일은 먼저 `work/backups/`에 복사해 둡니다.
- 원본 `Rofs*.dat`나 실행 파일은 바꾸지 않습니다.

HD 텍스처 없이 한글만 설치하려면 `--no-hd`를 붙입니다.

**macOS(Wine, Sikarugir 등):** `--game`에 Wine 접두사 안의 게임 폴더 경로를 넣습니다. 예: `.../drive_c/GOG Games/Resident Evil 3`.

## 제거

- 게임 폴더의 `mod_korean_hd/`를 지웁니다.
- HD 텍스처까지 되돌리려면 `work/backups/hd-*`의 내용을 게임 폴더에 다시 복사합니다. 각 폴더는 게임 폴더와 같은 구조로 되어 있습니다.
- 새로 추가된 HD 파일 목록은 `work/*-installed.txt`에 있습니다.

## 문제 해결

게임 폴더의 `mod_korean_hd/korean_hd.log`를 확인합니다(실행할 때마다 새로 씁니다).

- **`REFUSED: unsupported Classic REbirth ddraw.dll`:** 지원하지 않는 REbirth 버전입니다.
- **`room unmatched`:** 번역을 찾지 못한 방입니다. 이슈로 알려 주세요.
- **SD로 보이는 글자:** `python tools/audit_glyphs.py --game <게임 폴더>`로 HD 글자표에서 빠진 토큰을 찾을 수 있습니다.

## 직접 빌드

```sh
i686-w64-mingw32-gcc -shared -O2 -Wall -Wextra -Werror -Wno-misleading-indentation -Wno-format-truncation \
  -DKOREAN_HD_VERSION='"1.0.0"' src/korean_hd.c -ladvapi32 -o bin/korean_hd.dll
python tools/setup.py --game <게임 폴더> --patch <한글 패치 exe>
RE3_GAME=<게임 폴더> python -m unittest discover -s tests
```

`bin/korean_hd.dll`이 없고 mingw가 설치돼 있으면, `setup.py`가 DLL을 직접 빌드합니다. 배포 zip은 `python tools/make_release.py`로 만듭니다.

구성은 다음과 같습니다.

- `src/`: REbirth 모드 DLL입니다. 하는 일은 다음과 같습니다.
  - 방 메시지 교체
  - 한글 폰트 VRAM 업로드
  - 실행 파일과 REbirth 문자열 교체
  - REbirth 메뉴 글자 처리
- `tools/setup.py`: 설치 스크립트입니다. `install_hd.py`는 HD 텍스처 빌드와 설치, `audit_glyphs.py`는 HD 누락 글자 검사를 맡습니다.
- `translation/`: 이 모드가 직접 만든 데이터입니다.
  - 글자 코드와 실제 글자의 대응표(스테이지별)
  - REbirth 메뉴 번역
  - 문서 조판 데이터
  - 실행 파일 주소 대응
- [docs/hd-assets.md](docs/hd-assets.md): HD 텍스처 키 계산 방식
- [docs/porting.md](docs/porting.md): 다른 REbirth 버전을 지원하는 방법

## 크레딧과 권리

- **번역:** Steam판 BIOHAZARD 3 한글 패치 v1.0.15 제작자. 이 모드는 그 번역을 SourceNext 실행 파일로 옮기고, 문서를 같은 문장으로 다시 조판합니다.
- **[Classic REbirth](https://classicrebirth.com/):** Gemini. 모드 수명주기와 ROFS 형식은 [RE3-Mod-SDK](https://github.com/Gemini-Loboto3/RE3-Mod-SDK)를 참고했습니다.
- **글꼴:** Noto Sans KR, Noto Serif KR. SIL Open Font License이며 `assets/fonts/`에 라이선스가 함께 있습니다.
- **코드:** [LICENSE](LICENSE).
- **게임:** BIOHAZARD 3는 CAPCOM의 저작물입니다. 이 저장소에는 게임 데이터가 들어 있지 않습니다.
