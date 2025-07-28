import streamlit as st
import re
from datetime import datetime
import pandas as pd
import tempfile
import os

# Try to import PyMuPDF for PDF support
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    st.warning("⚠️ PyMuPDF not found. PDF support disabled. Install with: pip install PyMuPDF")

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
        """Extract items from Walmart receipt text"""
        lines = text.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        items = []
        
        # Skip terms for non-item lines
        skip_terms = [
            'subtotal', 'tax due', 'total', 'change due', 'cash tend', 'credit card',
            'debit card', 'visa', 'mastercard', 'receipt', 'thank you', 'walmart'
        ]
        
        # Walmart item patterns
        item_patterns = [
            r'^([A-Za-z][^0-9]*?)\s+(\d{10,15})\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*$',
            r'^([A-Za-z][^@]*?)\s+\d+\s*@\s*\$?[\d.]+\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*$',
            r'^([A-Za-z][^$]*?)\s+\$(\d+\.\d{2})\s*[A-Z]*\s*$',
            r'^([A-Za-z].*?)\s+(\d{10,15})\s+([^$]*?)\s+\$(\d+\.\d{2})\s*[A-Z]*\s*$',
            r'^([A-Za-z][^$]*?)\s+(\d+\.\d{2})\s*[A-ZTFN]*\s*$',
        ]
        
        for line in lines:
            clean_line = line.strip()
            
            if len(clean_line) < 3:
                continue
            
            line_lower = clean_line.lower()
            
            # Skip non-item lines
            if any(term in line_lower for term in skip_terms):
                continue
                
            # Skip lines with just numbers
            if clean_line.isdigit():
                continue
            
            # Try to match item patterns
            for pattern in item_patterns:
                match = re.match(pattern, clean_line)
                if match:
                    groups = match.groups()
                    
                    # Extract item name and price
                    if len(groups) == 3 and groups[1].isdigit() and len(groups[1]) > 10:
                        item_name = groups[0].strip()
                        price_str = groups[2].strip()
                    elif len(groups) == 4:
                        item_name = f"{groups[0]} {groups[2]}".strip()
                        price_str = groups[3].strip()
                    elif len(groups) >= 2:
                        item_name = groups[0].strip()
                        price_str = groups[-1].strip()
                    else:
                        continue
                    
                    # Clean item name
                    item_name = re.sub(r'\s+', ' ', item_name)
                    item_name = item_name.replace('*', '').strip()
                    
                    if len(item_name) > 2 and not item_name.isdigit():
                        try:
                            price = float(price_str)
                            if 0.01 <= price <= 1000:
                                items.append({
                                    'name': item_name,
                                    'price': f"${price:.2f}"
                                })
                                break
                        except ValueError:
                            continue
        
        return items

def main():
    st.title("🧾 Receipt Parser")
    
    parser = ReceiptParser()
    
    uploaded_file = st.file_uploader("Choose a receipt PDF", type=['pdf'])
    
    if uploaded_file is not None:
        with st.spinner("Processing receipt..."):
            pdf_bytes = uploaded_file.getvalue()
            text = parser.extract_text_from_pdf(pdf_bytes)
            
            if text:
                items = parser.extract_items(text)
                
                if items:
                    st.subheader(f"Found {len(items)} Items")
                    df_items = pd.DataFrame(items)
                    st.dataframe(df_items, use_container_width=True)
                    
                    # Tab-separated format for Google Sheets
                    st.subheader("Copy for Google Sheets")
                    tab_separated = '\n'.join([f"{item['name']}\t{item['price']}" for item in items])
                    st.text_area("Copy this:", value=tab_separated, height=200)
                else:
                    st.warning("No items found.")
                
                # Show raw text for debugging
                if st.checkbox("Show extracted text"):
                    st.text_area("Raw text:", value=text, height=300)
            else:
                st.error("Could not extract text from PDF.")

if __name__ == "__main__":
    main()
