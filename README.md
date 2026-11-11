# BIOHAZARD 3 Korean HD

Classic REbirth로 실행하는 **BIOHAZARD 3 PC**에서 한글로 플레이할 수 있게 해 주는 모드입니다.
대사, 아이템, 파일 목록, 문서, 상태 화면, REbirth 메뉴(키 설정, 저장, 불러오기)가 한글로 나옵니다.

## 스크린샷

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/1.png" alt="인트로 영상 한글 자막"></td>
    <td width="50%"><img src="docs/screenshots/2.png" alt="질과 다리오의 한글 대사"></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/3.png" alt="다리오의 한글 대사"></td>
    <td width="50%"><img src="docs/screenshots/4.png" alt="리로딩 툴 아이템 설명"></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/5.png" alt="창고 열쇠 사용 메시지"></td>
    <td width="50%"><img src="docs/screenshots/6.png" alt="용병의 일기 표지"></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/7.png" alt="용병의 일기 본문"></td>
    <td width="50%"><img src="docs/screenshots/8.png" alt="시계탑 엽서 설명"></td>
  </tr>
</table>

## 설치 (권장)

먼저 가지고 있는 판에 맞는 [Mulderland Enhancement Pack](https://www.mulderland.com/en/games/resident-evil-3-nemesis)을 설치합니다. Classic REbirth와 HD 텍스처가 함께 설치됩니다.

- **GOG판:** GOG에서 Resident Evil 3 Nemesis를 **일본어(Japanese)판**으로 받은 뒤 **GOG Enhancement Pack**을 설치합니다. 게임 폴더는 GOG 설치 폴더입니다.
- **Steam판:** **Steam Enhancement Pack**을 설치합니다. REbirth가 Steam 설치 폴더 안의 `rebirth` 폴더에 설치되며, 이 `rebirth` 폴더가 게임 폴더입니다.

팩을 설치할 때 "Graphical improvements"(HD 텍스처)는 켜고, 일본어 데이터를 지우는 "Free space" 옵션은 끕니다.

그다음 [Releases](../../releases)에서 설치 방식 하나를 골라 받습니다. 두 방식의 한글 내용은 같고, 함께 설치하지 않습니다.

### 방식 1. REbirth 모드 목록 (`re3-korean-hd-<버전>.zip`)

1. 게임을 끄고, 압축 파일 내용을 게임 폴더에 그대로 복사합니다. 게임 폴더는 `BIOHAZARD(R) 3 PC.exe`와 `ddraw.dll`이 있는 곳이며, 압축 파일 안의 `mod_korean_hd/`, `hires/`를 덮어씁니다.
2. `config.ini`의 `[DLL]`에서 `JapaneseEnable = 1`인지 확인합니다. 한글은 일본어 글꼴 경로로 출력됩니다. REbirth는 종료할 때 `config.ini`를 다시 쓰므로 게임이 꺼진 상태에서 바꿉니다.
3. 게임을 실행하고 REbirth 모드 목록에서 **BIOHAZARD 3 - Korean HD**를 고릅니다. 실행 옵션에 `-dev_korean_hd`를 넣으면 목록 없이 바로 시작합니다.

### 방식 2. ASI (`re3-korean-hd-<버전>-asi.zip`)

모드 목록에서 고르지 않고 게임을 그냥 실행하면 적용됩니다. 다른 ASI 모드와 함께 쓰려는 경우에 알맞습니다.

1. [Ultimate ASI Loader](https://github.com/ThirteenAG/Ultimate-ASI-Loader)(`dsound.dll`)가 게임 폴더에 있어야 합니다. 이미 있으면 그대로 둡니다. 다른 `dsound.dll`(예: DSOAL)이 있으면 덮어쓰지 말고 `winmm.dll` 이름으로 넣습니다.
2. 게임을 끄고, 압축 파일 내용(`RE3.KoreanHD.asi`, `mod_korean_hd/`, `DATA*`, `hires/`)을 게임 폴더에 그대로 복사합니다. 한글 그래픽이 `DATA`, `DATA_J`, `DATA_AJ`의 원본 파일을 덮어쓰므로, 같은 이름 파일이 있으면 먼저 백업해 둡니다.
3. `config.ini`의 `[DLL]`에서 `JapaneseEnable = 1`인지 확인합니다.
4. 모드 목록에서 다른 모드를 고르지 않고 게임을 실행합니다.

## 제거

- 게임 폴더의 `mod_korean_hd/`를 지웁니다.
- ASI 방식은 `RE3.KoreanHD.asi`도 지우고, 덮어쓴 `DATA`, `DATA_J`, `DATA_AJ`의 한글 그래픽 파일은 백업한 파일로 되돌립니다.
- `hires/`에 덮어쓴 HD 텍스처는 Enhancement Pack을 다시 설치해 되돌립니다.

## 크레딧과 권리

- **[Classic REbirth](https://classicrebirth.com/)** Gemini. 
- **글꼴:** Noto Sans KR, Noto Serif KR. SIL Open Font License이며 `assets/fonts/`에 라이선스가 함께 있습니다.
- **코드:** [LICENSE](LICENSE).
- **게임:** BIOHAZARD 3는 CAPCOM의 저작물입니다. 이 저장소에는 게임 전체 데이터가 포함되지 않습니다. 번역 그래픽 조각과 엔딩 텍스처 참조 이미지, 배포 zip의 한글 그래픽은 게임에서 파생한 자료입니다.
