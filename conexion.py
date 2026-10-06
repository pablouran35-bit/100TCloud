import psycopg2
from dotenv import load_dotenv
import os


# ==========================================================
# CARGAR CONFIGURACIÓN
# ==========================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


# ==========================================================
# CONEXIÓN A POSTGRESQL
# ==========================================================

def conectar():
    return psycopg2.connect(DATABASE_URL)