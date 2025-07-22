import streamlit as st
import pandas as pd
from PIL import Image
import pytesseract
import io
import re
import PyPDF2
from pdf2image import convert_from_bytes
import base64
from datetime import datetime
import numpy as np
from collections import defaultdict

# Set page config
st.set_page_config(
    page_title="Receipt Parser v3.0",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .upload-section {
        border: 2px dashed #1f77b4;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class ReceiptParser:
    """Enhanced receipt parser with improved accuracy and efficiency"""
    
    def __init__(self):
        # Compiled regex patterns for efficiency
        self.price_patterns = [
            re.compile(r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*[xX]\s*\d*\s*$'),  # Price with quantity
            re.compile(r'\$\s*(\d{1,3}(?:,\d{3})*\.\d{2})(?:\s*[xX])?'),   # $ prefixed price
            re.compile(r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*$'),                # Price at line end
            re.compile(r'(\d+\.\d{2})\s*[xX]\s*\d*\s*$'),                  # Simple price with qty
            re.compile(r'(\d+\.\d{2})\s*$'),                               # Simple price at end
            re.compile(r'(\d+\.\d{2})(?=\s|$)'),                          # Simple price with boundary
        ]
        
        # Skip patterns - using separate compiled patterns for efficiency
        skip_pattern_list = [
            # Store headers and transaction info
            r'^(?:walmart|target|costco|kroger|safeway|supercenter|grocery|market)\b',
            r'\b(?:st#|op#|te#|tr#|tc#|ref|aid|terminal|mgr\.?|manager)\b',
            r'\b(?:transaction|reference|confirmation|invoice|receipt)\s*#?\b',
            r'\b(?:store|location|address|phone)\b',
            
            # Dates, times, and technical codes
            r'^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}',  # Dates
            r'^\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?',  # Times
            r'^\d{3}-?\d{3}-?\d{4}
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),  # Phone numbers
            r'^\d{5,}
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),  # Long number codes (UPC, etc.)
            r'^\w{2}\s+\d+\s+\w+
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),  # State + number + code patterns
            
            # Promotional and footer text
            r'\b(?:survey|feedback|scan|trial|delivery|hours|thank\s*you)\b',
            r'(?:give\s+us\s+feedback|scan\s+for|get\s+free|with\s+walmart)',
            r'(?:low\s+prices|you\s+can\s+trust|every\s*day|supercenter)',
            
            # Payment and approval codes
            r'\b(?:mcard|tend|signature|required|appr#?|approval)\b',
            r'^\s*\d+\s+[iI]\s+\d+\s+appr',
            r'^\s*items\s+sold\s+\d+',
        ]
        self.skip_patterns = re.compile('|'.join(skip_pattern_list), re.IGNORECASE)
        
        # Summary line patterns
        summary_pattern_list = [
            # Totals and subtotals - more specific patterns
            r'^\s*(?:grand\s*)?(?:sub\s*)?total\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            r'^\s*(?:order|final|net|gross)\s+total\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            r'^\s*(?:balance|amount|total)\s*due\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            
            # Tax patterns
            r'^\s*(?:sales\s*)?tax(?:\s*\d*)?\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            r'^\s*(?:hst|gst|pst|vat|state|city|local)\s*(?:tax)?\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            
            # Payment and tender
            r'^\s*(?:change|cash|card|credit|debit|payment|tender)\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            r'^\s*(?:visa|mastercard|amex|discover)\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            
            # Fees and discounts
            r'^\s*(?:discount|coupon|savings|promo)\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            r'^\s*(?:delivery|service|bag)\s*fee\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
            r'^\s*(?:tip|gratuity|bottle\s*deposit|crv)\s*
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main(),
        ]
        self.summary_patterns = re.compile('|'.join(summary_pattern_list), re.IGNORECASE)
    
    def preprocess_image(self, image):
        """Optimized image preprocessing"""
        img_array = np.array(image)
        
        # Convert to grayscale using standard weights
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            img_array = gray.astype(np.uint8)
        
        return Image.fromarray(img_array)
    
    def extract_text_from_pdf(self, pdf_file):
        """Enhanced PDF text extraction with fallback to OCR"""
        try:
            # Try direct text extraction first
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n".join(page.extract_text() for page in pdf_reader.pages)
            
            if len(text.strip()) > 50 and not text.isspace():
                st.success("✅ Direct text extraction successful!")
                return text
            
            # Fallback to OCR with progress tracking
            st.info("📷 Using OCR for better text extraction...")
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read(), dpi=300)
            
            ocr_text = []
            progress_bar = st.progress(0)
            
            for i, image in enumerate(images):
                progress_bar.progress((i + 1) / len(images))
                processed_image = self.preprocess_image(image)
                
                # Optimized OCR config for receipts
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                page_text = pytesseract.image_to_string(processed_image, config=config)
                ocr_text.append(page_text)
            
            return "\n".join(ocr_text)
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return ""
    
    def extract_text_from_image(self, image):
        """Optimized image OCR"""
        try:
            processed_image = self.preprocess_image(image)
            
            with st.spinner("🔍 Extracting text from image..."):
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-:&@ '
                text = pytesseract.image_to_string(processed_image, config=config)
            
            return text
        except Exception as e:
            st.error(f"Image OCR error: {str(e)}")
            return ""
    
    def extract_price(self, line):
        """Enhanced price extraction with validation"""
        for pattern in self.price_patterns:
            match = pattern.search(line)
            if match:
                price_str = match.group(1)
                try:
                    price = float(price_str.replace(',', ''))
                    # Reasonable price validation
                    if 0.01 <= price <= 999.99:
                        return price
                except ValueError:
                    continue
        return None
    
    def clean_item_name(self, line, price_str):
        """Clean item name by removing price and artifacts"""
        # Remove the price pattern from the line
        cleaned = line
        for pattern in self.price_patterns:
            cleaned = pattern.sub('', cleaned)
        
        # Remove common artifacts and normalize
        cleaned = re.sub(r'[|\\]+', ' ', cleaned)  # Remove OCR artifacts
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)  # Remove UPC codes
        cleaned = re.sub(r'\s*[xX]\s*\d*\s*$', '', cleaned)  # Remove quantity markers
        cleaned = re.sub(r'[^\w\s\-\.&]', ' ', cleaned)  # Keep only valid chars
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned.strip()
    
    def is_likely_item_line(self, line, price, item_name):
        """Enhanced item line detection"""
        # Skip if line matches skip patterns
        if self.skip_patterns.search(line):
            return False
        
        # Skip summary lines
        if self.summary_patterns.search(line):
            return False
        
        # Item name quality checks
        if len(item_name) < 2 or item_name.isdigit():
            return False
        
        # Skip if too many digits (likely a code)
        if len(item_name) > 3:
            digit_ratio = sum(c.isdigit() for c in item_name) / len(item_name)
            if digit_ratio > 0.6:
                return False
        
        # Check for summary keywords in item name
        item_lower = item_name.lower()
        summary_keywords = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash']
        if any(keyword in item_lower for keyword in summary_keywords):
            return False
        
        return True
    
    def parse_receipt_text(self, text):
        """Enhanced receipt parsing with improved accuracy"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items = []
        processed_lines = set()  # Track exact lines to prevent duplicates
        
        # First pass: collect all potential items with metadata
        candidate_items = []
        
        for i, line in enumerate(lines):
            if line in processed_lines or len(line) < 3:
                continue
            
            price = self.extract_price(line)
            if not price:
                continue
            
            item_name = self.clean_item_name(line, str(price))
            
            if not self.is_likely_item_line(line, price, item_name):
                continue
            
            candidate_items.append({
                'line_index': i,
                'original_line': line,
                'item_name': item_name,
                'price': price,
                'context_lines': lines[max(0, i-2):i+3]  # Context for validation
            })
        
        # Second pass: validate candidates and remove false positives
        running_total = 0
        
        for candidate in candidate_items:
            # Skip if this looks like a running total
            if abs(candidate['price'] - running_total) < 0.05 and len(candidate['item_name']) < 8:
                continue
            
            # Check if item name is too generic/summary-like when compared to price
            if candidate['price'] > 50 and len(candidate['item_name']) < 4:
                # High price with very short name - might be a subtotal
                continue
            
            # Final validation: check context for summary indicators
            context_text = ' '.join(candidate['context_lines']).lower()
            if 'subtotal' in context_text or 'total' in context_text:
                # Be more conservative if we're near total-like text
                if len(candidate['item_name']) < 6:
                    continue
            
            # Add to final items
            item = {
                'Item': candidate['item_name'],
                'Amount': candidate['price'],
                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Original Line': candidate['original_line']
            }
            
            items.append(item)
            processed_lines.add(candidate['original_line'])
            running_total += candidate['price']
        
        return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'

def main():
    # Initialize parser
    parser = ReceiptParser()
    
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser v3.0</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted items
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("- **Images**: JPG, PNG, GIF, BMP, TIFF\n- **PDFs**: Single or multi-page")
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting and avoid shadows
        - Keep receipts flat and straight
        - Higher resolution images work better
        - Ensure text is clearly visible
        """)
        
        st.markdown("## ⚙️ v3.0 Improvements")
        st.markdown("""
        **Enhanced accuracy through:**
        - Compiled regex patterns for speed
        - Two-pass item validation
        - Contextual analysis
        - Better price pattern detection
        - Improved item name cleaning
        - Running total validation
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                extracted_text = parser.extract_text_from_pdf(uploaded_file)
                # Show PDF preview
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except:
                    st.info("PDF uploaded successfully")
            else:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = parser.extract_text_from_image(image)
        
        if extracted_text:
            # Show extracted text in expander
            st.markdown("## 📝 Extracted Text")
            with st.expander("View extracted text", expanded=False):
                st.text_area("Raw text:", value=extracted_text, height=200, disabled=True)
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parser.parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display results
                st.dataframe(display_df, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(items))
                with col2:
                    st.metric("Total Amount", f"${sum(item['Amount'] for item in items):.2f}")
                with col3:
                    st.metric("Average Price", f"${np.mean([item['Amount'] for item in items]):.2f}")
                
                # Debug information
                with st.expander("🔍 Debug Information", expanded=False):
                    for item in items:
                        st.markdown(f"**{item['Item']}** - ${item['Amount']:.2f}")
                        st.code(f"Original: {item['Original Line']}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Google Sheets Format")
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area("Copy and paste into Google Sheets:", value=sheets_data, height=150)
            else:
                st.warning("❌ No items found")
                st.markdown("### Troubleshooting")
                st.markdown("- Check image quality and lighting\n- Ensure text is clearly visible\n- Try a different file format")
                with st.expander("View raw text for debugging"):
                    st.text_area("", value=extracted_text, height=300, disabled=True)
        else:
            st.error("❌ Could not extract text from file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Receipt Parser v3.0** - Enhanced accuracy and performance")

if __name__ == "__main__":
    main()
