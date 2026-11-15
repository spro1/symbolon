"""AVIF가 Chromium에서 JPEG와 같은 그림으로 보이는지 확인한다(선택 점검, Python Playwright 필요).

    python3 build.py --serve &          # 다른 터미널에서
    python scripts/check-avif.py http://127.0.0.1:8000

sips가 만든 AVIF가 회색 판으로 깨지는 경우를 잡으려고 둔다. 평균 색 차이가 6을 넘으면 "다름"으로 표시하고 종료 코드 1.
"""
import os, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = os.path.join(ROOT, "dist", "assets", "img")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
names=sorted(f[:-5] for f in os.listdir(d) if f.endswith(".avif"))
JS="""async (n) => {
 const load = s => new Promise((r,j)=>{const i=new Image(); i.onload=()=>r(i); i.onerror=j; i.src=s;});
 const a = await load('assets/img/'+n+'.avif'), b = await load('assets/img/'+n+'.jpg');
 const W=200, H=Math.round(200*b.naturalHeight/b.naturalWidth);
 const px = img => { const c=document.createElement('canvas'); c.width=W; c.height=H; const x=c.getContext('2d'); x.drawImage(img,0,0,W,H); return x.getImageData(0,0,W,H).data; };
 const p=px(a), q=px(b); let s=0; for (let k=0;k<p.length;k+=4) s+=Math.abs(p[k]-q[k])+Math.abs(p[k+1]-q[k+1])+Math.abs(p[k+2]-q[k+2]);
 return s/(p.length/4)/3;
}"""
bad=0
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); pg.goto(BASE + "/404.html")
    for n in names:
        diff=pg.evaluate(JS, n)
        flag = "  <-- 다름" if diff>6 else ""
        if flag: bad+=1
        print(f"{diff:6.2f} {n}{flag}")
    b.close()
print("bad", bad)
sys.exit(1 if bad else 0)
