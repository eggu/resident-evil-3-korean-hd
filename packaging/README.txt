BIOHAZARD 3 Korean HD (한글 모드)
==================================

SourceNext 일본어판 BIOHAZARD 3 PC + Classic REbirth에서 대사, 아이템, 파일,
문서, 상태 화면, REbirth 메뉴를 한글로 보여 주고 글자와 문서를 HD로 그립니다.

준비
----
가지고 있는 판에 맞는 Mulderland Enhancement Pack을 설치합니다.
https://www.mulderland.com/en/games/resident-evil-3-nemesis
팩 설치 때 "Graphical improvements"(HD 텍스처)는 켜고, 일본어 데이터를 지우는
"Free space" 옵션은 끕니다.

- GOG판: GOG에서 Resident Evil 3 Nemesis를 일본어(Japanese)판으로 받은 뒤
  "GOG Enhancement Pack"을 설치합니다. 게임 폴더는 GOG 설치 폴더입니다.
- Steam판: "Steam Enhancement Pack"을 설치합니다. 게임 폴더는 Steam 설치 폴더
  안의 rebirth 폴더입니다.

설치
----
1. 게임을 끕니다.
2. 이 압축 파일의 내용(mod_korean_hd 폴더, hires 폴더)을 게임 폴더에 그대로 복사해
   덮어씁니다. 게임 폴더는 BIOHAZARD(R) 3 PC.exe와 ddraw.dll이 있는 폴더입니다.
3. 게임 폴더의 config.ini에서 [DLL] 아래 JapaneseEnable = 1 인지 확인합니다.
   (게임이 꺼진 상태에서 바꿉니다. 켜진 상태에서는 종료할 때 다시 덮어씁니다.)
4. 게임을 실행하고 REbirth 모드 목록에서 "BIOHAZARD 3 - Korean HD"를 고릅니다.

확인된 환경: Mulderland GOG Enhancement Pack (SourceNext BIOHAZARD(R) 3 PC.exe,
Classic REbirth ddraw.dll 1.0.3). Steam 팩은 같은 실행 파일(4GB 패치본)을 쓰지만
실행 확인 전입니다.
다른 REbirth 버전에서는 모드가 동작하지 않고 mod_korean_hd/korean_hd.log에
"REFUSED"가 남습니다.

제거
----
mod_korean_hd 폴더를 지웁니다. hires 폴더에 덮어쓴 HD 텍스처는 Enhancement Pack을
다시 설치하거나 덮어쓰기 전에 백업해 둔 파일로 되돌립니다.

크레딧
------
번역: BIOHAZARD 3 한글 패치 v1.0.15 제작자
Classic REbirth: Gemini / Enhancement Pack: Mulderland
글꼴: Noto Sans KR, Noto Serif KR (SIL Open Font License)
BIOHAZARD 3는 CAPCOM의 저작물입니다.
소스와 빌드 방법: https://github.com/eggu/re3-korean-hd
