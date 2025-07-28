import streamlit as st
import tempfile
import os

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
        """Extract items from Walmart receipt text"""
        lines = text.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        items = []
        
        # Skip terms for non-item lines
        skip_terms = [
            'subtotal', 'total', 'tax', 'change', 'cash', 'credit', 'debit', 
            'visa', 'mastercard', 'thank you', 'receipt', 'store'
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
            should_skip = False
            for term in skip_terms:
                if term in line_lower:
                    should_skip = True
                    break
            
            if should_skip:
                continue
            
            # Skip lines that are just numbers
            if clean_line.isdigit():
                continue
                
            # Skip lines with just special characters
            special_only = True
            for char in clean_line:
                if char not in ' *-=':
                    special_only = False
                    break
            
            if special_only:
                continue
            
            # Look for lines with dollar signs and decimal points (prices)
            if '$' in clean_line and '.' in clean_line:
                # Find the last dollar sign
                dollar_pos = clean_line.rfind('$')
                if dollar_pos >= 0:
                    # Get everything after the dollar sign
                    after_dollar = clean_line[dollar_pos + 1:].strip()
                    
                    # Split by spaces to get the first part (should be price)
                    price_parts = after_dollar.split()
                    if price_parts:
                        potential_price = price_parts[0]
                        
                        # Check if it looks like a price (has decimal point)
                        if '.' in potential_price:
                            try:
                                price = float(potential_price)
                                if 0.01 <= price <= 500:
                                    # Extract item name (everything before the last $)
                                    item_name = clean_line[:dollar_pos].strip()
                                    
                                    # Clean up item name - remove long sequences of numbers
                                    words = item_name.split()
                                    cleaned_words = []
                                    for word in words:
                                        # Skip words that are all digits and longer than 8 chars (UPC codes)
                                        if not (word.isdigit() and len(word) > 8):
                                            cleaned_words.append(word)
                                    
                                    item_name = ' '.join(cleaned_words)
                                    item_name = item_name.replace('*', '').strip()
                                    
                                    # Skip if item name is too short
                                    if len(item_name) > 2 and not item_name.isdigit():
                                        # Skip if item name contains skip terms
                                        name_has_skip_term = False
                                        for term in skip_terms:
                                            if term in item_name.lower():
                                                name_has_skip_term = True
                                                break
                                        
                                        if not name_has_skip_term:
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
                    import pandas as pd
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
