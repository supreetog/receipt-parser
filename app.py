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
            return text
        
        # If direct extraction failed, use OCR
        st.info("Direct text extraction failed, using OCR...")
        pdf_file.seek(0)  # Reset file pointer
        images = convert_from_bytes(pdf_file.read(), dpi=300)
        ocr_text = ""
        
        progress_bar = st.progress(0)
        for i, image in enumerate(images):
            st.write(f"Processing page {i+1}/{len(images)}...")
            progress_bar.progress((i + 1) / len(images))
            page_text = pytesseract.image_to_string(image)
            ocr_text += page_text + "\n"
        
        return ocr_text
    except Exception as e:
        st.error(f"Error extracting text from PDF: {str(e)}")
        return ""

def extract_text_from_image(image):
    """Extract text from image using OCR"""
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        with st.spinner("Extracting text from image..."):
            text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        st.error(f"Error extracting text from image: {str(e)}")
        return ""

def parse_receipt_text(text):
    """Parse receipt text to extract items and amounts"""
    lines = text.strip().split('\n')
    items = []
    
    # Common patterns for prices
    price_patterns = [
        r'(\d+\.\d{2})',  # Standard price format (e.g., 12.99)
        r'(\d+,\d{2})',   # European format (e.g., 12,99)
        r'\$(\d+\.\d{2})', # With dollar sign
    ]
    
    # Words to skip (common receipt header/footer words)
    skip_words = {
        'total', 'subtotal', 'tax', 'change', 'cash', 'card', 'credit',
        'debit', 'receipt', 'thank', 'you', 'store', 'date', 'time',
        'cashier', 'transaction', 'balance', 'tender', 'qty', 'quantity',
        'amount', 'due', 'paid', 'discount', 'coupon', 'visa', 'mastercard'
    }
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip lines that are likely headers/footers
        if any(skip in line.lower() for skip in skip_words):
            continue
            
        # Look for price patterns in the line
        for pattern in price_patterns:
            matches = re.findall(pattern, line)
            if matches:
                # Get the price (last match in line is usually the price)
                price = matches[-1]
                # Extract item name (everything before the price)
                item_text = re.sub(pattern, '', line).strip()
                # Clean up item text
                item_text = re.sub(r'[^\w\s]', ' ', item_text)
                item_text = ' '.join(item_text.split())
                
                if item_text and len(item_text) > 1:
                    # Convert comma decimal to dot if needed
                    if ',' in price:
                        price = price.replace(',', '.')
                    try:
                        price_float = float(price)
                        if price_float > 0:  # Only add positive prices
                            items.append({
                                'Item': item_text,
                                'Amount': price_float,
                                'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                    except ValueError:
                        continue
                break
    
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
        
        st.markdown("## 💡 Tips")
        st.markdown("""
        - Use clear, well-lit photos
        - Ensure text is readable
        - Check extracted text before downloading
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
            with st.spinner("Parsing receipt items..."):
                items = parse_receipt_text(extracted_text)
            
            if items:
                df = pd.DataFrame(items)
                
                st.markdown("## 📊 Parsed Items")
                st.success(f"✅ Found {len(items)} items!")
                
                # Display the dataframe
                st.dataframe(df, use_container_width=True)
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Items", len(df))
                with col2:
                    st.metric("Total Amount", f"${df['Amount'].sum():.2f}")
                with col3:
                    st.metric("Average Price", f"${df['Amount'].mean():.2f}")
                
                # Download options
                st.markdown("## 💾 Download Options")
                
                # Generate filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"receipt_items_{timestamp}.csv"
                
                # Create download link
                st.markdown(create_download_link(df, filename), unsafe_allow_html=True)
                
                # Google Sheets format
                st.markdown("### 📋 Copy to Google Sheets")
                st.info("Copy the data below and paste it directly into Google Sheets:")
                
                # Create tab-separated format for Google Sheets
                sheets_data = df.to_csv(sep='\t', index=False)
                st.text_area(
                    "Google Sheets format (tab-separated):",
                    value=sheets_data,
                    height=150,
                    help="Select all and copy, then paste into Google Sheets"
                )
                
            else:
                st.warning("❌ No items found in the receipt")
                st.markdown("### 🔍 Debugging Information")
                st.markdown("Here's what was extracted. You might need to:")
                st.markdown("- Check if the image is clear enough")
                st.markdown("- Verify the text contains recognizable price formats")
                st.markdown("- Try a different image or PDF")
                
                st.text_area("Raw extracted text:", value=extracted_text, height=300)
        else:
            st.error("❌ Could not extract text from the file")
    
    # Footer
    st.markdown("---")
    st.markdown("**Made with ❤️ for easy receipt processing**")

if __name__ == "__main__":
    main()
