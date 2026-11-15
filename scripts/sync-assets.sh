#!/bin/sh
# 제품 자료(PDF), 구성도, 로고, 화면 캡처를 사이트 소스로 가져와 변환한다.
# 원본 위치는 모두 환경 변수로 준다. 주지 않은 항목은 건너뛰고, 커밋된 파일을 그대로 둔다.
#
#   PDF_SRC=<PDF 디렉터리>             제품소개서_일반.pdf (src/assets/pdf/). 다른 PDF는 공개하지 않는다
#   BRAND_SRC=<로고 디렉터리>           lockup/, symbol/, favicon/ (src/static/brand/, 파비콘)
#   CONSOLE_CAPTURES=<디렉터리>         콘솔 화면 캡처 (console-*)
#   ID_CAPTURES=<디렉터리>              Symbolon ID 화면 캡처를 잘라 낸 것 (id-*)
#   (캡처 스크립트는 공개하지 않는다. 로컬의 scripts/private/에 둔다)
#   PAGE_CAPTURES=<디렉터리>            게이트웨이 안내 페이지 캡처 gw-forbidden.jpg
#
#   예: PDF_SRC=~/work/docs scripts/sync-assets.sh
#
# 그림은 macOS sips로 줄여 AVIF + JPEG(대체용)로 만든다. sips가 없으면 원본을 복사만 한다.
# PDF는 저장소에 커밋한다(공개 사이트가 바로 내려받게). 원본이 바뀌면 이 스크립트를 다시 돌리고 build.py를 다시 돌린다.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PDF_OUT="$ROOT/src/assets/pdf"
IMG_OUT="$ROOT/src/assets/img"
mkdir -p "$PDF_OUT" "$IMG_OUT"

HAVE_SIPS=0
command -v sips >/dev/null 2>&1 && HAVE_SIPS=1
[ "$HAVE_SIPS" = 1 ] || echo "경고: sips가 없어 그림을 변환하지 않고 원본을 복사합니다." >&2

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# encode <원본> <출력 이름(확장자 없이)> <최대 너비>
encode() {
  src=$1; name=$2; maxw=$3
  if [ "$HAVE_SIPS" = 0 ]; then
    ext=${src##*.}
    cp "$src" "$IMG_OUT/$name.$ext"
    return
  fi
  work="$TMP/$name.png"
  sips -s format png "$src" --out "$work" >/dev/null
  w=$(sips -g pixelWidth "$work" | awk '/pixelWidth/ {print $2}')
  if [ "$w" -gt "$maxw" ]; then
    sips --resampleWidth "$maxw" "$work" --out "$work" >/dev/null
  fi
  # sips의 AVIF 인코더는 가로·세로가 홀수이면 Chromium에서 회색 판으로 보이는 파일을 만든다. 짝수로 맞춘다.
  w=$(sips -g pixelWidth "$work" | awk '/pixelWidth/ {print $2}')
  h=$(sips -g pixelHeight "$work" | awk '/pixelHeight/ {print $2}')
  ew=$((w - w % 2)); eh=$((h - h % 2))
  if [ "$ew" != "$w" ] || [ "$eh" != "$h" ]; then
    sips -c "$eh" "$ew" --cropOffset 1 1 "$work" --out "$work" >/dev/null 2>&1 || true
  fi
  sips -s format avif -s formatOptions 62 "$work" --out "$IMG_OUT/$name.avif" >/dev/null
  sips -s format jpeg -s formatOptions 82 "$work" --out "$IMG_OUT/$name.jpg" >/dev/null
}

# 브랜드(로고·파비콘): 그대로 복사한다. 로고 파일은 고치지 않는다.
BRAND="${BRAND_SRC:-}"
BRAND_OUT="$ROOT/src/static/brand"
if [ -n "$BRAND" ]; then
  echo "브랜드"
  mkdir -p "$BRAND_OUT"
  for f in symbolon-on-dark symbolon-on-light symbolon-gateway-on-dark symbolon-gateway-on-light \
           symbolon-id-on-dark symbolon-id-on-light symbolon-gateway-ko-on-dark symbolon-id-ko-on-dark; do
    cp "$BRAND/lockup/$f.svg" "$BRAND_OUT/$f.svg"
  done
  cp "$BRAND/symbol/symbol-on-dark.svg" "$BRAND/symbol/symbol-on-light.svg" "$BRAND_OUT/"
  cp "$BRAND/favicon/favicon.svg" "$ROOT/src/static/favicon.svg"
  cp "$BRAND/favicon/favicon-32.png" "$BRAND/favicon/favicon-180.png" "$ROOT/src/static/"
  echo "  lockup 8, symbol 2, favicon 3"
else
  echo "브랜드: BRAND_SRC 없음(건너뜀)"
fi

if [ -n "${PDF_SRC:-}" ]; then
  echo "PDF"
  for f in 제품소개서_일반.pdf; do  # 공개 자료는 일반 제품소개서 하나뿐이다(나머지는 요청 시 제공)
    if [ -f "$PDF_SRC/$f" ]; then
      cp "$PDF_SRC/$f" "$PDF_OUT/$f"
      echo "  $f"
    else
      echo "  없음: $f" >&2
    fi
  done
else
  echo "PDF: PDF_SRC 없음(건너뜀)"
fi

# 구성도(포트·내부 구성요소 이름이 들어 있다)는 공개 사이트에 싣지 않는다. DIAGRAM_SRC는 무시한다.
if [ -n "${DIAGRAM_SRC:-}" ]; then
  echo "구성도: 공개하지 않음(DIAGRAM_SRC 무시)"
fi

# Symbolon Gateway 콘솔 화면은 견본 데이터로 찍는다(캡처 스크립트는 scripts/private/, 공개하지 않음).
# 찍은 디렉터리를 CONSOLE_CAPTURES로 주면 변환한다. 주지 않으면 이미 커밋된 콘솔 그림을 그대로 둔다.
if [ -n "${CONSOLE_CAPTURES:-}" ]; then
  echo "콘솔 화면 ($CONSOLE_CAPTURES)"
  for f in "$CONSOLE_CAPTURES"/*-light.png "$CONSOLE_CAPTURES"/*-dark.png; do
    [ -f "$f" ] || continue
    base=$(basename "$f" .png)
    encode "$f" "console-$base" 2000
    echo "  $base"
  done
else
  echo "콘솔 화면: CONSOLE_CAPTURES가 없어 건너뜀(커밋된 그림 유지)"
fi

# Symbolon ID 화면은 가상 사용자로 찍고 잘라 낸 PNG 디렉터리를 ID_CAPTURES로 준다
# 내부 동작을 설명하는 안내 문구와 내부 식별자 열은 가린 뒤 넣는다(커밋된 그림은 가린 상태다).
# (id-login|id-account|id-users|id-groups)-(light|dark).png. 주지 않으면 커밋된 그림을 그대로 둔다.
if [ -n "${ID_CAPTURES:-}" ]; then
  echo "Symbolon ID 화면"
  for f in "$ID_CAPTURES"/id-*.png; do
    base=$(basename "$f" .png)
    case "$base" in id-login-*|id-account-*) w=1000 ;; *) w=1600 ;; esac
    encode "$f" "$base" "$w"
  done
  rm -f "$IMG_OUT"/id-login.* "$IMG_OUT"/id-account.* "$IMG_OUT"/id-users.* "$IMG_OUT"/id-groups.*
  echo "  login, account, users, groups (light/dark)"
fi
if [ -n "${PAGE_CAPTURES:-}" ]; then
  encode "$PAGE_CAPTURES/gw-forbidden.jpg" gw-forbidden 1440
  echo "안내 페이지: gw-forbidden"
fi

echo "완료. 이제 python3 build.py"
