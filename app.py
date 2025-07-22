import streamlit as st
import pytesseract
from PIL import Image
import re
from datetime import datetime
import pandas as pd
import io
import tempfile
import os

# Try to import PyMuPDF, fall back gracefully if not available
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    st.warning("⚠️ PyMuPDF not found. PDF support disabled. Install with: pip install PyMuPDF")

# Configure page
st.set_page_config(
    page_title="Receipt Parser",
    page_icon="🧾",
    layout="wide"
)

class ReceiptParser:
    def __init__(self):
        self.common_stores = [
            'walmart', 'target', 'costco', 'safeway', 'kroger', 'cvs', 'walgreens',
            'home depot', 'lowes', 'best buy', 'amazon', 'whole foods', 'trader joe',
            'starbucks', 'mcdonalds', 'subway', 'chipotle'
        ]
    
    def extract_text_from_image(self, image):
        """Extract text from image using OCR"""
        try:
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Use pytesseract to extract text
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            st.error(f"Error extracting text: {str(e)}")
            return ""
    
    def extract_text_from_pdf(self, pdf_bytes):
        """Extract text from PDF file"""
        if not PDF_SUPPORT:
            st.error("PDF support not available. Please install PyMuPDF: pip install PyMuPDF")
            return "", None
            
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_file_path = tmp_file.name
            
            try:
                # Open PDF with PyMuPDF
                doc = fitz.open(tmp_file_path)
                full_text = ""
                images = []
                
                # Process each page
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    
                    # First try to extract text directly (for searchable PDFs)
                    page_text = page.get_text()
                    if page_text.strip():
                        full_text += page_text + "\n"
                    else:
                        # If no text found, convert page to image and OCR
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        images.append(img)
                        
                        # OCR the image
                        ocr_text = self.extract_text_from_image(img)
                        full_text += ocr_text + "\n"
                
                doc.close()
                
                return full_text, images if images else None
            
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            return "", None
    
    def parse_receipt(self, text):
        """Parse receipt text and extract structured data"""
        lines = text.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        
        receipt_data = {
            'store_name': '',
            'date': '',
            'total_amount': '',
            'items': [],
            'raw_text': text
        }
        
        # Extract store name (usually in first few lines)
        receipt_data['store_name'] = self.extract_store_name(lines[:5])
        
        # Extract date
        receipt_data['date'] = self.extract_date(text)
        
        # Extract items first (most important)
        receipt_data['items'] = self.extract_items(lines)
        
        # Extract total amount (less critical now)
        receipt_data['total_amount'] = self.extract_total(lines)
        
        return receipt_data
    
    def extract_store_name(self, first_lines):
        """Extract store name from first few lines"""
        for line in first_lines:
            line_lower = line.lower()
            for store in self.common_stores:
                if store in line_lower:
                    return line.title()
        
        # If no common store found, return first non-empty line
        for line in first_lines:
            if len(line) > 2 and not line.isdigit():
                return line.title()
        
        return "Unknown Store"
    
    def extract_date(self, text):
        """Extract date from receipt text"""
        # Common date patterns
        date_patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
            r'\b(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\b',
            r'\b(\w{3,9}\s+\d{1,2},?\s+\d{2,4})\b'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    # Try to parse the date
                    date_str = matches[0]
                    # Simple validation - if it contains numbers, return it
                    if any(char.isdigit() for char in date_str):
                        return date_str
                except:
                    continue
        
        return datetime.now().strftime("%m/%d/%Y")
    
    def extract_total(self, lines):
        """Extract total amount from receipt"""
        total_patterns = [
            r'total[:\s]*\$?(\d+\.?\d*)',
            r'amount[:\s]*\$?(\d+\.?\d*)',
            r'balance[:\s]*\$?(\d+\.?\d*)',
            r'\$(\d+\.\d{2})\s*$'
        ]
        
        # Look for total in reverse order (usually at bottom)
        for line in reversed(lines):
            line_lower = line.lower()
            for pattern in total_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    amount = match.group(1)
                    try:
                        # Validate it's a reasonable amount
                        float_amount = float(amount)
                        if 0.01 <= float_amount <= 10000:  # Reasonable range
                            return f"${amount}"
                    except ValueError:
                        continue
        
        return "Not found"
    
    def extract_items(self, lines):
        """Extract individual items from receipt with improved parsing"""
        items = []
        
        # Enhanced patterns for item lines
        item_patterns = [
            # Pattern 1: Item name followed by price at end of line
            r'^(.+?)\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    if receipt_data['total_amount'] and receipt_data['total_amount'] != "Not found":
                        st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        
                        # Calculate total from items if official total not found
                        calculated_total = sum(float(item['price'].replace('
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            r'^(.+?)\s+(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            # Pattern 2: Item with quantity and price
            r'^(.+?)\s+\d+\s*@\s*\$?(\d+\.\d{2})\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            r'^(.+?)\s+\d+\s*x\s*\$?(\d+\.\d{2})\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            # Pattern 3: Item with loose price format
            r'^(.+?)\s+\$?(\d+\.?\d*)

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            # Pattern 4: Item code followed by description and price
            r'^\d+\s+(.+?)\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            # Pattern 5: Barcode/UPC followed by item and price
            r'^\d{8,13}\s+(.+?)\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
        ]
        
        # Expanded skip terms
        skip_terms = [
            'total', 'subtotal', 'sub total', 'sub-total', 'tax', 'sales tax', 'state tax',
            'change', 'cash', 'credit', 'debit', 'visa', 'mastercard', 'amex', 'discover',
            'receipt', 'thank', 'visit', 'store', 'phone', 'address', 'cashier', 'register',
            'balance', 'tendered', 'payment', 'card', 'approval', 'auth', 'reference',
            'transaction', 'merchant', 'terminal', 'batch', 'sequence', 'invoice',
            'customer', 'member', 'savings', 'discount total', 'coupon', 'promotion',
            'tender', 'amount due', 'new balance', 'previous balance', 'minimum payment',
            'date', 'time', 'store #', 'reg #', 'tran #', 'card #', 'account',
            'www.', 'http', '.com', '.net', '.org', 'survey', 'save', 'earn',
            'points', 'rewards', 'club', 'membership', 'expires', 'valid'
        ]
        
        # Additional filters for non-item lines
        def is_likely_item_line(line):
            line_lower = line.lower().strip()
            
            # Skip if line is too short or too long
            if len(line.strip()) < 3 or len(line.strip()) > 100:
                return False
            
            # Skip lines that are mostly numbers (like barcodes, transaction IDs)
            if len(re.sub(r'[\d\s\-\.]', '', line)) < 3:
                return False
            
            # Skip lines with skip terms
            for term in skip_terms:
                if term in line_lower:
                    return False
            
            # Skip lines that look like headers or footers
            if line.isupper() and len(line.split()) <= 3:
                return False
            
            # Skip lines with common receipt formatting
            if any(pattern in line_lower for pattern in ['***', '---', '===', 'store hours', 'return policy']):
                return False
            
            # Skip lines that are just dates or times
            if re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), line.strip()):
                return False
            if re.match(r'^\d{1,2}:\d{2}(:\d{2})?\s*(am|pm)?

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), line_lower.strip()):
                return False
            
            return True
        
        # Process each line
        for line in lines:
            if not is_likely_item_line(line):
                continue
            
            line = line.strip()
            matched = False
            
            # Try each pattern
            for pattern in item_patterns:
                match = re.search(pattern, line)
                if match:
                    if len(match.groups()) == 2:
                        # Standard item and price
                        item_name = match.group(1).strip()
                        price_str = match.group(2).strip()
                    elif len(match.groups()) == 3:
                        # Item with quantity (use total price)
                        item_name = match.group(1).strip()
                        price_str = match.group(3).strip()  # Use total price, not unit price
                    else:
                        continue
                    
                    # Clean up item name
                    item_name = re.sub(r'^\d+\s*', '', item_name)  # Remove leading item codes
                    item_name = re.sub(r'\s+', ' ', item_name)      # Normalize whitespace
                    
                    # Skip if item name is too short or generic
                    if len(item_name.strip()) < 2:
                        continue
                    
                    # Skip if item name looks like a code or ID
                    if re.match(r'^\d+[A-Z]*\d*

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), item_name.strip()):
                        continue
                    
                    # Validate and format price
                    try:
                        price_float = float(price_str)
                        if 0.01 <= price_float <= 2000:  # Reasonable item price range
                            # Format price consistently
                            formatted_price = f"${price_float:.2f}"
                            
                            # Check for duplicates
                            duplicate = False
                            for existing_item in items:
                                if (existing_item['name'].lower() == item_name.lower() and 
                                    existing_item['price'] == formatted_price):
                                    duplicate = True
                                    break
                            
                            if not duplicate:
                                items.append({
                                    'name': item_name,
                                    'price': formatted_price
                                })
                                matched = True
                                break
                    except ValueError:
                        continue
            
            # If no pattern matched, try a more liberal approach for obvious items
            if not matched and '

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main() in line:
                # Look for price patterns anywhere in the line
                price_matches = re.findall(r'\$?(\d+\.\d{2})', line)
                if price_matches:
                    # Take the last price found (usually the item total)
                    price_str = price_matches[-1]
                    
                    try:
                        price_float = float(price_str)
                        if 0.01 <= price_float <= 2000:
                            # Extract item name (everything before the last price)
                            item_name = re.sub(r'\$?\d+\.\d{2}.*

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), '', line).strip()
                            item_name = re.sub(r'^\d+\s*', '', item_name)  # Remove item codes
                            item_name = re.sub(r'\s+', ' ', item_name)
                            
                            if len(item_name) >= 3 and not any(term in item_name.lower() for term in skip_terms[:10]):
                                formatted_price = f"${price_float:.2f}"
                                
                                # Check for duplicates
                                duplicate = False
                                for existing_item in items:
                                    if (existing_item['name'].lower() == item_name.lower() and 
                                        existing_item['price'] == formatted_price):
                                        duplicate = True
                                        break
                                
                                if not duplicate:
                                    items.append({
                                        'name': item_name,
                                        'price': formatted_price
                                    })
        
        # Sort items by price (descending) to put expensive items first
        items.sort(key=lambda x: float(x['price'].replace('

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), '')), reverse=True)
        
        return items[:50]  # Increased limit to 50 items

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), '')) for item in receipt_data['items'])
                        st.write(f"**Items Count:** {len(receipt_data['items'])}")
                        st.write(f"**Calculated Total:** ${calculated_total:.2f}")
                        
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Use calculated total if official total not found
                        display_total = receipt_data['total_amount'] if receipt_data['total_amount'] != "Not found" else f"${calculated_total:.2f}"
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [display_total],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Top Items': ['; '.join([item['name'][:25] + ('...' if len(item['name']) > 25 else '') 
                                                   for item in receipt_data['items'][:4]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{display_total}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:40] + ('...' if len(item['name']) > 40 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            r'^(.+?)\s+(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            # Pattern 2: Item with quantity and price
            r'^(.+?)\s+\d+\s*@\s*\$?(\d+\.\d{2})\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            r'^(.+?)\s+\d+\s*x\s*\$?(\d+\.\d{2})\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            # Pattern 3: Item with loose price format
            r'^(.+?)\s+\$?(\d+\.?\d*)

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            # Pattern 4: Item code followed by description and price
            r'^\d+\s+(.+?)\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
            # Pattern 5: Barcode/UPC followed by item and price
            r'^\d{8,13}\s+(.+?)\s+\$?(\d+\.\d{2})

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(),
        ]
        
        # Expanded skip terms
        skip_terms = [
            'total', 'subtotal', 'sub total', 'sub-total', 'tax', 'sales tax', 'state tax',
            'change', 'cash', 'credit', 'debit', 'visa', 'mastercard', 'amex', 'discover',
            'receipt', 'thank', 'visit', 'store', 'phone', 'address', 'cashier', 'register',
            'balance', 'tendered', 'payment', 'card', 'approval', 'auth', 'reference',
            'transaction', 'merchant', 'terminal', 'batch', 'sequence', 'invoice',
            'customer', 'member', 'savings', 'discount total', 'coupon', 'promotion',
            'tender', 'amount due', 'new balance', 'previous balance', 'minimum payment',
            'date', 'time', 'store #', 'reg #', 'tran #', 'card #', 'account',
            'www.', 'http', '.com', '.net', '.org', 'survey', 'save', 'earn',
            'points', 'rewards', 'club', 'membership', 'expires', 'valid'
        ]
        
        # Additional filters for non-item lines
        def is_likely_item_line(line):
            line_lower = line.lower().strip()
            
            # Skip if line is too short or too long
            if len(line.strip()) < 3 or len(line.strip()) > 100:
                return False
            
            # Skip lines that are mostly numbers (like barcodes, transaction IDs)
            if len(re.sub(r'[\d\s\-\.]', '', line)) < 3:
                return False
            
            # Skip lines with skip terms
            for term in skip_terms:
                if term in line_lower:
                    return False
            
            # Skip lines that look like headers or footers
            if line.isupper() and len(line.split()) <= 3:
                return False
            
            # Skip lines with common receipt formatting
            if any(pattern in line_lower for pattern in ['***', '---', '===', 'store hours', 'return policy']):
                return False
            
            # Skip lines that are just dates or times
            if re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), line.strip()):
                return False
            if re.match(r'^\d{1,2}:\d{2}(:\d{2})?\s*(am|pm)?

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), line_lower.strip()):
                return False
            
            return True
        
        # Process each line
        for line in lines:
            if not is_likely_item_line(line):
                continue
            
            line = line.strip()
            matched = False
            
            # Try each pattern
            for pattern in item_patterns:
                match = re.search(pattern, line)
                if match:
                    if len(match.groups()) == 2:
                        # Standard item and price
                        item_name = match.group(1).strip()
                        price_str = match.group(2).strip()
                    elif len(match.groups()) == 3:
                        # Item with quantity (use total price)
                        item_name = match.group(1).strip()
                        price_str = match.group(3).strip()  # Use total price, not unit price
                    else:
                        continue
                    
                    # Clean up item name
                    item_name = re.sub(r'^\d+\s*', '', item_name)  # Remove leading item codes
                    item_name = re.sub(r'\s+', ' ', item_name)      # Normalize whitespace
                    
                    # Skip if item name is too short or generic
                    if len(item_name.strip()) < 2:
                        continue
                    
                    # Skip if item name looks like a code or ID
                    if re.match(r'^\d+[A-Z]*\d*

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), item_name.strip()):
                        continue
                    
                    # Validate and format price
                    try:
                        price_float = float(price_str)
                        if 0.01 <= price_float <= 2000:  # Reasonable item price range
                            # Format price consistently
                            formatted_price = f"${price_float:.2f}"
                            
                            # Check for duplicates
                            duplicate = False
                            for existing_item in items:
                                if (existing_item['name'].lower() == item_name.lower() and 
                                    existing_item['price'] == formatted_price):
                                    duplicate = True
                                    break
                            
                            if not duplicate:
                                items.append({
                                    'name': item_name,
                                    'price': formatted_price
                                })
                                matched = True
                                break
                    except ValueError:
                        continue
            
            # If no pattern matched, try a more liberal approach for obvious items
            if not matched and '

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main() in line:
                # Look for price patterns anywhere in the line
                price_matches = re.findall(r'\$?(\d+\.\d{2})', line)
                if price_matches:
                    # Take the last price found (usually the item total)
                    price_str = price_matches[-1]
                    
                    try:
                        price_float = float(price_str)
                        if 0.01 <= price_float <= 2000:
                            # Extract item name (everything before the last price)
                            item_name = re.sub(r'\$?\d+\.\d{2}.*

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), '', line).strip()
                            item_name = re.sub(r'^\d+\s*', '', item_name)  # Remove item codes
                            item_name = re.sub(r'\s+', ' ', item_name)
                            
                            if len(item_name) >= 3 and not any(term in item_name.lower() for term in skip_terms[:10]):
                                formatted_price = f"${price_float:.2f}"
                                
                                # Check for duplicates
                                duplicate = False
                                for existing_item in items:
                                    if (existing_item['name'].lower() == item_name.lower() and 
                                        existing_item['price'] == formatted_price):
                                        duplicate = True
                                        break
                                
                                if not duplicate:
                                    items.append({
                                        'name': item_name,
                                        'price': formatted_price
                                    })
        
        # Sort items by price (descending) to put expensive items first
        items.sort(key=lambda x: float(x['price'].replace('

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main(), '')), reverse=True)
        
        return items[:50]  # Increased limit to 50 items

def main():
    st.title("🧾 Receipt Parser")
    st.markdown("Upload a receipt image to extract and parse the data for easy copying to Google Sheets")
    
    parser = ReceiptParser()
    
    # File uploader
    supported_types = ['png', 'jpg', 'jpeg']
    if PDF_SUPPORT:
        supported_types.append('pdf')
    
    uploaded_file = st.file_uploader(
        "Choose a receipt image" + (" or PDF" if PDF_SUPPORT else ""), 
        type=supported_types,
        help="Upload a clear image of your receipt" + (" or a PDF file" if PDF_SUPPORT else "")
    )
    
    if uploaded_file is not None:
        # Check file type
        file_type = uploaded_file.type
        is_pdf = file_type == "application/pdf"
        
        # Display the file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if is_pdf:
                st.subheader("PDF Receipt")
                st.write(f"📄 **File:** {uploaded_file.name}")
                st.write(f"📊 **Size:** {len(uploaded_file.getvalue())} bytes")
            else:
                st.subheader("Original Receipt")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Parsed Data")
            
            # Process the file
            with st.spinner("Processing receipt..."):
                text = ""
                pdf_images = None
                
                if is_pdf:
                    # Process PDF
                    pdf_bytes = uploaded_file.getvalue()
                    text, pdf_images = parser.extract_text_from_pdf(pdf_bytes)
                    
                    # Show PDF pages as images if OCR was used
                    if pdf_images:
                        st.write("**PDF Pages (converted to images for OCR):**")
                        for i, img in enumerate(pdf_images):
                            with st.expander(f"Page {i+1}"):
                                st.image(img, use_column_width=True)
                else:
                    # Process image
                    text = parser.extract_text_from_image(image)
                
                if text:
                    receipt_data = parser.parse_receipt(text)
                    
                    # Display parsed information
                    st.write("**Store:**", receipt_data['store_name'])
                    st.write("**Date:**", receipt_data['date'])
                    st.write("**Total:**", receipt_data['total_amount'])
                    
                    # Create DataFrame for items
                    if receipt_data['items']:
                        st.subheader("Items Found")
                        df_items = pd.DataFrame(receipt_data['items'])
                        st.dataframe(df_items, use_container_width=True)
                        
                        # Create summary DataFrame for Google Sheets
                        st.subheader("📋 Copy to Google Sheets")
                        
                        # Summary row format
                        summary_data = {
                            'Date': [receipt_data['date']],
                            'Store': [receipt_data['store_name']],
                            'Total': [receipt_data['total_amount']],
                            'Items': [f"{len(receipt_data['items'])} items"],
                            'Description': ['; '.join([item['name'][:30] + ('...' if len(item['name']) > 30 else '') 
                                                     for item in receipt_data['items'][:3]])]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True)
                        
                        # Copyable text format
                        st.subheader("📄 Tab-Separated Format")
                        st.markdown("*Copy this text and paste directly into Google Sheets:*")
                        
                        # Create tab-separated values
                        tab_separated = f"{receipt_data['date']}\t{receipt_data['store_name']}\t{receipt_data['total_amount']}\t{len(receipt_data['items'])} items\t" + \
                                      '; '.join([item['name'][:50] + ('...' if len(item['name']) > 50 else '') 
                                               for item in receipt_data['items'][:5]])
                        
                        st.text_area(
                            "Copy this text:",
                            value=tab_separated,
                            height=100,
                            help="Select all and copy (Ctrl+A, Ctrl+C), then paste in Google Sheets"
                        )
                        
                        # Detailed items export
                        if st.checkbox("Show detailed items for export"):
                            st.subheader("Detailed Items (Tab-Separated)")
                            detailed_items = []
                            for item in receipt_data['items']:
                                detailed_items.append(f"{receipt_data['date']}\t{receipt_data['store_name']}\t{item['name']}\t{item['price']}")
                            
                            detailed_text = '\n'.join(detailed_items)
                            st.text_area(
                                "Detailed items (one per row):",
                                value=detailed_text,
                                height=200,
                                help="Each line represents one item with date, store, item name, and price"
                            )
                    
                    else:
                        st.warning("No items were detected in the receipt. Try uploading a clearer image or PDF.")
                    
                    # Raw text for debugging
                    if st.checkbox("Show raw extracted text"):
                        st.subheader("Raw Extracted Text")
                        st.text_area("Extracted Text:", value=text, height=200)
                else:
                    st.error("Could not extract text from the file. Please try a clearer image or a different PDF.")
    
    # Instructions
    st.sidebar.markdown("""
    ## 📝 Instructions
    
    1. **Upload** a clear image or PDF of your receipt
    2. **Review** the parsed data for accuracy
    3. **Copy** the tab-separated text
    4. **Paste** directly into Google Sheets
    
    ## 💡 Tips for Best Results
    
    **For Images:**
    - Use good lighting when photographing receipts
    - Ensure the receipt is flat and not crumpled
    - Make sure all text is clearly visible
    - Crop the image to focus on the receipt
    
    **For PDFs:**
    - Digital receipts work best (e.g., email receipts)
    - Scanned PDFs are also supported
    - Multi-page PDFs are handled automatically
    
    ## 📊 Google Sheets Setup
    
    Create columns for:
    - Date
    - Store
    - Total
    - Items Count
    - Description
    
    Then paste the copied text into a new row.
    
    ## 🔧 Supported Formats
    
    - **Images:** PNG, JPG, JPEG
    - **PDFs:** Digital and scanned receipts
    """)

if __name__ == "__main__":
    main()
