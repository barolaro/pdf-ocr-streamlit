import io
import zipfile
import shutil
from typing import List

import pypdfium2 as pdfium
import pytesseract
import streamlit as st
from PIL import Image
from pypdf import PdfReader, PdfWriter

st.set_page_config(page_title="PDF OCR masivo", page_icon="📄")

# CONFIG
DEFAULT_BLOCK_SIZE = 20


# ------------------------
# UTILIDADES
# ------------------------

def check_tesseract():
    if not shutil.which("tesseract"):
        st.error("Tesseract no está instalado.")
        st.stop()
    st.success("Tesseract listo ✅")


def get_page_count(pdf_bytes):
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    return len(pdf)


def render_page(pdf, index, dpi):
    scale = dpi / 72
    page = pdf[index]
    bitmap = page.render(scale=scale)
    return bitmap.to_pil().convert("L")


def ocr_image(image, lang):
    return pytesseract.image_to_pdf_or_hocr(
        image,
        extension="pdf",
        lang=lang
    )


def merge_pages(pdf_parts):
    writer = PdfWriter()
    for part in pdf_parts:
        reader = PdfReader(io.BytesIO(part))
        for page in reader.pages:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# ------------------------
# PROCESO PRINCIPAL
# ------------------------

def process_pdf_blocks(pdf_bytes, block_size, dpi, lang):
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    total_pages = len(pdf)

    zip_buffer = io.BytesIO()
    zip_file = zipfile.ZipFile(zip_buffer, "w")

    progress = st.progress(0)
    status = st.empty()

    block_number = 1

    for start in range(0, total_pages, block_size):
        end = min(start + block_size, total_pages)

        status.info(f"Procesando bloque {block_number}: páginas {start+1}-{end}")

        pages_pdf = []

        for i in range(start, end):
            img = render_page(pdf, i, dpi)
            pdf_page = ocr_image(img, lang)
            pages_pdf.append(pdf_page)

            progress.progress((i + 1) / total_pages)

        merged = merge_pages(pages_pdf)

        filename = f"bloque_{block_number:03d}_pag_{start+1}_{end}.pdf"
        zip_file.writestr(filename, merged)

        block_number += 1

    zip_file.close()
    progress.progress(1.0)

    return zip_buffer.getvalue()


# ------------------------
# UI
# ------------------------

def main():
    st.title("📄 OCR para PDFs grandes")
    st.write("Convierte PDFs grandes a OCR dividiéndolos en partes descargables.")

    check_tesseract()

    st.markdown("### Configuración")

    lang = st.selectbox(
        "Idioma",
        ["spa", "eng", "spa+eng"],
        index=0
    )

    dpi = st.selectbox(
        "Calidad",
        {
            "Baja (rápido y liviano)": 100,
            "Media (recomendado)": 120,
            "Alta (mejor calidad)": 140
        }.keys()
    )

    dpi = {
        "Baja (rápido y liviano)": 100,
        "Media (recomendado)": 120,
        "Alta (mejor calidad)": 140
    }[dpi]

    block_size = st.slider(
        "Páginas por bloque",
        5,
        50,
        DEFAULT_BLOCK_SIZE
    )

    st.info("💡 Para PDFs grandes usa bloques de 10 a 20 páginas")

    uploaded_file = st.file_uploader("Sube tu PDF", type=["pdf"])

    if uploaded_file is None:
        return

    pdf_bytes = uploaded_file.read()

    total_pages = get_page_count(pdf_bytes)

    st.write(f"📄 Páginas detectadas: {total_pages}")

    if total_pages > 500:
        st.warning("Archivo grande. Se procesará por partes para evitar errores.")

    if st.button("Procesar OCR"):
        zip_result = process_pdf_blocks(
            pdf_bytes,
            block_size,
            dpi,
            lang
        )

        st.success("Proceso terminado")

        st.download_button(
            "Descargar ZIP con PDFs OCR",
            zip_result,
            file_name="ocr_resultado.zip"
        )


if __name__ == "__main__":
    main()
