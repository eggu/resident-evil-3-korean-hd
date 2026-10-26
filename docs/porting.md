# 다른 Classic REbirth 버전 지원하기

REbirth `ddraw.dll`의 함수와 전역 변수 위치는 빌드마다 다릅니다. 그래서 모드는 SHA256이 정확히 일치하는 빌드만 받아들이고, 나머지는 거부합니다(`korean_hd.log`에 `REFUSED: unsupported Classic REbirth ddraw.dll`). 새 빌드를 지원하려면 아래 두 표에 행을 하나씩 추가합니다.

| 위치 | 내용 |
|---|---|
| `src/korean_hd.c`의 `rebirth_profiles[]` | 파일 크기, SHA256, 그리고 아래 RVA |
| `tools/rebirth_profiles.py`의 `PROFILES` | 메시지 저장 함수 VA, exe 테이블 시작 주소를 담는 REbirth 전역 변수 RVA |

1.0.3 값을 기준으로, 새 빌드에서 같은 코드를 찾아 채웁니다. 각 주소에는 아래 바이트 패턴이 있습니다.

| 필드 | 1.0.3 | 찾는 법 |
|---|---|---|
| `upload` | `0xA8480` | exe `0x425450`의 `jmp`가 가리키는 곳. `55 8B EC 83 EC 0C 56 8B 75 08 0F B7 46 04 0F BF D0` |
| `lookup` / `lookup_end_global` | `0x74F90` / `0x701200` | 코드포인트 이진 탐색. `55 8B EC 8B 0D <lookup_end_global>` |
| `store`, `messages` | `0xAB490`, `0x4020B0` | `mov edx,id; mov ecx,text; call store` 패턴. `messages`는 메시지 포인터 표 |
| `menu_returns[3]` | `0xB6964, 0xB6C28, 0xB6C67` | 메뉴 글자 렌더러에서 `lookup`을 부른 바로 다음 주소 |
| `cell_site` / `cell_tail` / `cell_f2` | `0xB6A2D` / `0xB6ABA` / `0xB6A55` | `81 F9 00 EB 00 00 74 3B 81 F9 00 F2 00 00 74 18 8B 45 DC` |
| `menu_base_site`, `menu_one`, `menu_list` | `0xCD18B`, `0x7CA2A8`, `0x7CA2B4` | 불러오기 메뉴 문자열 포인터를 채우는 코드(1.0.3 RVA `0xCD17E`) |
| `own_slot[4]` / `own_japanese[4]` | `0x7CA298…` / `0x3F601C…` | "불러오지 않음, 저장 안 함, 예, 아니오" 슬롯과 일본어 원문 |

**추가 작업:**
- 상태 화면 HD 키(`translation/status-route.json`)는 exe와 ddraw 해시에 묶여 있습니다. 새 빌드에서 상태 화면 HD를 쓰려면 이 파일도 새로 만들어야 합니다. 방법은 [hd-assets.md](hd-assets.md)를 참고합니다.
- 값을 채운 뒤에는 게임에서 대사, REbirth 메뉴, 불러오기·저장 메뉴, 상태 화면을 확인합니다. 그리고 `korean_hd.log`에 `REFUSED`나 `skipped`가 없는지 봅니다.
