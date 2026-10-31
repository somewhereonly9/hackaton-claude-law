from fastapi import APIRouter, Depends

from app.auth.dependencias import usuario_actual
from app.modelos import Usuario

router = APIRouter()


# Ruta provisional: la Task 6 la reemplaza por el listado real.
@router.get("/documentos")
def listar(usuario: Usuario = Depends(usuario_actual)):
    return {"ok": True}
