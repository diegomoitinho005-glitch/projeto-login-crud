from pathlib import Path
from typing import Optional
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="API Clínica - Login e Agendamentos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# --- BANCO DE DADOS EM MEMÓRIA ---
users_db = {
    "admin": "1234",
    "recepcao": "1234",
}

active_tokens = {}

consultas_db = [
    {
        "id": 1,
        "paciente": "Maria Oliveira",
        "contato": "(75) 99911-2233",
        "medico": "Dr. Roberto Lima - Clínico Geral",
        "data_hora": "2026-11-23T14:00",
        "status": "Confirmada",
    },
    {
        "id": 2,
        "paciente": "João Pedro Santos",
        "contato": "(75) 98844-5566",
        "medico": "Dra. Ana Paula - Cardiologia",
        "data_hora": "2026-11-23T15:30",
        "status": "Agendada",
    },
]
next_consulta_id = 3


# --- SCHEMAS ---
class UserSchema(BaseModel):
    username: str
    password: str


class ConsultaSchema(BaseModel):
    paciente: str
    contato: str
    medico: str
    data_hora: str
    status: str


# --- AUTENTICAÇÃO ---
def verificar_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente ou inválido")

    token = authorization.split(" ")[1]
    username = active_tokens.get(token)

    if not username:
        raise HTTPException(status_code=401, detail="Sessão expirada ou inválida")

    return username


@app.post("/register", status_code=201)
def register(user: UserSchema):
    username = user.username.strip()
    if not username or not user.password:
        raise HTTPException(status_code=400, detail="Usuário e senha são obrigatórios")

    if username in users_db:
        raise HTTPException(status_code=400, detail="Este usuário já existe")

    users_db[username] = user.password
    return {"message": "Usuário cadastrado com sucesso"}


@app.post("/login")
def login(user: UserSchema):
    senha_salva = users_db.get(user.username)
    if not senha_salva or senha_salva != user.password:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    token = secrets.token_hex(16)
    active_tokens[token] = user.username
    return {"token": token, "username": user.username}


@app.post("/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        active_tokens.pop(token, None)
    return {"message": "Logout realizado"}


# --- CRUD DE CONSULTAS DA CLÍNICA ---
@app.get("/consultas")
def listar_consultas(usuario: str = Depends(verificar_token)):
    return consultas_db


@app.post("/consultas", status_code=201)
def criar_consulta(consulta: ConsultaSchema, usuario: str = Depends(verificar_token)):
    global next_consulta_id
    nova_consulta = {
        "id": next_consulta_id,
        "paciente": consulta.paciente,
        "contato": consulta.contato,
        "medico": consulta.medico,
        "data_hora": consulta.data_hora,
        "status": consulta.status,
    }
    consultas_db.append(nova_consulta)
    next_consulta_id += 1
    return nova_consulta


@app.put("/consultas/{consulta_id}")
def atualizar_consulta(
    consulta_id: int,
    consulta_atualizada: ConsultaSchema,
    usuario: str = Depends(verificar_token),
):
    for item in consultas_db:
        if item["id"] == consulta_id:
            item["paciente"] = consulta_atualizada.paciente
            item["contato"] = consulta_atualizada.contato
            item["medico"] = consulta_atualizada.medico
            item["data_hora"] = consulta_atualizada.data_hora
            item["status"] = consulta_atualizada.status
            return item
    raise HTTPException(status_code=404, detail="Consulta não encontrada")


@app.delete("/consultas/{consulta_id}")
def deletar_consulta(consulta_id: int, usuario: str = Depends(verificar_token)):
    for index, item in enumerate(consultas_db):
        if item["id"] == consulta_id:
            consultas_db.pop(index)
            return {"message": "Agendamento removido com sucesso"}
    raise HTTPException(status_code=404, detail="Consulta não encontrada")


# --- SERVIR FRONTEND ---
@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/style.css")
def serve_css():
    return FileResponse(FRONTEND_DIR / "style.css")


@app.get("/app.js")
def serve_js():
    return FileResponse(FRONTEND_DIR / "app.js")
