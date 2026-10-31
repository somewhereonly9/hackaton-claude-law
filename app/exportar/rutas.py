from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.auth.dependencias import usuario_actual
from app.db import get_db
from app.documentos import servicio
from app.exportar.pdf import ErrorConversionPDF, disposicion_adjunto, docx_a_pdf
from app.exportar.word import tiptap_a_docx
from app.modelos import Usuario

router = APIRouter(prefix="/documentos")

TIPO_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/{documento_id}/exportar.docx")
def exportar_docx(
    documento_id: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)
):
    documento = servicio.obtener(db, usuario.id, documento_id)
    contenido = tiptap_a_docx(documento.contenido, documento.titulo)
    return Response(
        contenido,
        media_type=TIPO_DOCX,
        headers={"Content-Disposition": disposicion_adjunto(documento.titulo, "docx")},
    )


# `def` sincrónica: la conversión bloquea (Lock + subprocess) y así corre fuera del event loop.
@router.get("/{documento_id}/exportar.pdf")
def exportar_pdf(
    documento_id: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)
):
    documento = servicio.obtener(db, usuario.id, documento_id)
    docx = tiptap_a_docx(documento.contenido, documento.titulo)
    try:
        pdf = docx_a_pdf(docx)
    except ErrorConversionPDF:
        return PlainTextResponse(
            "No se pudo generar el PDF. Puedes descargar el .docx.", status_code=503
        )
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": disposicion_adjunto(documento.titulo, "pdf")},
    )
