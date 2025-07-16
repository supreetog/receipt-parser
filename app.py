def parse_receipt_text(text):
    """Enhanced receipt parsing with better item detection and duplicate handling"""
    lines = text.strip().split('\n')
    items = []
    
    # Enhanced skip patterns - more specific to avoid false positives
    skip_patterns = [
        r'^\s*total\s*$|^\s*subtotal\s*$|^\s*tax\d?\s*$|^\s*change\s*$|^\s*cash\s*$|^\s*card\s*$',
        r'^\s*receipt\s*$|^\s*thank\s*you\s*$|^\s*store\s*$|^\s*date\s*$|^\s*time\s*$|^\s*cashier\s*$',
        r'transaction|balance|tender|qty|quantity|amount\s+due|paid',
        r'discount|coupon|visa|mastercard|amex|discover',
        r'walmart|target|costco|kroger|safeway|supercenter',  # Store names
        r'st#|op#|te#|tr#|tc#|ref|aid|terminal|mgr\.|manager',  # Transaction codes
        r'survey|feedback|delivery|scan|trial|free\s+delivery',
        r'phone|address|mountain\s+view|ca\s+\d{5}',
        r'^\d{3}-\d{3}-\d{4}|^\d{5}$',  # Phone numbers, zip codes
        r'mcard|tend|signature|required|no\s+signature',
        r'^\d{2}/\d{2}/\d{2,4}|^\d{2}:\d{2}:\d{2}',  # Dates and times
        r'low\s+prices|you\s+can\s+trust|every\s+day',
        r'^\s*\d+\s*$',  # Lines with just numbers
        r'^\s*[A-Z]{2}\s+\d+\s*$',  # State codes
        r'^\s*give\s+us\s+feedback|^\s*scan\s+for',  # Feedback requests
        r'^\s*items\s+sold\s+\d+',  # Items sold line
        r'^\s*appr#|^\s*ref\s+#|^\s*aid\s+a',  # Transaction references
        r'^\s*\d+\s+i\s+\d+\s+appr',  # Approval codes
        r'^\s*\d+\.\d+\s+total\s+purchase',  # Total purchase line
        r'^\s*get\s+free\s+delivery|^\s*with\s+walmart',  # Promotional text
        r'^\s*\d+\s+showers\s+dr',  # Address lines
    ]
    
    # Compile patterns for efficiency
    skip_regex = re.compile('|'.join(skip_patterns), re.IGNORECASE)
    
    # Track processed items to handle duplicates better
    processed_items = []
    
    for i, line in enumerate(lines):
        original_line = line
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        # Skip obvious header/footer lines
        if skip_regex.search(line):
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
            
            # Check if price is reasonable (between $0.01 and $999.99)
            if 0.01 <= price <= 999.99:
                # Create item entry
                item_entry = {
                    'Item': item_name,
                    'Amount': price,
                    'Date Processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Original Line': original_line.strip()
                }
                
                # Check for exact duplicates (same item name and price)
                is_duplicate = False
                for existing_item in processed_items:
                    if (existing_item['Item'] == item_name and 
                        existing_item['Amount'] == price and
                        existing_item['Original Line'] == original_line.strip()):
                        is_duplicate = True
                        break
                
                # Only add if not an exact duplicate
                if not is_duplicate:
                    processed_items.append(item_entry)
                    items.append(item_entry)
                    
                    # Debug output for items with same price
                    if price == 0.96:
                        print(f"DEBUG: Found $0.96 item: '{item_name}' from line: '{original_line.strip()}'")
    
    # Post-processing: Handle cases where similar items might have been missed
    # Look for patterns that might indicate missed items
    text_lower = text.lower()
    
    # Special handling for receipts that might have missed items
    # Look for specific patterns that indicate multiple similar items
    if "0.96" in text and len([item for item in items if item['Amount'] == 0.96]) < 2:
        # Re-examine lines that contain 0.96 but might have been skipped
        for line in lines:
            if "0.96" in line and "x" in line.lower():
                # This might be a line with quantity and price
                # Try to extract it differently
                print(f"DEBUG: Re-examining potential missed line: '{line}'")
    
    return items

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
