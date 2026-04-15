import io

import pytesseract
import streamlit as st
from pdf2image import convert_from_bytes


st.set_page_config(page_title="PDF OCR", page_icon="📄")

st.title("📄 PDF OCR")
st.write("Sube un PDF y genera una versión OCR simple.")

uploaded_file = st.file_uploader("Sube tu PDF", type=["pdf"])


def images_to_pdf(images):
    pdf_bytes = io.BytesIO()
    if not images:
        return None

    images_rgb = []
    for img in images:
        if img.mode != "RGB":
            img = img.convert("RGB")
        images_rgb.append(img)

    images_rgb[0].save(
        pdf_bytes,
        format="PDF",
        save_all=True,
        append_images=images_rgb[1:],
    )
    return pdf_bytes.getvalue()


if uploaded_file is not None:
    st.info(f"Archivo cargado: {uploaded_file.name}")

    if st.button("Procesar OCR"):
        with st.spinner("Procesando PDF..."):
            try:
                images = convert_from_bytes(uploaded_file.read())
                processed_images = []

                for img in images:
                    _ = pytesseract.image_to_string(img, lang="spa")
                    img = img.convert("L")
                    processed_images.append(img)

                pdf_output = images_to_pdf(processed_images)

                if pdf_output:
                    size_mb = len(pdf_output) / (1024 * 1024)
                    st.success(f"PDF generado correctamente. Tamaño: {size_mb:.2f} MB")

                    st.download_button(
                        "Descargar PDF",
                        data=pdf_output,
                        file_name="ocr.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.error("No se pudo generar el PDF.")

            except Exception as e:
                st.error(f"Error: {e}")
