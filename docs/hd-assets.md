# HD 텍스처 키

REbirth의 HD 키는 모두 **BGRA 픽셀의 CRC32**를 대문자 16진수로 쓴 값입니다. 교체 파일은 `hires/<category>/<KEY>.webp`에 둡니다. 키를 직접 확인하려면 `config.ini`에 `HDTexturesDump = 1`을 넣고 `dump/<category>/`에 쌓인 파일을 봅니다.

| 대상 | 해시 대상 | 빌더 |
|---|---|---|
| 폰트 (TEXJ, tpage 0x1C/0x1D) | 256×256 페이지 하나를 CLUT 행 하나로 디코드한 결과 | `build_font_hd.py` |
| 상태 atlas (STMOJIJ 256×72) | TIM 업로드 영역(crop). 키 계산은 ddraw 0x1008CE60 | `build_ui_hd.py` + `install_hd.py` |
| 문서, JapaneseEnable=1 | 문서(256×176)를 맨 위에 둔 256×256 VRAM 페이지 전체. ddraw 0x1008C880 | `build_doc_pages.py` |
| 문서, file/*.png 경로 | `png_texture_key`(별도 sentinel 키), `hires/memo` | `build_hd.py` |

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
