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

# Set page config
st.set_page_config(
    page_title="Receipt Parser",
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

def preprocess_image(image):
    """Preprocess image for better OCR results"""
    # Convert to numpy array
    img_array = np.array(image)
    
    # Convert to grayscale if needed
    if len(img_array.shape) == 3:
        # Convert to grayscale using weighted average
        gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])
        img_array = gray.astype(np.uint8)
    
    # Create PIL image from processed array
    processed_image = Image.fromarray(img_array)
    
    return processed_image

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF using both text extraction and OCR"""
    try:
        # First try to extract text directly
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text.strip():
                text += page_text + "\n"
        
        # If we got good text, return it
        if text.strip() and len(text.strip()) > 50:
            st.success("✅ Direct text extraction successful!")
            return text
        
        # If direct extraction failed, use OCR
        st.info("📷 Direct text extraction failed, using OCR...")
        pdf_file.seek(0)  # Reset file pointer
        images = convert_from_bytes(pdf_file.read(), dpi=300)
        ocr_text = ""
        
        progress_bar = st.progress(0)
        for i, image in enumerate(images):
            st.write(f"Processing page {i+1}/{len(images)}...")
            progress_bar.progress((i + 1) / len(images))
            
            # Preprocess image
            processed_image = preprocess_image(image)
            
            # Use better OCR config
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-: '
            page_text = pytesseract.image_to_string(processed_image, config=custom_config)
            ocr_text += page_text + "\n"
        
        return ocr_text
    except Exception as e:
        st.error(f"Error extracting text from PDF: {str(e)}")
        return ""

def extract_text_from_image(image):
    """Extract text from image using OCR with better preprocessing"""
    try:
        # Preprocess image
        processed_image = preprocess_image(image)
        
        with st.spinner("🔍 Extracting text from image..."):
            # Use custom OCR configuration for better results
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()$%/-: '
            text = pytesseract.image_to_string(processed_image, config=custom_config)
        
        return text
    except Exception as e:
        st.error(f"Error extracting text from image: {str(e)}")
        return ""

def clean_text_line(line):
    """Clean and normalize a text line"""
    # Remove extra whitespace and normalize
    line = ' '.join(line.split())
    # Remove some common OCR artifacts
    line = re.sub(r'[|\\]', '', line)
    # Fix common OCR mistakes
    line = line.replace('5', 'S').replace('0', 'O').replace('1', 'I')
    return line

def extract_price_from_line(line):
    """Extract price from a line using multiple patterns"""
    # More comprehensive price patterns
    price_patterns = [
        r'(\d{1,3}(?:,\d{3})*\.\d{2})',  # Standard format with commas (e.g., 1,234.56)
        r'(\d+\.\d{2})',                  # Standard format (e.g., 12.99)
        r'(\d+,\d{2})',                   # European format (e.g., 12,99)
        r'\$\s*(\d+\.\d{2})',            # With dollar sign and space
        r'(\d+\.\d{2})\s*X',             # Price followed by X (quantity)
        r'(\d+\.\d{2})\s*$',             # Price at end of line
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, line)
        if matches:
            price = matches[-1]  # Take the last match (usually the actual price)
            # Convert comma decimal to dot if needed
            if ',' in price and '.' not in price:
                price = price.replace(',', '.')
            try:
                return float(price)
            except ValueError:
                continue
    
    return None

def parse_receipt_text(text):
    """Enhanced receipt parsing with better item detection"""
    lines = text.strip().split('\n')
    items = []
    
    # Enhanced skip patterns - more specific to avoid false positives
    skip_patterns = [
        r'^(sub)?total\s*\d+\.\d{2}',  # Total lines
        r'^tax\d?\s*\d+\.\d{2}',      # Tax lines
        r'^change\s+due',              # Change due
        r'^cash|^card|^credit|^debit', # Payment methods
        r'receipt|thank\s+you',        # Receipt footer
        r'store\s+\d+|manager',        # Store info
        r'st#\s+\d+|op#\s+\d+|te#\s+\d+|tr#\s+\d+|tc#\s+\d+',  # Transaction codes
        r'ref\s+#|aid\s+[A-Z0-9]+|terminal\s+#',  # Reference codes
        r'survey|feedback|delivery|scan.*trial',   # Marketing text
        r'^\d{3}-\d{3}-\d{4}',         # Phone numbers
        r'^\d{5}\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),                 # Zip codes alone
        r'mcard\s+tend|signature\s+required',  # Payment info
        r'^\d{2}/\d{2}/\d{2,4}',       # Dates
        r'^\d{1,2}:\d{2}:\d{2}',       # Times
        r'low\s+prices.*trust',        # Walmart slogan
        r'^\s*\d+\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),                # Lines with just numbers
        r'^\s*[A-Z]{2}\s+\d+\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),     # State codes
        r'^\s*\d{10,}\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),            # Long product codes alone
        r'get\s+free\s+delivery',      # Marketing
        r'walmart\s*\+?

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),             # Store name alone
        r'supercenter\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),            # Store type alone
        r'mountain\s+view\s+ca',       # Address
        r'^\s*\d+\s+[A-Z]+\s+[A-Z]+\s+\d+\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),  # Address-like patterns
    ]
    
    # Compile patterns for efficiency
    skip_regex = re.compile('|'.join(skip_patterns), re.IGNORECASE)
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        # Skip obvious header/footer lines
        if skip_regex.search(line):
            continue
        
        # Skip lines that are mostly numbers (like barcodes) but allow short codes
        if re.match(r'^\d+

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(), line) and len(line) > 12:
            continue
        
        # Look for price in the line
        price = extract_price_from_line(line)
        if price and price > 0:
            # Extract item name (everything before the price)
            item_name = line
            
            # Remove price from item name - be more specific
            price_patterns = [
                r'\s*\d{1,3}(?:,\d{3})*\.\d{2}\s*X?\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),  # Price with optional X at end
                r'\s*\d+\.\d{2}\s*X?\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),                 # Standard price with optional X
                r'\s*\d+,\d{2}\s*X?\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),                  # European format
                r'\s*\$\s*\d+\.\d{2}\s*X?\s*

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main(),           # With dollar sign
            ]
            
            for pattern in price_patterns:
                item_name = re.sub(pattern, '', item_name)
            
            # Remove product codes (long numbers) but keep shorter ones
            item_name = re.sub(r'\b\d{12,}\b', '', item_name)
            
            # Clean up item name more carefully
            item_name = item_name.strip()
            
            # Remove extra spaces but preserve structure
            item_name = re.sub(r'\s+', ' ', item_name)
            
            # Only remove truly problematic characters, keep letters and numbers
            item_name = re.sub(r'[^\w\s&+\-/]', ' ', item_name)
            item_name = ' '.join(item_name.split())
            
            # More lenient validation for item names
            if len(item_name) >= 2 and not item_name.isdigit():
                # Allow more items through - don't filter by digit ratio for short names
                if len(item_name) <= 10 or sum(c.isdigit() for c in item_name) / len(item_name) < 0.7:
                    # Check if price is reasonable (between $0.01 and $999.99)
                    if 0.01 <= price <= 999.99:
                        items.append({
                            'Item': item_name,
                            'Amount': price,
                            'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'Original Line': line  # Keep for debugging
                        })
    
    return items

def create_download_link(df, filename):
    """Create a download link for the dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🧾 Receipt Parser</h1>', unsafe_allow_html=True)
    
    # Sidebar for instructions
    with st.sidebar:
        st.markdown("## 📋 Instructions")
        st.markdown("""
        1. **Upload** your receipt (PDF or image)
        2. **Review** the extracted text
        3. **Download** the parsed data as CSV
        4. **Import** to Google Sheets or Excel
        """)
        
        st.markdown("## 🔧 Supported Formats")
        st.markdown("""
        - **Images**: JPG, PNG, GIF, BMP, TIFF
        - **PDFs**: Single or multi-page
        """)
        
        st.markdown("## 💡 Tips for Better Results")
        st.markdown("""
        - Use good lighting when taking photos
        - Keep the receipt flat and straight
        - Ensure text is clearly visible
        - Avoid shadows and reflections
        - Higher resolution images work better
        """)
        
        st.markdown("## ⚙️ OCR Settings")
        st.markdown("""
        This version includes:
        - Image preprocessing for better OCR
        - Enhanced text cleaning
        - Better price pattern recognition
        - Improved item name extraction
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("## 📤 Upload Receipt")
        uploaded_file = st.file_uploader(
            "Choose a receipt file",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'],
            help="Upload a PDF or image file of your receipt"
        )
    
    if uploaded_file is not None:
        # Display file info
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Process the file
        file_type = uploaded_file.name.lower().split('.')[-1]
        
        with col2:
            st.markdown("## 👀 Preview")
            
            if file_type == 'pdf':
                st.markdown("📄 PDF uploaded - processing...")
                extracted_text = extract_text_from_pdf(uploaded_file)
                
                # Show PDF preview if possible
                try:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read(), dpi=150)
                    if images:
                        st.image(images[0], caption="First page preview", use_column_width=True)
                except Exception as e:
                    st.warning("Could not create PDF preview")
                    
            elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
                st.markdown("🖼️ Image uploaded - processing...")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded image", use_column_width=True)
                extracted_text = extract_text_from_image(image)
            
            else:
                st.error("❌ Unsupported file type")
                return
        
        # Show extracted text
        if extracted_text:
            st.markdown("## 📝 Extracted Text")
            with st.expander("Click to view extracted text", expanded=False):
                st.text_area(
                    "Extracted text:",
                    value=extracted_text,
                    height=200,
                    help="This is the raw text extracted from your receipt"
                )
            
            # Parse items
            with st.spinner("🔍 Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                # Create dataframe and remove debug column for display
                df = pd.DataFrame(items)
                display_df = df.drop('Original Line', axis=1)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(display_df, use_container_width=True)
                
                # Show debugging info
                with st.expander("🔍 Debug Information", expanded=False):
                    st.markdown("**Items with original lines:**")
                    for item in items:
                        st.markdown(f"**{item['Item']}** (${item['Amount']:.2f})")
                        st.markdown(f"*Original line:* `{item['Original Line']}`")
                        st.markdown("---")
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(display_df))
                with col2:
                    st.metric("Total Amount", f"${display_df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${display_df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(display_df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = display_df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("**Possible reasons:**")
                st.markdown("- The image quality might be too low")
                st.markdown("- The receipt format is not recognized")
                st.markdown("- The text extraction didn't work properly")
                st.markdown("- Try taking a clearer photo with better lighting")
                
                st.markdown("**Raw extracted text:**")
                st.text_area("", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("- Make sure the image is clear and readable")
            st.markdown("- Try a different image format")
            st.markdown("- Ensure the receipt is well-lit in the photo")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")
    st.markdown("*Enhanced with better OCR and parsing algorithms*")

if __name__ == "__main__":
    main()
