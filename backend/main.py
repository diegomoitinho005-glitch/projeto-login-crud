import os
from pathlib import Path
from typing import Optional
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

app = FastAPI(title="API Clínica - Login e Agendamentos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# --- CONFIGURAÇÃO DO BANCO DE DADOS (NEON POSTGRESQL / SQLITE LOCAL) ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clinica.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- MODELOS DAS TABELAS SQL ---
class UsuarioDB(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)


class TokenDB(Base):
    __tablename__ = "tokens"

    token = Column(String, primary_key=True, index=True)
    username = Column(String, nullable=False)


class ConsultaDB(Base):
    __tablename__ = "consultas"

    id = Column(Integer, primary_key=True, index=True)
    paciente = Column(String, nullable=False)
    contato = Column(String, nullable=False)
    medico = Column(String, nullable=False)
    data_hora = Column(String, nullable=False)
    status = Column(String, nullable=False)


# Cria as tabelas automaticamente no Neon se ainda não existirem
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def inicializar_dados():
    db = SessionLocal()
    try:
        if db.query(UsuarioDB).count() == 0:
            db.add_all([
                UsuarioDB(username="admin", password="1234"),
                UsuarioDB(username="recepcao", password="1234"),
            ])
            db.add_all([
                ConsultaDB(
                    paciente="Maria Oliveira",
                    contato="(75) 99911-2233",
                    medico="Dr. Roberto Lima - Clínico Geral",
                    data_hora="2026-11-23T14:00",
                    status="Confirmada",
                ),
                ConsultaDB(
                    paciente="João Pedro Santos",
                    contato="(75) 98844-5566",
                    medico="Dra. Ana Paula - Cardiologia",
                    data_hora="2026-11-23T15:30",
                    status="Agendada",
                ),
            ])
            db.commit()
    finally:
        db.close()


inicializar_dados()


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
def verificar_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente ou inválido")

    token = authorization.split(" ")[1]
    sessao = db.query(TokenDB).filter(TokenDB.token == token).first()

    if not sessao:
        raise HTTPException(status_code=401, detail="Sessão expirada ou inválida")

    return sessao.username


@app.post("/register", status_code=201)
def register(user: UserSchema, db: Session = Depends(get_db)):
    username = user.username.strip()
    if not username or not user.password:
        raise HTTPException(status_code=400, detail="Usuário e senha são obrigatórios")

    usuario_existente = db.query(UsuarioDB).filter(UsuarioDB.username == username).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Este usuário já existe")

    novo_usuario = UsuarioDB(username=username, password=user.password)
    db.add(novo_usuario)
    db.commit()
    return {"message": "Usuário cadastrado com sucesso"}


@app.post("/login")
def login(user: UserSchema, db: Session = Depends(get_db)):
    usuario_salvo = db.query(UsuarioDB).filter(UsuarioDB.username == user.username).first()
    if not usuario_salvo or usuario_salvo.password != user.password:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    token = secrets.token_hex(16)
    db.add(TokenDB(token=token, username=user.username))
    db.commit()
    return {"token": token, "username": user.username}


@app.post("/logout")
def logout(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        db.query(TokenDB).filter(TokenDB.token == token).delete()
        db.commit()
    return {"message": "Logout realizado"}


# --- CRUD DE CONSULTAS DA CLÍNICA ---
@app.get("/consultas")
def listar_consultas(
    usuario: str = Depends(verificar_token),
    db: Session = Depends(get_db),
):
    return db.query(ConsultaDB).order_by(ConsultaDB.id.asc()).all()


@app.post("/consultas", status_code=201)
def criar_consulta(
    consulta: ConsultaSchema,
    usuario: str = Depends(verificar_token),
    db: Session = Depends(get_db),
):
    nova_consulta = ConsultaDB(
        paciente=consulta.paciente,
        contato=consulta.contato,
        medico=consulta.medico,
        data_hora=consulta.data_hora,
        status=consulta.status,
    )
    db.add(nova_consulta)
    db.commit()
    db.refresh(nova_consulta)
    return nova_consulta


@app.put("/consultas/{consulta_id}")
def atualizar_consulta(
    consulta_id: int,
    consulta_atualizada: ConsultaSchema,
    usuario: str = Depends(verificar_token),
    db: Session = Depends(get_db),
):
    item = db.query(ConsultaDB).filter(ConsultaDB.id == consulta_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    item.paciente = consulta_atualizada.paciente
    item.contato = consulta_atualizada.contato
    item.medico = consulta_atualizada.medico
    item.data_hora = consulta_atualizada.data_hora
    item.status = consulta_atualizada.status
    db.commit()
    db.refresh(item)
    return item


@app.delete("/consultas/{consulta_id}")
def deletar_consulta(
    consulta_id: int,
    usuario: str = Depends(verificar_token),
    db: Session = Depends(get_db),
):
    item = db.query(ConsultaDB).filter(ConsultaDB.id == consulta_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    db.delete(item)
    db.commit()
    return {"message": "Agendamento removido com sucesso"}


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
