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
        
        # Very minimal skip terms - only obvious non-items
        skip_terms = [
            'subtotal', 'total', 'tax', 'change', 'cash', 'credit', 'debit', 
            'visa', 'mastercard', 'thank you', 'receipt #', 'store #'
        ]
        
        # Show first 20 lines for debugging
        st.write("**First 20 lines of text:**")
        for i, line in enumerate(lines[:20]):
            st.text(f"{i+1:2d}: {line}")
        
        for line in lines:
            clean_line = line.strip()
            
            # Skip very short lines
            if len(clean_line) < 3:
                continue
            
            line_lower = clean_line.lower()
            
            # Skip obvious non-item lines
            if any(term in line_lower for term in skip_terms):
                continue
            
            # Skip lines that are just numbers or codes
            #if re.match(r'^\d+

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
    main(), clean_line):
                continue
                
            # Skip lines with just special characters
            if re.match(r'^[\s\*\-=]+

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
    main(), clean_line):
                continue
            
            # Look for any line that ends with a price pattern
            price_match = re.search(r'\$?(\d+\.\d{2})\s*[A-Z]*\s*

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
    main(), clean_line)
            if price_match:
                price_str = price_match.group(1)
                
                try:
                    price = float(price_str)
                    if 0.01 <= price <= 500:  # Reasonable price range
                        # Extract everything before the price as item name
                        item_name = clean_line[:price_match.start()].strip()
                        
                        # Clean up item name - remove UPC codes and extra whitespace
                        item_name = re.sub(r'\d{10,15}', '', item_name)  # Remove UPC codes
                        item_name = re.sub(r'\s+', ' ', item_name)  # Normalize whitespace
                        item_name = item_name.replace('*', '').strip()  # Remove asterisks
                        
                        # Skip if item name is too short or looks like a code
                        if len(item_name) > 2 and not item_name.isdigit():
                            # Skip if item name contains obvious skip terms
                            if not any(term in item_name.lower() for term in skip_terms):
                                items.append({
                                    'name': item_name,
                                    'price': f"${price:.2f}"
                                })
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
