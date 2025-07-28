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
        
        # Extract total amount
        receipt_data['total_amount'] = self.extract_total(lines)
        
        # Extract items
        receipt_data['items'] = self.extract_items(lines)
        
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

        for line in reversed(lines):  # Start from bottom
            line_lower = line.lower()
            for pattern in total_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    amount = match.group(1)
                    try:
                        float_amount = float(amount)
                        if 0.01 <= float_amount <= 10000:
                            return f"${float_amount:.2f}"
                    except ValueError:
                        continue

        return "Not found"
    
    def extract_items(self, lines):
        """Extract individual items from receipt - optimized for Walmart receipts"""
        items = []
        
        # More targeted skip terms - only clear non-item lines
        skip_terms = [
            'subtotal', 'tax due', 'total', 'change due', 'cash tend', 'credit card',
            'debit card', 'visa', 'mastercard', 'discover', 'receipt', 'thank you',
            'store manager', 'phone', 'address', 'cashier', 'terminal', 'transaction',
            'balance due', 'tender', 'payment method', 'auth code', 'ref #',
            'items sold:', 'tc#', 'te#', 'st#', 'op#', '* * * * *', '====',
            'walmart', 'supercenter', 'neighborhood market'
        ]
        
        # Skip common header patterns
        skip_patterns = [
            r'^\*+\s*$',  # Lines with just asterisks
            r'^=+\s*$',   # Lines with just equals signs
            r'^-+\s*$',   # Lines with just dashes
            r'^\d{1,2}/\d{1,2}/\d{2,4}',  # Date lines
            r'^\d+:\d+\s*(AM|PM)',  # Time lines
            r'^STORE\s*#?\d+',  # Store number lines
            r'^(ST|TE|TC|OP)#?\s*\d+',  # Transaction codes
        ]
        
        # Walmart-specific item patterns
        item_patterns = [
            # Standard format: ITEM NAME 001234567890 $12.34 N
            r'^([A-Za-z][^0-9]*?)\s+(\d{10,15})\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*$',
            # Format with quantity: ITEM NAME QTY @ $X.XX $Total N
            r'^([A-Za-z][^@]*?)\s+\d+\s*@\s*\$?[\d.]+\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*$',
            # Simple format: ITEM NAME $XX.XX
            r'^([A-Za-z][^$]*?)\s+\$(\d+\.\d{2})\s*[A-Z]*\s*$',
            # Format with UPC in middle: ITEM 001234567890 NAME $XX.XX
            r'^([A-Za-z].*?)\s+(\d{10,15})\s+([^$]*?)\s+\$(\d+\.\d{2})\s*[A-Z]*\s*$',
            # Generic item line with price at end
            r'^([A-Za-z][^$]*?)\s+(\d+\.\d{2})\s*[A-ZTFN]*\s*$',
        ]
        
        for line in lines:
            clean_line = line.strip()
            
            # Skip very short lines or lines with only special characters
            if len(clean_line) < 3 or clean_line.replace(' ', '').replace('*', '').replace('=', '').replace('-', '') == '':
                continue
            
            line_lower = clean_line.lower()
            
            # Skip lines that match our skip terms
            if any(term in line_lower for term in skip_terms):
                continue
                
            # Skip lines that match skip patterns
            if any(re.match(pattern, clean_line, re.IGNORECASE) for pattern in skip_patterns):
                continue
            
            # Skip lines that are mostly numbers (likely UPC codes or transaction IDs)
            if re.match(r'^\d+\s*
        
        # If we didn't find many items, try a more lenient approach
        if len(items) < 5:
            items.extend(self.extract_items_lenient(lines, set()))
        
        return items[:100]  # Return up to 100 items
    
    def extract_items_lenient(self, lines, seen_items):
        """More lenient item extraction for cases where strict patterns fail"""
        items = []
        
        # Very simple pattern: anything that ends with a price
        simple_pattern = r'^(.+?)\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*


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
    main(), clean_line):
                continue
                
            # Skip lines with only special characters and spaces
            if re.match(r'^[\s\*\-=]+
        
        # If we didn't find many items, try a more lenient approach
        if len(items) < 5:
            items.extend(self.extract_items_lenient(lines, seen_items))
        
        return items[:100]  # Return up to 100 items
    
    def extract_items_lenient(self, lines, seen_items):
        """More lenient item extraction for cases where strict patterns fail"""
        items = []
        
        # Very simple pattern: anything that ends with a price
        simple_pattern = r'^(.+?)\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*$'
        
        for line in lines:
            clean_line = line.strip()
            
            if len(clean_line) < 5:
                continue
                
            # Skip obvious non-item lines
            if any(skip in clean_line.lower() for skip in ['total', 'tax', 'change', 'tender', 'cash']):
                continue
                
            match = re.match(simple_pattern, clean_line)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(2).strip()
                
                # Basic cleaning
                item_name = re.sub(r'[*=\-]+', '', item_name).strip()
                
                if len(item_name) > 2 and not item_name.isdigit():
                    try:
                        price = float(price_str)
                        if 0.01 <= price <= 500:
                            item_key = (item_name.lower(), price)
                            if item_key not in seen_items:
                                items.append({
                                    'name': item_name,
                                    'price': f"${price:.2f}"
                                })
                                seen_items.add(item_key)
                    except ValueError:
                        continue
        
        return items


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
    main(), clean_line):
                continue
            
            # Try to match against item patterns
            for pattern in item_patterns:
                match = re.match(pattern, clean_line)
                if match:
                    groups = match.groups()
                    
                    # Extract item name and price based on pattern
                    if len(groups) == 3 and groups[1].isdigit() and len(groups[1]) > 10:
                        # Pattern with UPC: name, upc, price
                        item_name = groups[0].strip()
                        price_str = groups[2].strip()
                    elif len(groups) == 4:
                        # Pattern with UPC in middle: combine first and third groups for name
                        item_name = f"{groups[0]} {groups[2]}".strip()
                        price_str = groups[3].strip()
                    elif len(groups) >= 2:
                        # Simple patterns: name, price
                        item_name = groups[0].strip()
                        price_str = groups[-1].strip()
                    else:
                        continue
                    
                    # Clean up item name
                    item_name = re.sub(r'\s+', ' ', item_name)  # Normalize whitespace
                    item_name = item_name.replace('*', '').strip()  # Remove asterisks
                    
                    # Skip if item name is too short or looks like a code
                    if len(item_name) < 2 or item_name.isdigit():
                        continue
                    
                    # Skip if item name contains skip terms
                    if any(term in item_name.lower() for term in skip_terms):
                        continue
                    
                    try:
                        price = float(price_str)
                        if 0.01 <= price <= 1000:  # Reasonable price range
                            # Add all items, including duplicates (for multiple quantities)
                            items.append({
                                'name': item_name,
                                'price': f"${price:.2f}"
                            })
                            break  # Found a match, don't try other patterns
                    except (ValueError, IndexError):
                        continue
        
        # If we didn't find many items, try a more lenient approach
        if len(items) < 5:
            items.extend(self.extract_items_lenient(lines, seen_items))
        
        return items[:100]  # Return up to 100 items
    
    def extract_items_lenient(self, lines, seen_items):
        """More lenient item extraction for cases where strict patterns fail"""
        items = []
        
        # Very simple pattern: anything that ends with a price
        simple_pattern = r'^(.+?)\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*$'
        
        for line in lines:
            clean_line = line.strip()
            
            if len(clean_line) < 5:
                continue
                
            # Skip obvious non-item lines
            if any(skip in clean_line.lower() for skip in ['total', 'tax', 'change', 'tender', 'cash']):
                continue
                
            match = re.match(simple_pattern, clean_line)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(2).strip()
                
                # Basic cleaning
                item_name = re.sub(r'[*=\-]+', '', item_name).strip()
                
                if len(item_name) > 2 and not item_name.isdigit():
                    try:
                        price = float(price_str)
                        if 0.01 <= price <= 500:
                            item_key = (item_name.lower(), price)
                            if item_key not in seen_items:
                                items.append({
                                    'name': item_name,
                                    'price': f"${price:.2f}"
                                })
                                seen_items.add(item_key)
                    except ValueError:
                        continue
        
        return items


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
        
        for line in lines:
            clean_line = line.strip()
            
            if len(clean_line) < 5:
                continue
                
            # Skip obvious non-item lines
            if any(skip in clean_line.lower() for skip in ['total', 'tax', 'change', 'tender', 'cash']):
                continue
                
            match = re.match(simple_pattern, clean_line)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(2).strip()
                
                # Basic cleaning
                item_name = re.sub(r'[*=\-]+', '', item_name).strip()
                
                if len(item_name) > 2 and not item_name.isdigit():
                    try:
                        price = float(price_str)
                        if 0.01 <= price <= 500:
                            # Add all items, including duplicates
                            items.append({
                                'name': item_name,
                                'price': f"${price:.2f}"
                            })
                    except ValueError:
                        continue
        
        return items


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
    main(), clean_line):
                continue
                
            # Skip lines with only special characters and spaces
            if re.match(r'^[\s\*\-=]+
        
        # If we didn't find many items, try a more lenient approach
        if len(items) < 5:
            items.extend(self.extract_items_lenient(lines, seen_items))
        
        return items[:100]  # Return up to 100 items
    
    def extract_items_lenient(self, lines, seen_items):
        """More lenient item extraction for cases where strict patterns fail"""
        items = []
        
        # Very simple pattern: anything that ends with a price
        simple_pattern = r'^(.+?)\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*$'
        
        for line in lines:
            clean_line = line.strip()
            
            if len(clean_line) < 5:
                continue
                
            # Skip obvious non-item lines
            if any(skip in clean_line.lower() for skip in ['total', 'tax', 'change', 'tender', 'cash']):
                continue
                
            match = re.match(simple_pattern, clean_line)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(2).strip()
                
                # Basic cleaning
                item_name = re.sub(r'[*=\-]+', '', item_name).strip()
                
                if len(item_name) > 2 and not item_name.isdigit():
                    try:
                        price = float(price_str)
                        if 0.01 <= price <= 500:
                            item_key = (item_name.lower(), price)
                            if item_key not in seen_items:
                                items.append({
                                    'name': item_name,
                                    'price': f"${price:.2f}"
                                })
                                seen_items.add(item_key)
                    except ValueError:
                        continue
        
        return items


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
    main(), clean_line):
                continue
            
            # Try to match against item patterns
            for pattern in item_patterns:
                match = re.match(pattern, clean_line)
                if match:
                    groups = match.groups()
                    
                    # Extract item name and price based on pattern
                    if len(groups) == 3 and groups[1].isdigit() and len(groups[1]) > 10:
                        # Pattern with UPC: name, upc, price
                        item_name = groups[0].strip()
                        price_str = groups[2].strip()
                    elif len(groups) == 4:
                        # Pattern with UPC in middle: combine first and third groups for name
                        item_name = f"{groups[0]} {groups[2]}".strip()
                        price_str = groups[3].strip()
                    elif len(groups) >= 2:
                        # Simple patterns: name, price
                        item_name = groups[0].strip()
                        price_str = groups[-1].strip()
                    else:
                        continue
                    
                    # Clean up item name
                    item_name = re.sub(r'\s+', ' ', item_name)  # Normalize whitespace
                    item_name = item_name.replace('*', '').strip()  # Remove asterisks
                    
                    # Skip if item name is too short or looks like a code
                    if len(item_name) < 2 or item_name.isdigit():
                        continue
                    
                    # Skip if item name contains skip terms
                    if any(term in item_name.lower() for term in skip_terms):
                        continue
                    
                    try:
                        price = float(price_str)
                        if 0.01 <= price <= 1000:  # Reasonable price range
                            # Add all items, including duplicates (for multiple quantities)
                            items.append({
                                'name': item_name,
                                'price': f"${price:.2f}"
                            })
                            break  # Found a match, don't try other patterns
                    except (ValueError, IndexError):
                        continue
        
        # If we didn't find many items, try a more lenient approach
        if len(items) < 5:
            items.extend(self.extract_items_lenient(lines, seen_items))
        
        return items[:100]  # Return up to 100 items
    
    def extract_items_lenient(self, lines, seen_items):
        """More lenient item extraction for cases where strict patterns fail"""
        items = []
        
        # Very simple pattern: anything that ends with a price
        simple_pattern = r'^(.+?)\s+\$?(\d+\.\d{2})\s*[A-Z]*\s*$'
        
        for line in lines:
            clean_line = line.strip()
            
            if len(clean_line) < 5:
                continue
                
            # Skip obvious non-item lines
            if any(skip in clean_line.lower() for skip in ['total', 'tax', 'change', 'tender', 'cash']):
                continue
                
            match = re.match(simple_pattern, clean_line)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(2).strip()
                
                # Basic cleaning
                item_name = re.sub(r'[*=\-]+', '', item_name).strip()
                
                if len(item_name) > 2 and not item_name.isdigit():
                    try:
                        price = float(price_str)
                        if 0.01 <= price <= 500:
                            item_key = (item_name.lower(), price)
                            if item_key not in seen_items:
                                items.append({
                                    'name': item_name,
                                    'price': f"${price:.2f}"
                                })
                                seen_items.add(item_key)
                    except ValueError:
                        continue
        
        return items


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
