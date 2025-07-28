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
        """Improved Walmart receipt parser with spacing + line grouping fixes"""
        import re
          'visa', 'mastercard', 'thank', 'receipt', 'store', 'balance', 'amount', 
                  
        lines = text.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        cleaned_lines = []
    
        # Fix "4 . 9 7" to "4.97", and clean weird spaces
        for line in lines:
            fixed_line = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', line)  # 4 . 9 7 → 4.97
            fixed_line = re.sub(r'\s{2,}', ' ', fixed_line)  # collapse large spaces
            fixed_line = fixed_line.strip()
            cleaned_lines.append(fixed_line)
    
        # Debug: show first 20 cleaned lines
        st.write("**First 20 cleaned lines of text:**")
        for i, line in enumerate(cleaned_lines[:20]):
            st.text(f"{i+1:2d}: {line}")
    
        skip_terms = ['subtotal', 'total', 'tax', 'change', 'cash', 'credit', 'debit', 
                    'payment', 'approval', 'terminal', 'tc#', 'st#', 'showers dr', 'mountain view']
    
        items = []
        previous_line = ""
        pattern_price = re.compile(r'^\$?\d+\.\d{2}$')
    
        for i, line in enumerate(cleaned_lines):
            lower = line.lower()
            if any(term in lower for term in skip_terms):
                continue
    
            # Is this a standalone price line?
            if pattern_price.match(line):
                price = float(line.replace('$', ''))
                # Use previous line as item name
                item_name = re.sub(r'\d{8,}', '', previous_line).strip()
                item_name = re.sub(r'[^A-Za-z0-9\s\-\.,]', '', item_name)
                if item_name and len(item_name) > 3:
                    items.append({
                        'name': item_name,
                        'price': f"${price:.2f}"
                    })
            else:
                previous_line = line  # Save for possible price next line
    
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
