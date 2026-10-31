import { Editor } from "https://esm.sh/@tiptap/core@2.27.3";
import StarterKit from "https://esm.sh/@tiptap/starter-kit@2.27.3";

const RETRASO_MS = 2000;

const elemento = document.getElementById("editor");
const indicador = document.getElementById("estado-guardado");
const documentoId = elemento.dataset.documentoId;
const contenidoInicial = JSON.parse(document.getElementById("contenido-inicial").textContent);

let temporizador = null;
let enVuelo = false;
let sucio = false; // hay cambios sin confirmar en el servidor

function mostrar(estado) {
  indicador.textContent = estado;
}

const editor = new Editor({
  element: elemento,
  extensions: [StarterKit],
  content: contenidoInicial,
  onUpdate() {
    sucio = true;
    mostrar("Guardando…");
    clearTimeout(temporizador);
    temporizador = setTimeout(guardar, RETRASO_MS);
  },
  onSelectionUpdate: actualizarBarra,
  onTransaction: actualizarBarra,
});
window.editorDocumento = editor;

async function guardar() {
  temporizador = null;
  if (enVuelo) return; // al terminar el PUT actual se reevalúa
  if (!sucio) return;
  enVuelo = true;
  sucio = false; // los cambios posteriores a este punto vuelven a marcarlo
  const cuerpo = JSON.stringify(editor.getJSON());
  let correcto = false;
  try {
    const respuesta = await fetch(`/documentos/${documentoId}/contenido`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: cuerpo,
    });
    correcto = respuesta.ok;
  } catch {
    correcto = false;
  }
  enVuelo = false;
  if (!correcto) {
    sucio = true; // se reintenta en el siguiente cambio
    mostrar("Error al guardar");
    return;
  }
  if (sucio) {
    // hubo cambios durante el PUT: se manda el contenido más reciente
    clearTimeout(temporizador);
    guardar();
  } else {
    mostrar("Guardado");
  }
}

window.addEventListener("beforeunload", (evento) => {
  if (sucio || enVuelo) {
    evento.preventDefault();
    evento.returnValue = "";
  }
});

const acciones = {
  negrita: { ejecutar: (c) => c.toggleBold(), activo: () => editor.isActive("bold") },
  cursiva: { ejecutar: (c) => c.toggleItalic(), activo: () => editor.isActive("italic") },
  h1: { ejecutar: (c) => c.toggleHeading({ level: 1 }), activo: () => editor.isActive("heading", { level: 1 }) },
  h2: { ejecutar: (c) => c.toggleHeading({ level: 2 }), activo: () => editor.isActive("heading", { level: 2 }) },
  h3: { ejecutar: (c) => c.toggleHeading({ level: 3 }), activo: () => editor.isActive("heading", { level: 3 }) },
  parrafo: { ejecutar: (c) => c.setParagraph(), activo: () => editor.isActive("paragraph") },
  lista: { ejecutar: (c) => c.toggleBulletList(), activo: () => editor.isActive("bulletList") },
  "lista-numerada": { ejecutar: (c) => c.toggleOrderedList(), activo: () => editor.isActive("orderedList") },
};

const botones = document.querySelectorAll(".editor-barra button[data-accion]");
botones.forEach((boton) => {
  boton.addEventListener("click", () => {
    acciones[boton.dataset.accion].ejecutar(editor.chain().focus()).run();
  });
});

function actualizarBarra() {
  botones.forEach((boton) => {
    boton.classList.toggle("activo", acciones[boton.dataset.accion].activo());
  });
}
actualizarBarra();
