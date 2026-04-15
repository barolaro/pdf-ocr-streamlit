import io
import shutil
from typing import List, Tuple

import pypdfium2 as pdfium
import pytesseract
import streamlit as st
from PIL import Image
from pypdf import PdfReader, PdfWriter

MAX_FILE_MB = 25
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

DEFAULT_BLOCK_SIZE = 25
MAX_BLOCK_SIZE = 100


st.set_page_config(page_title="PDF OCR por bloques", page_icon="📄", layout="centered")


def check_tesseract() -> Tuple[bool, str]:
    try:
        tesseract_path = shutil.which("tesseract")
        if not tesseract_path:
            return False, "No se encontró Tesseract en el sistema."
        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract detectado: {version}"
    except Exception as e:
        return False, f"Error verificando Tesseract: {e}"


def available_languages() -> List[str]:
    try:
        return pytesseract.get_languages(config="")
    except Exception:
        return []


def get_page_count(pdf_bytes: bytes) -> int:
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    return len(pdf)


def render_page(pdf: pdfium.PdfDocument, page_index: int, dpi: int) -> Image.Image:
    scale = dpi / 72.0
    page = pdf[page_index]
    bitmap = page.render(scale=scale)
    image = bitmap.to_pil().convert("L")
    return image


def image_to_searchable_pdf_page(image: Image.Image, lang: str) -> bytes:
    return pytesseract.image_to_pdf_or_hocr(
        image,
        extension="pdf",
        lang=lang,
    )


def merge_pdf_bytes_list(pdf_parts: List[bytes]) -> bytes:
    writer = PdfWriter()

    for part in pdf_parts:
        reader = PdfReader(io.BytesIO(part))
        for page in reader.pages:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def process_block(
    pdf_bytes: bytes,
    start_page: int,
    end_page: int,
    dpi: int,
    lang: str,
    total_pages: int,
    progress_bar,
    status_box,
) -> bytes:
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    block_page_pdfs: List[bytes] = []

    for page_idx in range(start_page, end_page):
        image = render_page(pdf, page_idx, dpi=dpi)
        page_pdf = image_to_searchable_pdf_page(image, lang=lang)
        block_page_pdfs.append(page_pdf)

        pct = int(((page_idx + 1) / total_pages) * 100)
        progress_bar.progress(
            pct,
            text=f"Procesando página {page_idx + 1}/{total_pages}"
        )
        status_box.info(
            f"Bloque actual: páginas {start_page + 1}-{end_page} | "
            f"Página {page_idx + 1} de {total_pages}"
        )

    return merge_pdf_bytes_list(block_page_pdfs)


def process_large_pdf_in_blocks(
    pdf_bytes: bytes,
    lang: str,
    dpi: int,
    block_size: int,
    progress_bar,
    status_box,
) -> bytes:
    total_pages = get_page_count(pdf_bytes)
    merged_blocks: List[bytes] = []

    for block_start in range(0, total_pages, block_size):
        block_end = min(block_start + block_size, total_pages)

        block_pdf = process_block(
            pdf_bytes=pdf_bytes,
            start_page=block_start,
            end_page=block_end,
            dpi=dpi,
            lang=lang,
            total_pages=total_pages,
            progress_bar=progress_bar,
            status_box=status_box,
        )
        merged_blocks.append(block_pdf)

    status_box.info("Uniendo bloques finales...")
    final_pdf = merge_pdf_bytes_list(merged_blocks)
    progress_bar.progress(100, text="Proceso terminado")
    return final_pdf


def main():
    st.title("📄 PDF OCR robusto por bloques")
    st.write("Sube un PDF y genera un PDF OCR searchable por partes, pensado para archivos grandes.")

    ok, msg = check_tesseract()
    if not ok:
        st.error(msg)
        st.stop()
    st.success(msg)

    langs = available_languages()
    lang_options = []

    if "spa" in langs and "eng" in langs:
        lang_options.append("spa+eng")
    if "spa" in langs:
        lang_options.append("spa")
    if "eng" in langs:
        lang_options.append("eng")

    if not lang_options:
        st.error("No hay idiomas OCR disponibles.")
        st.stop()

    selected_lang = st.selectbox("Idioma OCR", lang_options, index=0)

    dpi = st.selectbox("Calidad / DPI", [100, 120, 140, 150], index=1)
    block_size = st.slider("Páginas por bloque", min_value=5, max_value=MAX_BLOCK_SIZE, value=DEFAULT_BLOCK_SIZE, step=5)

    uploaded_file = st.file_uploader("Sube tu PDF", type=["pdf"])

    if uploaded_file is None:
        st.info("Esperando archivo PDF.")
        return

    pdf_bytes = uploaded_file.read()
    input_size_mb = len(pdf_bytes) / (1024 * 1024)

    st.write(f"**Archivo:** {uploaded_file.name}")
    st.write(f"**Tamaño original:** {input_size_mb:.2f} MB")

    try:
        total_pages = get_page_count(pdf_bytes)
        st.write(f"**Páginas detectadas:** {total_pages}")
    except Exception as e:
        st.error(f"No se pudo leer el PDF: {e}")
        return

    if total_pages == 0:
        st.error("El PDF no contiene páginas.")
        return

    if total_pages > 1000:
        st.warning(
            f"El PDF tiene {total_pages} páginas. Se intentará procesar por bloques, "
            "pero puede tardar bastante en Streamlit Cloud."
        )

    if st.button("Procesar OCR"):
        progress_bar = st.progress(0, text="Iniciando proceso...")
        status_box = st.empty()

        try:
            output_pdf = process_large_pdf_in_blocks(
                pdf_bytes=pdf_bytes,
                lang=selected_lang,
                dpi=dpi,
                block_size=block_size,
                progress_bar=progress_bar,
                status_box=status_box,
            )

            output_size_mb = len(output_pdf) / (1024 * 1024)
            st.write(f"**Tamaño final:** {output_size_mb:.2f} MB")

            if len(output_pdf) <= MAX_FILE_BYTES:
                st.success("El archivo final quedó dentro del límite de 25 MB.")
            else:
                st.warning(
                    f"El archivo final quedó en {output_size_mb:.2f} MB. "
                    "Para bajarlo más, usa un DPI menor o bloques más pequeños."
                )

            out_name = uploaded_file.name.rsplit(".", 1)[0] + "_ocr_bloques.pdf"

            st.download_button(
                label="Descargar PDF OCR",
                data=output_pdf,
                file_name=out_name,
                mime="application/pdf",
            )

        except Exception as e:
            st.error(f"Error procesando el PDF: {e}")


if __name__ == "__main__":
    main()
