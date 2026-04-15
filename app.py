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
MAX_PAGES = 80

DPI_CANDIDATES_COMPACT = [140, 120, 100]
DPI_CANDIDATES_NORMAL = [170, 150, 130]


st.set_page_config(page_title="PDF OCR 25MB", page_icon="📄", layout="centered")


def check_tesseract() -> Tuple[bool, str]:
    """Verifica si Tesseract está disponible."""
    try:
        tesseract_path = shutil.which("tesseract")
        if not tesseract_path:
            return False, "No se encontró el binario 'tesseract' en el sistema."

        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract detectado: {version}"
    except Exception as e:
        return False, f"Error verificando Tesseract: {e}"


def available_languages() -> List[str]:
    """Obtiene idiomas disponibles en Tesseract."""
    try:
        return pytesseract.get_languages(config="")
    except Exception:
        return []


def render_pdf_pages(pdf_bytes: bytes, dpi: int, grayscale: bool = True) -> List[Image.Image]:
    """
    Convierte páginas PDF a imágenes PIL usando pypdfium2.
    """
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    page_count = len(pdf)

    images: List[Image.Image] = []

    scale = dpi / 72.0

    for page_index in range(page_count):
        page = pdf[page_index]
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()

        if grayscale:
            pil_image = pil_image.convert("L")
        else:
            pil_image = pil_image.convert("RGB")

        images.append(pil_image)

    return images


def image_to_searchable_pdf_page(image: Image.Image, lang: str) -> bytes:
    """
    Convierte una imagen PIL en una página PDF searchable usando Tesseract.
    """
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    pdf_bytes = pytesseract.image_to_pdf_or_hocr(
        image,
        extension="pdf",
        lang=lang,
    )
    return pdf_bytes


def merge_pdf_pages(pdf_pages: List[bytes]) -> bytes:
    """
    Une varias páginas PDF en un solo archivo PDF.
    """
    writer = PdfWriter()

    for page_pdf in pdf_pages:
        reader = PdfReader(io.BytesIO(page_pdf))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def build_searchable_pdf(
    pdf_bytes: bytes,
    lang: str,
    dpi_candidates: List[int],
    progress_bar,
    status_box,
) -> Tuple[bytes, int]:
    """
    Intenta generar un PDF OCR searchable usando distintos DPI.
    Devuelve el primero que quede <= 25 MB. Si ninguno lo logra,
    devuelve el más pequeño encontrado.
    """
    best_pdf = None
    best_size = None
    best_dpi = None

    # Solo para saber cantidad de páginas una vez
    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    total_pages = len(pdf)

    for dpi_try_index, dpi in enumerate(dpi_candidates, start=1):
        status_box.info(f"Probando con DPI {dpi}...")

        images = render_pdf_pages(pdf_bytes, dpi=dpi, grayscale=True)
        page_pdfs: List[bytes] = []

        for i, image in enumerate(images, start=1):
            page_pdf = image_to_searchable_pdf_page(image, lang=lang)
            page_pdfs.append(page_pdf)

            percent = int(((i / total_pages) * 100))
            progress_bar.progress(percent, text=f"Procesando página {i}/{total_pages} con DPI {dpi}")

        merged_pdf = merge_pdf_pages(page_pdfs)
        merged_size = len(merged_pdf)

        if best_size is None or merged_size < best_size:
            best_pdf = merged_pdf
            best_size = merged_size
            best_dpi = dpi

        if merged_size <= MAX_FILE_BYTES:
            status_box.success(
                f"Listo. PDF OCR generado con DPI {dpi} y tamaño "
                f"{merged_size / (1024 * 1024):.2f} MB."
            )
            return merged_pdf, dpi

    status_box.warning(
        "No se pudo dejar bajo 25 MB sin bajar más la calidad. "
        f"Se entrega la versión más liviana encontrada (DPI {best_dpi}, "
        f"{best_size / (1024 * 1024):.2f} MB)."
    )
    return best_pdf, best_dpi


def main():
    st.title("📄 PDF OCR robusto")
    st.write("Sube un PDF y genera un PDF OCR searchable intentando mantenerlo bajo 25 MB.")

    ok, msg = check_tesseract()
    if ok:
        st.success(msg)
    else:
        st.error(msg)
        st.stop()

    langs = available_languages()
    default_lang = "spa" if "spa" in langs else ("eng" if "eng" in langs else None)

    if default_lang is None:
        st.error("No hay idiomas OCR disponibles en Tesseract.")
        st.stop()

    lang_options = []
    if "spa" in langs:
        lang_options.append("spa")
    if "eng" in langs:
        lang_options.append("eng")
    if "spa" in langs and "eng" in langs:
        lang_options.insert(0, "spa+eng")

    selected_lang = st.selectbox("Idioma OCR", options=lang_options, index=0)

    compact_mode = st.checkbox("Modo compacto (prioriza quedar bajo 25 MB)", value=True)

    uploaded_file = st.file_uploader("Sube tu PDF", type=["pdf"])

    if uploaded_file is None:
        st.info("Esperando archivo PDF.")
        return

    file_size = uploaded_file.size
    st.write(f"**Archivo:** {uploaded_file.name}")
    st.write(f"**Tamaño original:** {file_size / (1024 * 1024):.2f} MB")

    if file_size > MAX_FILE_BYTES:
        st.error("El PDF de entrada supera 25 MB. Reduce el archivo antes de subirlo.")
        return

    pdf_bytes = uploaded_file.read()

    try:
        pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
        total_pages = len(pdf)
        st.write(f"**Páginas detectadas:** {total_pages}")
    except Exception as e:
        st.error(f"No se pudo leer el PDF: {e}")
        return

    if total_pages == 0:
        st.error("El PDF no contiene páginas.")
        return

    if total_pages > MAX_PAGES:
        st.error(f"El PDF tiene {total_pages} páginas. Máximo permitido: {MAX_PAGES}.")
        return

    if st.button("Procesar OCR"):
        progress_bar = st.progress(0, text="Iniciando...")
        status_box = st.empty()

        try:
            dpi_candidates = DPI_CANDIDATES_COMPACT if compact_mode else DPI_CANDIDATES_NORMAL

            output_pdf, used_dpi = build_searchable_pdf(
                pdf_bytes=pdf_bytes,
                lang=selected_lang,
                dpi_candidates=dpi_candidates,
                progress_bar=progress_bar,
                status_box=status_box,
            )

            output_size_mb = len(output_pdf) / (1024 * 1024)
            progress_bar.progress(100, text="Proceso finalizado")

            st.write(f"**DPI usado:** {used_dpi}")
            st.write(f"**Tamaño final:** {output_size_mb:.2f} MB")

            if len(output_pdf) <= MAX_FILE_BYTES:
                st.success("El archivo final quedó dentro del límite de 25 MB.")
            else:
                st.warning("El archivo final quedó sobre 25 MB, pero se entrega la versión más liviana posible.")

            out_name = uploaded_file.name.rsplit(".", 1)[0] + "_ocr.pdf"

            st.download_button(
                label="Descargar PDF OCR",
                data=output_pdf,
                file_name=out_name,
                mime="application/pdf",
            )

        except Exception as e:
            st.error(f"Error procesando OCR: {e}")


if __name__ == "__main__":
    main()
