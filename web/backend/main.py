"""ChromaPeak Studio — Web 后端 (FastAPI).

启动：uvicorn main:app --reload  (在 web/backend 目录，项目根已加入 sys.path)
"""
from __future__ import annotations

import io
import json
import os
import sys
import uuid
import zipfile

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

# 让 web/backend 能 import 到项目根的 core 包
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.io import load_from_bytes  # noqa: E402
from core.pipeline import (analyze, available_algorithms,  # noqa: E402
                          run_algorithms)

from . import auth, db  # noqa: E402

db.init_db()
EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

app = FastAPI(title="ChromaPeak Studio API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.mount("/exports", StaticFiles(directory=EXPORT_DIR), name="exports")


# ---------------- auth ----------------
class RegisterReq(BaseModel):
    username: str
    password: str


class LoginReq(BaseModel):
    username: str
    password: str


@app.post("/register")
def register(req: RegisterReq, session: Session = Depends(db.get_session)):
    if session.query(db.User).filter_by(username=req.username).first():
        raise HTTPException(400, "用户名已存在")
    user = db.User(username=req.username,
                   password_hash=auth.hash_password(req.password))
    session.add(user)
    session.commit()
    return {"id": user.id, "username": user.username}


@app.post("/login")
def login(req: LoginReq, session: Session = Depends(db.get_session)):
    user = session.query(db.User).filter_by(username=req.username).first()
    if not user or not auth.verify_password(req.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return {"access_token": auth.create_token(user.id), "token_type": "bearer"}


# ---------------- algorithms ----------------
@app.get("/algorithms")
def algorithms():
    return available_algorithms()


# ---------------- analyze ----------------
@app.post("/analyze")
def analyze_file(file: UploadFile = File(...), algorithms: str = None,
                params: str = None):
    data = file.file.read()
    try:
        x, y = load_from_bytes(data, file.filename or "data.csv")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"无法解析文件：{e}")
    algos = json.loads(algorithms) if algorithms else None
    algo_params = json.loads(params) if params else None
    res = run_algorithms(x, y, algos, algo_params)
    return res


# ---------------- batch (zip) ----------------
@app.post("/analyze_batch")
def analyze_batch(file: UploadFile = File(...), algorithms: str = None):
    data = file.file.read()
    algos = json.loads(algorithms) if algorithms else None
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "上传的不是有效的 zip 文件")
    rows = []
    names = []
    for name in zf.namelist():
        if name.lower().endswith((".csv", ".txt")):
            try:
                x, y = load_from_bytes(zf.read(name), name)
            except Exception:
                continue
            res = run_algorithms(x, y, algos)
            for alg, peaks in res["results"].items():
                for p in peaks:
                    rows.append([name, alg, p["rt"], p["height"], p["area"],
                                 p["fwhm"], p["asymmetry"], p["score"]])
            names.append(name)
    out_name = f"batch_{uuid.uuid4().hex[:8]}.csv"
    out_path = os.path.join(EXPORT_DIR, out_name)
    import csv
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "algorithm", "rt", "height", "area",
                    "fwhm", "asymmetry", "score"])
        w.writerows(rows)
    return {"files": names, "n_peaks": len(rows),
            "download_url": f"/exports/{out_name}"}


# ---------------- projects ----------------
class ProjectReq(BaseModel):
    name: str
    algorithms: list = []
    algo_params: dict = {}
    x: list = []
    y: list = []


@app.get("/projects")
def list_projects(user=Depends(auth.get_current_user),
                 session: Session = Depends(db.get_session)):
    items = session.query(db.Project).filter_by(owner_id=user.id).all()
    return [{"id": p.id, "name": p.name, "created_at": p.created_at}
            for p in items]


@app.post("/projects")
def create_project(req: ProjectReq, user=Depends(auth.get_current_user),
                  session: Session = Depends(db.get_session)):
    import time
    proj = db.Project(
        owner_id=user.id, name=req.name,
        algorithms=json.dumps(req.algorithms),
        algo_params=json.dumps(req.algo_params),
        x_data=json.dumps(req.x), y_data=json.dumps(req.y),
        results="{}", created_at=time.time())
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return {"id": proj.id, "name": proj.name}


@app.get("/projects/{pid}")
def get_project(pid: int, user=Depends(auth.get_current_user),
               session: Session = Depends(db.get_session)):
    proj = session.get(db.Project, pid)
    if not proj or proj.owner_id != user.id:
        raise HTTPException(404, "项目不存在")
    return {
        "id": proj.id, "name": proj.name,
        "algorithms": json.loads(proj.algorithms),
        "algo_params": json.loads(proj.algo_params),
        "x": json.loads(proj.x_data) if proj.x_data else [],
        "y": json.loads(proj.y_data) if proj.y_data else [],
        "results": json.loads(proj.results) if proj.results else {},
    }


# ---------------- WebSocket 流式推理 ----------------
@app.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            msg = await websocket.receive_json()
            x = msg.get("x")
            y = msg.get("y")
            algos = msg.get("algorithms") or [m["name"] for m in available_algorithms()]
            algo_params = msg.get("params") or {}
            pre_opts = msg.get("preprocess") or None
            if not x or not y:
                await websocket.send_json({"type": "error", "msg": "缺少 x/y"})
                continue
            # 边算边发：每个算法算完即推送其峰
            for name in algos:
                res = analyze(x, y, name, algo_params.get(name), pre_opts)
                await websocket.send_json({
                    "type": "algorithm", "algorithm": name,
                    "peaks": res["peaks"],
                    "y_proc": res["y_proc"][::10],  # 降采样避免过大
                })
            await websocket.send_json({"type": "done",
                                      "y_proc": analyze(x, y, algos[0], None,
                                                       pre_opts)["y_proc"][::10]})
    except WebSocketDisconnect:
        return
    except Exception as e:  # noqa: BLE001
        await websocket.send_json({"type": "error", "msg": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
