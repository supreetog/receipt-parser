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
    """Extract price from a line using multiple patterns - enhanced version"""
    # More comprehensive price patterns, ordered by specificity
    price_patterns = [
        r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*X',      # Price followed by X (quantity)
        r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*$',      # Price at end of line
        r'\$\s*(\d{1,3}(?:,\d{3})*\.\d{2})',     # Price with dollar sign
        r'(\d{1,3}(?:,\d{3})*\.\d{2})',          # Standard format with commas
        r'(\d+\.\d{2})\s*X',                      # Simple price with X
        r'(\d+\.\d{2})\s*$',                      # Simple price at end
        r'(\d+\.\d{2})',                          # Simple price anywhere
        r'(\d+,\d{2})',                           # European format
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, line)
        if matches:
            price = matches[-1]  # Take the last match
            # Convert comma decimal to dot if needed
            if ',' in price and '.' not in price:
                price = price.replace(',', '.')
            try:
                price_float = float(price)
                # Additional validation: price should be reasonable
                if 0.01 <= price_float <= 999.99:
                    return price_float
            except ValueError:
                continue
    
    return None

def is_summary_line(line, all_items_so_far):
    """
    Enhanced function to detect if a line is a summary line (subtotal, total, tax, etc.)
    Uses context from previously found items to make better decisions
    """
    line_lower = line.lower().strip()
    
    # Basic summary line patterns - more comprehensive
    summary_patterns = [
        # Totals and subtotals
        r'^\s*total\s*$|^\s*subtotal\s*$|^\s*sub\s*total\s*$|^\s*sub-total\s*$',
        r'^\s*grand\s*total\s*$|^\s*final\s*total\s*$|^\s*order\s*total\s*$',
        r'^\s*balance\s*$|^\s*amount\s*due\s*$|^\s*total\s*due\s*$',
        r'^\s*net\s*total\s*$|^\s*gross\s*total\s*$',
        
        # Tax lines
        r'^\s*tax\s*$|^\s*sales\s*tax\s*$|^\s*tax\s*\d*\s*$',
        r'^\s*hst\s*$|^\s*gst\s*$|^\s*pst\s*$|^\s*vat\s*$',
        r'^\s*state\s*tax\s*$|^\s*city\s*tax\s*$|^\s*local\s*tax\s*$',
        
        # Payment related
        r'^\s*change\s*$|^\s*cash\s*$|^\s*card\s*$|^\s*credit\s*$|^\s*debit\s*$',
        r'^\s*payment\s*$|^\s*tender\s*$|^\s*tendered\s*$',
        r'^\s*visa\s*$|^\s*mastercard\s*$|^\s*amex\s*$|^\s*discover\s*$',
        
        # Discounts and fees
        r'^\s*discount\s*$|^\s*coupon\s*$|^\s*savings\s*$|^\s*promo\s*$',
        r'^\s*delivery\s*fee\s*$|^\s*service\s*fee\s*$|^\s*tip\s*$',
        r'^\s*bag\s*fee\s*$|^\s*bottle\s*deposit\s*$|^\s*crv\s*$',
        
        # Transaction details
        r'^\s*receipt\s*$|^\s*transaction\s*$|^\s*order\s*$|^\s*invoice\s*$',
        r'^\s*ref\s*#|^\s*reference\s*$|^\s*confirmation\s*$',
        
        # Common receipt footer items
        r'^\s*thank\s*you\s*$|^\s*have\s*a\s*nice\s*day\s*$|^\s*come\s*again\s*$',
        r'^\s*store\s*$|^\s*cashier\s*$|^\s*register\s*$|^\s*terminal\s*$',
        
        # Lines that contain "total" or "subtotal" anywhere
        r'.*total.*|.*subtotal.*|.*sub\s*total.*',
    ]
    
    # Check basic patterns
    for pattern in summary_patterns:
        if re.search(pattern, line_lower):
            return True
    
    # Additional contextual checks
    price = extract_price_from_line(line)
    if price and all_items_so_far:
        # If this line's price is suspiciously close to sum of previous items
        previous_total = sum(item['Amount'] for item in all_items_so_far)
        
        # Check if this price is close to the sum of previous items (within 20%)
        if abs(price - previous_total) / max(previous_total, 0.01) < 0.2:
            # This might be a subtotal, but let's check the item name
            item_name = line
            # Remove price from item name
            for pattern in [r'\$?\s*\d{1,3}(?:,\d{3})*\.\d{2}\s*X?', r'\$?\s*\d+\.\d{2}\s*X?']:
                item_name = re.sub(pattern, '', item_name)
            item_name = item_name.strip().lower()
            
            # If the remaining text is very short or looks like a summary
            if len(item_name) < 3 or any(word in item_name for word in ['total', 'subtotal', 'tax', 'due', 'balance']):
                return True
    
    return False

def parse_receipt_text(text):
    """Enhanced receipt parsing with better total/subtotal detection"""
    lines = text.strip().split('\n')
    items = []
    
    # Enhanced skip patterns - more specific to avoid false positives
    skip_patterns = [
        # Store and transaction info
        r'walmart|target|costco|kroger|safeway|supercenter|grocery|market',
        r'st#|op#|te#|tr#|tc#|ref|aid|terminal|mgr\.|manager',
        r'transaction|ref|reference|confirmation|invoice|receipt\s*#',
        
        # Date, time, and contact info
        r'^\d{2}/\d{2}/\d{2,4}|^\d{2}:\d{2}:\d{2}',
        r'phone|address|mountain\s+view|ca\s+\d{5}',
        r'^\d{3}-\d{3}-\d{4}|^\d{5}$',
        
        # Promotional and feedback
        r'survey|feedback|delivery|scan|trial|free\s+delivery',
        r'low\s+prices|you\s+can\s+trust|every\s+day',
        r'give\s+us\s+feedback|scan\s+for|get\s+free\s+delivery',
        r'with\s+walmart|supercenter|store\s+hours',
        
        # Transaction codes and technical info
        r'mcard|tend|signature|required|no\s+signature',
        r'appr#|ref\s+#|aid\s+a|approval',
        r'^\s*\d+\s+i\s+\d+\s+appr',
        r'^\s*items\s+sold\s+\d+',
        
        # Lines that are just numbers or codes
        r'^\s*\d+\s*$',
        r'^\s*[A-Z]{2}\s+\d+\s*$',
        r'^\d{12,}$',  # UPC codes
        
        # Address-like patterns
        r'^\s*\d+\s+\w+\s+dr|^\s*\d+\s+\w+\s+st|^\s*\d+\s+\w+\s+ave',
    ]
    
    # Compile patterns for efficiency
    skip_regex = re.compile('|'.join(skip_patterns), re.IGNORECASE)
    
    # Track processed items to handle duplicates and context
    processed_items = []
    
    for i, line in enumerate(lines):
        original_line = line
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        # Skip obvious header/footer lines
        if skip_regex.search(line):
            continue
        
        # ENHANCED: Check if this is a summary line using context
        if is_summary_line(line, processed_items):
            continue
        
        # Skip lines that are mostly numbers (like barcodes) but longer than 8 chars
        if re.match(r'^\d+$', line) and len(line) > 8:
            continue
        
        # Skip lines that look like UPC codes (long numbers)
        if re.match(r'^\d{12,}$', line):
            continue
        
        # Look for price patterns in the line
        price = extract_price_from_line(line)
        if price and price > 0:
            # Extract item name (everything before the price)
            item_name = line
            
            # Remove price from item name using more specific patterns
            price_patterns = [
                r'\$?\s*\d{1,3}(?:,\d{3})*\.\d{2}\s*X?',  # Standard price with optional $ and X
                r'\$?\s*\d+\.\d{2}\s*X?',                 # Simple price with optional $ and X
                r'\$?\s*\d+,\d{2}\s*X?',                  # European format
                r'\d{1,3}(?:,\d{3})*\.\d{2}',             # Just the number
                r'\d+\.\d{2}',                            # Simple number
            ]
            
            for pattern in price_patterns:
                item_name = re.sub(pattern, '', item_name)
            
            # Remove quantity indicators more aggressively
            item_name = re.sub(r'\s+X\s*$', '', item_name, flags=re.IGNORECASE)
            item_name = re.sub(r'\s+x\s*$', '', item_name, flags=re.IGNORECASE)
            
            # Remove UPC codes and long numbers from item name
            item_name = re.sub(r'\b\d{10,}\b', '', item_name)
            
            # Remove common OCR artifacts and clean up
            item_name = re.sub(r'[|\\]', '', item_name)  # Remove pipes and backslashes
            item_name = item_name.strip()
            item_name = re.sub(r'\s+', ' ', item_name)  # Multiple spaces to single
            
            # More gentle cleaning - preserve letters, numbers, and basic punctuation
            item_name = re.sub(r'[^\w\s\-\.]', ' ', item_name)
            item_name = ' '.join(item_name.split())  # Final cleanup
            
            # Skip if item name is too short or looks like a code
            if len(item_name) < 2:
                continue
            
            # Skip if item name is just numbers
            if item_name.isdigit():
                continue
            
            # Skip if item name contains too many digits (likely a code)
            if len(item_name) > 0 and sum(c.isdigit() for c in item_name) / len(item_name) > 0.7:
                continue
            
            # ENHANCED: Additional check for summary-like item names
            item_name_lower = item_name.lower()
            summary_words = ['total', 'subtotal', 'tax', 'due', 'balance', 'change', 'payment', 'cash', 'card']
            if any(word in item_name_lower for word in summary_words):
                continue
            
            # Check if price is reasonable (between $0.01 and $999.99)
            if 0.01 <= price <= 999.99:
                # ENHANCED: Final contextual check - is this price suspiciously similar to running total?
                # Only apply this check if the item name looks like it could be a summary
                if processed_items and len(item_name) < 10:  # Only check short names that might be summaries
                    running_total = sum(item['Amount'] for item in processed_items)
                    # If this price is very close to the running total, it might be a subtotal
                    if abs(price - running_total) < 0.05:  # Within 5 cents
                        continue
                
                # Create item entry
                item_entry = {
                    'Item': item_name,
                    'Amount': price,
                    'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Original Line': original_line.strip()
                }
                
                # Check for exact duplicates (same item name, price, AND original line)
                # This prevents processing the same line twice but allows legitimate multiples
                is_duplicate = False
                for existing_item in processed_items:
                    if existing_item['Original Line'] == original_line.strip():
                        is_duplicate = True
                        break
                
                # Only add if not processing the same line twice
                if not is_duplicate:
                    processed_items.append(item_entry)
                    items.append(item_entry)
    
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
        **Enhanced v2.0 includes:**
        - Better subtotal/total detection
        - Contextual summary line filtering
        - Improved price validation
        - Enhanced duplicate handling
        - Running total validation
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
    st.markdown("*Enhanced v2.0 with better total/subtotal filtering*")

if __name__ == "__main__":
    main()
