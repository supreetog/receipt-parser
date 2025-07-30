import streamlit as st
from receipt_parser_core import parse_receipt_text
import pytesseract
from PIL import Image

st.title("Receipt Parser")

uploaded_file = st.file_uploader("Upload a receipt image", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="Uploaded Receipt")

    text = pytesseract.image_to_string(img)
    st.text_area("Extracted Text", text, height=200)

    result = parse_receipt_text(text)
    st.json(result)
