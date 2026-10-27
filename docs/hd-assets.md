# HD 텍스처 키

REbirth의 HD 키는 모두 **BGRA 픽셀의 CRC32**를 대문자 16진수로 쓴 값입니다. 교체 파일은 `hires/<category>/<KEY>.webp`에 둡니다. 키를 직접 확인하려면 `config.ini`에 `HDTexturesDump = 1`을 넣고 `dump/<category>/`에 쌓인 파일을 봅니다.

| 대상 | 해시 대상 | 빌더 |
|---|---|---|
| 폰트 (TEXJ, tpage 0x1C/0x1D) | 256×256 페이지 하나를 CLUT 행 하나로 디코드한 결과 | `build_font_hd.py` |
| 상태 atlas (STMOJIJ 256×72) | TIM 업로드 영역(crop). 키 계산은 ddraw 0x1008CE60 | `build_ui_hd.py` + `install_hd.py` |
| 문서, JapaneseEnable=1 | 문서(256×176)를 맨 위에 둔 256×256 VRAM 페이지 전체. ddraw 0x1008C880 | `build_doc_pages.py` |
| 문서, file/*.png 경로 | `png_texture_key`(별도 sentinel 키), `hires/memo` | `build_hd.py` |
| 전체 화면 그림 (경고문, 도움말 등 320×240) | 그림 전체. 16비트 색은 `c<<3 \| c>>2`, 완전한 검정은 R=1로 바꿈. `hires/bgd` | `build_screens_hd.py` |

## 폰트 페이지

한글 글자는 4bpp 페이지 안에 2비트 필드로 겹쳐 있습니다. CLUT 행 하나는 그중 필드 하나만 드러냅니다. 그래서 (페이지, CLUT 행) 조합마다 HD 이미지가 한 장씩 필요합니다.

글자 코드는 리드 바이트 EB~F0에 코드 바이트가 붙는 형식입니다. 리드 바이트별 배치는 `build_font_hd.LAYERS`에 정리되어 있습니다.

FONTST1J~7J는 스테이지마다 tpage 0x1D를 교체하므로, 스테이지별 대응표(`glyph-stage-tokens.json`)를 따로 씁니다. 대응표에 없는 칸은 SD 글자를 4배 nearest로 키워 채웁니다.

## 문서

`build_hd.py`는 검수된 문장(`translation/documents-reviewed.json`)을 다시 조판합니다.

- **글자 배율:** 문서마다(`file_id`) 본문 쪽 배율의 최솟값 하나를 공유하므로 글자 크기가 같아집니다(최대 1.5배).
- **배경판:** `PLATE_ALPHA` 100, `PLATE_GREY` 9입니다. 이 회색은 계산값이 아니라 게임 화면을 측정해서 정했습니다. 문서 바깥의 (10,10,10)과 같아지도록 맞춘 값입니다.

JapaneseEnable=1에서는 문서 페이지 키에 문서 아래 80줄도 들어갑니다. 이 80줄에는 VRAM 잔여물이 남는데, 게임 상황마다 달라집니다. 그래서 `korean_hd.dll`은 문서를 올리기 직전에 이 80줄을 0으로 채웁니다. 페이지 키는 `CRC32(문서 BGRA + 0 바이트 80줄)`이 되어 문서만으로 정해집니다.

## 설치와 복원

`tools/install_hd.py`는 덮어쓰거나 지우는 파일을 모두 `work/backups/hd-<시각>/`에 먼저 복사합니다. 복원할 때는 그 폴더 내용을 게임 폴더에 그대로 다시 복사하면 됩니다.

설치 목록은 `work/*-installed.txt`에 남습니다. 다음 실행 때 이 목록에 있지만 더 이상 만들지 않는 파일은 지웁니다.

## 전체 화면 그림

한글 패치가 글자를 그려 넣은 전체 화면 그림(경고문, 도움말)은 HD 팩에 맞는 HD가 없습니다. `build_screens_hd.py`는 다음 순서로 HD를 만듭니다(`translation/screens.json`).

1. HD 팩의 같은 화면 그림에서 시작합니다.
2. 글자 영역의 밝은 픽셀을 지웁니다. 다른 언어판(`alt`)의 같은 자리에 글자가 없으면 그 픽셀을 가져옵니다. 남은 자리는 주변 픽셀로 메웁니다.
3. 한글 문장을 Noto Sans KR Bold로 그립니다.

키는 `mod_korean_hd`의 해당 파일(DAT 안의 TIM은 `offset`)에서 계산합니다. 경고문(WARNJ.TIM), 도움말(CHECKJ.TIM), 모니터 조정(OPTIONJ.DAT), 에필로그와 엔딩(OMBG_J.DAT)이 대상입니다.

에필로그는 일본어 문단이 인물 그림 위에 겹쳐 있습니다. 그래서 밝기 기준 대신 `mask: sd`를 씁니다. 원본 SD에서 흰 글자였는데 한글 패치가 고친 픽셀을 4배로 키운 범위가 일본어 글자 자리입니다. 다른 언어판 HD는 같은 그림이라도 픽셀이 조금씩 달라 섞지 않습니다. 원본 HD가 없는 화면(키 설정 2장, 질의 다른 에필로그)은 원본도 SD이므로 만들지 않습니다.

엔딩 뉴스 원고(STR_BG.DAT의 256×176 텍스처)는 게임이 줄 단위로 잘라 자막으로 씁니다. 키 경로를 덤프로 확인하지 못해, 가능한 세 가지 키로 모두 `hires/misc`에 넣습니다(`textures`). 문서식 페이지 키, BGRA 키, PNG 키입니다. END0/1.CPT는 알려진 압축 형식이 아니어서 내용과 키를 알 수 없습니다. 엔딩 덤프가 있어야 만들 수 있습니다.
