BIOHAZARD 3 Korean HD (ASI 방식)
================================

Classic REbirth로 실행하는 BIOHAZARD 3 PC(SourceNext 판)용 한글 모드입니다. 대사, 아이템, 파일 목록,
문서, 상태 화면, REbirth 메뉴(키 설정, 저장, 불러오기)가 한글로 나옵니다.
REbirth 모드 목록에서 고르지 않고 게임을 그냥 실행하면 적용되는 ASI 방식입니다.
다른 ASI 모드와 함께 쓸 수 있습니다. 모드 목록 방식 압축 파일(re3-korean-hd-<버전>.zip)과 같이 쓰지 않습니다.

준비
----
- 가지고 있는 판에 맞는 Mulderland Enhancement Pack을 설치합니다. 팩을 설치할 때 "Graphical improvements"
  (HD 텍스처)는 켜고, 일본어 데이터를 지우는 "Free space" 옵션은 끕니다.
- Ultimate ASI Loader(dsound.dll)가 게임 폴더에 있어야 합니다. 없으면
  https://github.com/ThirteenAG/Ultimate-ASI-Loader 에서 받아 dsound.dll로 넣습니다.
  다른 dsound.dll(예: DSOAL)이 있으면 덮어쓰지 말고 winmm.dll 이름으로 넣습니다.

설치
----
1. 게임을 끕니다.
2. 이 압축 파일의 내용(RE3.KoreanHD.asi, mod_korean_hd, DATA, DATA_J, DATA_AJ, hires)을 게임 폴더에 그대로
   복사해 덮어씁니다. 게임 폴더는 BIOHAZARD(R) 3 PC.exe와 ddraw.dll이 있는 폴더입니다.
   DATA, DATA_J, DATA_AJ 폴더에는 한글 그래픽 파일이 들어 있습니다. 덮어쓰기 전에 같은 이름 파일이 있으면 백업해 둡니다.
3. 게임 폴더의 config.ini에서 [DLL] 아래 JapaneseEnable = 1 인지 확인합니다.
   (게임이 꺼진 상태에서 바꿉니다. 켜진 상태에서는 종료할 때 다시 덮어씁니다.)
4. 게임을 평소처럼 실행합니다. REbirth 모드 목록에서 다른 모드를 고르지 않습니다.

확인된 환경: Mulderland GOG Enhancement Pack (SourceNext BIOHAZARD(R) 3 PC.exe,
Classic REbirth ddraw.dll 1.0.3). 다른 REbirth 버전에서는 모드가 동작하지 않고
mod_korean_hd/korean_hd.log에 "REFUSED"가 남습니다.

제거
----
RE3.KoreanHD.asi를 지우고, 덮어쓴 DATA, DATA_J, DATA_AJ의 한글 그래픽 파일과 hires 텍스처는
백업해 둔 파일로 되돌리거나 Enhancement Pack을 다시 설치합니다. mod_korean_hd 폴더도 지웁니다.

크레딧
------
번역: BIOHAZARD 3 한글 패치 v1.0.15 제작자
Classic REbirth: Gemini / Enhancement Pack: Mulderland
글꼴: Noto Sans KR, Noto Serif KR (SIL Open Font License)
BIOHAZARD 3는 CAPCOM의 저작물입니다.
소스와 빌드 방법: https://github.com/eggu/re3-korean-hd
