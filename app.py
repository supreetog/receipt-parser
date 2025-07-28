import streamlit as st
import tempfile
import os
import re
import pandas as pd

# Try to import PyMuPDF for PDF support
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    st.warning("PyMuPDF not found. PDF support disabled. Install with: pip install PyMuPDF")

st.set_page_config(page_title="Receipt Parser", page_icon="🧾", layout="wide")

class ReceiptParser:
    def extract_text_from_pdf(self, pdf_bytes):
        """Extract text from PDF file"""
        if not PDF_SUPPORT:
            st.error("PDF support not available. Please install PyMuPDF: pip install PyMuPDF")
            return ""
            
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_file_path = tmp_file.name
            
            try:
                doc = fitz.open(tmp_file_path)
                full_text = ""
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    page_text = page.get_text()
                    full_text += page_text + "\n"
                
                doc.close()
                return full_text
            
            finally:
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            return ""

    def extract_items(self, text):
        """Specialized extractor for Walmart receipts"""
        lines = text.strip().split('\n')
        items = []

        # Debug: show first 20 lines
        st.write("**First 20 lines of text:**")
        for i, line in enumerate(lines[:20]):
            st.text(f"{i+1:2d}: {line}")

        skip_terms = [
            'subtotal', 'total', 'tax', 'change', 'cash', 'credit', 'debit', 
            'visa', 'mastercard', 'thank', 'receipt', 'store', 'balance', 'amount', 'payment'
        ]

        # Pattern: "Item Name ....... 2.98"
        pattern = re.compile(r'(.+?)\s+([\d]+\.\d{2})$')

        for line in lines:
            line = line.strip()
            if not line or len(line) < 4:
                continue

            line_lower = line.lower()
            if any(term in line_lower for term in skip_terms):
                continue

            match = pattern.search(line)
            if match:
                name = match.group(1).strip()
                price_str = match.group(2).strip()

                # Clean name
                name = re.sub(r'\d{8,}', '', name).strip()  # Remove long digit strings (UPC)
                name = re.sub(r'[^A-Za-z0-9\s\-\.,]', '', name)

                try:
                    price = float(price_str)
                    if 0.01 <= price <= 500 and len(name) > 2:
                        items.append({'name': name, 'price': f"${price:.2f}"})
                except:
                    continue

        return items

def main():
    st.title("🧾 Walmart Receipt Parser")

    parser = ReceiptParser()
    uploaded_file = st.file_uploader("Upload a Walmart receipt (PDF)", type=['pdf'])

    if uploaded_file is not None:
        with st.spinner("Processing receipt..."):
            pdf_bytes = uploaded_file.getvalue()
            text = parser.extract_text_from_pdf(pdf_bytes)

            if text:
                items = parser.extract_items(text)

                if items:
                    st.subheader(f"✅ Found {len(items)} items")
                    df_items = pd.DataFrame(items)
                    st.dataframe(df_items, use_container_width=True)

                    # Tab-separated format for Google Sheets
                    st.subheader("📋 Copy this into Google Sheets:")
                    tab_separated = '\n'.join([f"{item['name']}\t{item['price']}" for item in items])
                    st.text_area("Tab-separated list:", value=tab_separated, height=200)

                else:
                    st.warning("⚠️ No items detected. Check the receipt format or try another one.")

                if st.checkbox("🔎 Show full extracted text"):
                    st.text_area("Extracted raw text:", value=text, height=300)
            else:
                st.error("❌ Could not extract any text from the PDF.")

if __name__ == "__main__":
    main()
