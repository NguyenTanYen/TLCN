"""Kiểm tra độ bền của bộ chấm phiếu (OMR) của hệ thống trên ảnh phiếu tổng hợp.

Chạy:  python tools/omr/kiem_tra_omr.py   (từ thư mục HeThong, đã cài thư viện của backend)
Phần 1: 30 phiếu 40 câu (2/3/4 phương án), MSSV 8 chữ số, 4 mã đề – qua 6 điều kiện ảnh.
Phần 2: 20 phiếu × 40 câu với các kiểu tô khác nhau (bút chì nhạt, tô không kín, vết tẩy, gạch chéo ô cũ, tô 2 ô, bỏ trống).
"""
import random, sys, time
from pathlib import Path
import numpy as np, cv2, fitz
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.services import paper as P, omr
rng=random.Random(7)
nopts=[4]*30+[3]*6+[2]*4
o=P.SheetOptions(subtitle="DBMS330284", exam_title="Thử nghiệm", n_questions=40, options_per_question=nopts, student_digits=8, version_codes=["01","02","03","04"])
N=30
fills=[]
for i in range(N):
    ans={q+1:("" if rng.random()<0.05 else rng.choice("ABCD"[:nopts[q]])) for q in range(40)}
    fills.append({"student":f"2213{rng.randrange(10000):04d}","version":rng.choice(o.version_codes),"answers":ans})
doc=fitz.open(stream=P.sheet_pdf(o,prefills=fills),filetype="pdf")
base=[]
for p in doc:
    pix=p.get_pixmap(matrix=fitz.Matrix(150/72,150/72),colorspace=fitz.csGRAY)
    base.append(np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width).copy())
def tilt(g):
    h,w=g.shape; M=cv2.getRotationMatrix2D((w/2,h/2),rng.uniform(-7,7),rng.uniform(.85,.95)); return cv2.warpAffine(g,M,(w,h),borderValue=110)
def phone(g):
    h,w=g.shape; d=lambda:rng.uniform(0,.06)
    src=np.float32([[0,0],[w,0],[w,h],[0,h]]); dst=np.float32([[w*d(),h*d()],[w*(1-d()),h*d()],[w*(1-d()),h*(1-d())],[w*d(),h*(1-d())]])
    out=cv2.warpPerspective(g,cv2.getPerspectiveTransform(src,dst),(w,h),borderValue=70).astype(np.float32)
    yy,xx=np.mgrid[0:h,0:w]; light=0.6+0.4*(xx/w)*(1-0.5*yy/h); out=out*light
    out=cv2.GaussianBlur(out,(5,5),0)+np.random.normal(0,6,out.shape)
    out=np.clip(out,0,255).astype(np.uint8); return cv2.imdecode(cv2.imencode('.jpg',out,[cv2.IMWRITE_JPEG_QUALITY,60])[1],0)
def upside(g): return cv2.rotate(g,cv2.ROTATE_180)
def land(g): return cv2.rotate(g,cv2.ROTATE_90_CLOCKWISE)
def scrib(g):
    g=g.copy(); h,w=g.shape
    for _ in range(15):
        x,y=rng.randrange(w),rng.randrange(h); cv2.line(g,(x,y),(x+rng.randrange(-80,80),y+rng.randrange(-40,40)),rng.randrange(60,160),2)
    return g
conds={"Bản quét 150 dpi":lambda g:g,"Quét nghiêng ±7°, thu nhỏ":tilt,"Ảnh chụp điện thoại (phối cảnh, ánh sáng lệch, mờ, JPEG 60)":phone,"Đặt ngược 180°":upside,"Ảnh xoay ngang 90°":land,"Nét bút vẽ lung tung (kể cả đè lên ô định vị)":scrib}
for name,f in conds.items():
    ok_s=ok_v=ok_a=tot=err=0; t=time.time()
    for g,fi in zip(base,fills):
        try: r=omr.read_sheet(f(g),o)
        except Exception as e: err+=1; continue
        ok_s+=r["student_code"]==fi["student"]; ok_v+=r["version_code"]==fi["version"]
        ok_a+=sum(r["answers"][q]==fi["answers"][q] for q in range(1,41)); tot+=40
    print(f"{name}\t{ok_s}/{N}\t{ok_v}/{N}\t{ok_a}/{N*40}\terr={err}\t{(time.time()-t)/N*1000:.0f}ms")

print("--- Kiểu tô")
rng=random.Random(11)
o=P.SheetOptions(n_questions=40, student_digits=8, version_codes=["01","02"])
L=P.sheet_layout(o); S=150/25.4
blank=fitz.open(stream=P.sheet_pdf(o,prefills=[{"student":"22130001","version":"01","answers":{}}]),filetype="pdf")[0]
pix=blank.get_pixmap(matrix=fitz.Matrix(150/72,150/72),colorspace=fitz.csGRAY)
g0=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width).copy()
bq={}
for b in L["answers"]: bq.setdefault(b["q"],{})[b["label"]]=(b["x"]*S,b["y"]*S)
r=L["r"]*S
def dot(g,xy,val,rad=0.9): cv2.circle(g,(int(xy[0]),int(xy[1])),int(r*rad),int(val),-1)
def X(g,xy): x,y=xy; d=int(r*1.1); cv2.line(g,(int(x-d),int(y-d)),(int(x+d),int(y+d)),30,2); cv2.line(g,(int(x-d),int(y+d)),(int(x+d),int(y-d)),30,2)
res={k:[0,0,0] for k in ["Tô bút chì đậm vừa (xám 110)","Tô bút chì nhạt (xám 150)","Tô không kín (≈60% ô)","Vết tẩy còn mờ (xám 215) + ô tô mới","Gạch chéo ô cũ + tô ô mới","Tô 2 ô (phải được cảnh báo)","Bỏ trống"]}
for t in range(20):
    g=g0.copy(); truth={}; kind={}
    for q in range(1,41):
        k=list(res)[q%len(res)]; labs=list(bq[q]); a=rng.choice(labs); kind[q]=k
        if k.startswith("Tô bút chì đậm"): dot(g,bq[q][a],110); truth[q]=a
        elif k.startswith("Tô bút chì nhạt"): dot(g,bq[q][a],150); truth[q]=a
        elif k.startswith("Tô không kín"):
            x,y=bq[q][a]; cv2.ellipse(g,(int(x),int(y)),(int(r*.9),int(r*.9)),0,0,215,40,-1); truth[q]=a
        elif k.startswith("Vết tẩy"):
            old=rng.choice([l for l in labs if l!=a]); dot(g,bq[q][old],215); dot(g,bq[q][a],40); truth[q]=a
        elif k.startswith("Gạch chéo"):
            old=rng.choice([l for l in labs if l!=a]); X(g,bq[q][old]); dot(g,bq[q][a],40); truth[q]=a
        elif k.startswith("Tô 2"):
            b2=rng.choice([l for l in labs if l!=a]); dot(g,bq[q][a],40); dot(g,bq[q][b2],40); truth[q]="".join(sorted(a+b2))
        else: truth[q]=""
    rr=omr.read_sheet(g,o)
    fl={int(s.split()[1].rstrip(':')) for s in rr["issues"] if s.startswith("Câu")}
    for q in range(1,41):
        c=res[kind[q]]; c[0]+=1; c[1]+=rr["answers"][q]==truth[q]; c[2]+= q in fl
for k,(n,ok,f) in res.items(): print(f"{k}\t{ok}/{n}\tcảnh báo {f}")
