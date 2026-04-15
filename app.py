import io
import zipfile
import shutil

import pypdfium2 as pdfium
import pytesseract
import streamlit as st
from PIL import Image
from pypdf import PdfReader, PdfWriter

st.set_page_config(page_title="PDF OCR PRO", page_icon="📄")

# CONFIG
DEFAULT_BLOCK_SIZE = 20


# ------------------------
# UTILIDADES
# ------------------------

def check_tesseract():
    if not shutil.which("tesseract"):
        st.error("❌ Tesseract no está instalado")
        st.stop()
    st.success("✅ Tesseract listo")


def get_pdf(pdf_bytes):
    return pdfium.PdfDocument(io.BytesIO(pdf_bytes))


def render_page(pdf, index, dpi):
    scale = dpi / 72
    page = pdf[index]
    bitmap = page.render(scale=scale)
    return bitmap.to_pil().convert("L")


def ocr_page(image, lang):
    return pytesseract.image_to_pdf_or_hocr(
        image,
        extension="pdf",
        lang=lang
    )


def merge_pages(pages):
    writer = PdfWriter()
    for p in pages:
        reader = PdfReader(io.BytesIO(p))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


# ------------------------
# PROCESO PRINCIPAL
# ------------------------

def process_pdf(pdf_bytes, dpi, lang, block_size):
    pdf = get_pdf(pdf_bytes)
    total_pages = len(pdf)

    zip_buffer = io.BytesIO()
    zip_file = zipfile.ZipFile(zip_buffer, "w")

    progress = st.progress(0)
    status = st.empty()

    block_pages = []
    block_num = 1

    for i in range(total_pages):
        # OCR por página (CLAVE 🔥)
        img = render_page(pdf, i, dpi)
        page_pdf = ocr_page(img, lang)

        block_pages.append(page_pdf)

        # cada N páginas → guardar bloque
        if len(block_pages) == block_size or i == total_pages - 1:
            merged = merge_pages(block_pages)

            filename = f"bloque_{block_num:03d}_pag_{i+1-len(block_pages)+1}_{i+1}.pdf"
            zip_file.writestr(filename, merged)

            block_pages = []
            block_num += 1

        progress.progress((i + 1) / total_pages)
        status.info(f"Procesando página {i+1} de {total_pages}")

    zip_file.close()
    progress.progress(1.0)

    return zip_buffer.getvalue()


# ------------------------
# UI
# ------------------------

def main():
    st.title("📄 OCR para PDFs grandes")
    st.write("Convierte PDFs grandes a OCR de forma estable.")

    check_tesseract()

    st.markdown("### ⚙️ Configuración")

    lang = st.selectbox(
        "Idioma",
        ["spa", "eng", "spa+eng"]
    )

    quality_map = {
        "Baja (rápido)": 100,
        "Media (recomendado)": 120,
        "Alta (mejor calidad)": 140
    }

    quality_label = st.selectbox("Calidad", list(quality_map.keys()))
    dpi = quality_map[quality_label]

    block_size = st.slider(
        "Páginas por archivo",
        5, 50, DEFAULT_BLOCK_SIZE
    )

    st.info("💡 Para PDFs grandes usa bloques de 10 a 20 páginas")

    st.markdown("### 📤 Subir PDF")

    uploaded_file = st.file_uploader("Archivo PDF", type=["pdf"])

    if not uploaded_file:
        return

    pdf_bytes = uploaded_file.read()
    pdf = get_pdf(pdf_bytes)
    total_pages = len(pdf)

    st.write(f"📄 Páginas detectadas: {total_pages}")

    if total_pages > 500:
        st.warning("Archivo muy grande. Se procesará por partes.")

    st.markdown("### ▶️ Procesar")

    if st.button("Iniciar OCR"):
        zip_result = process_pdf(
            pdf_bytes,
            dpi,
            lang,
            block_size
        )

        st.success("✅ OCR terminado")

        st.download_button(
            "⬇️ Descargar resultado (ZIP)",
            zip_result,
            file_name="ocr_resultado.zip"
        )


if __name__ == "__main__":
    main()
