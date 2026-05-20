"""
=============================================================
SMART RECEIPT PROCESSING MODEL
EasyOCR + NLP Pipeline
=============================================================
"""

import easyocr
import cv2
import re
import dateparser
import pickle
import json


# -------------------------------------------------------
# Initialize EasyOCR
# -------------------------------------------------------

reader = easyocr.Reader(['en'], gpu=False)


# -------------------------------------------------------
# CATEGORY KEYWORDS
# -------------------------------------------------------

CATEGORY_KEYWORDS = {

    "Food": [
        "restaurant", "resto", "cafe", "cafeteria", "hotel",
        "pizza", "burger", "coffee", "tea", "chai",
        "food", "meal", "canteen", "mess", "lounge",
        "dine", "dining", "takeaway", "parcel", "delivery",
        "snacks", "fast food", "eatery", "bakery",
        "bread", "milk", "butter", "cheese", "curd", "paneer",
        "egg", "rice", "roti", "dal", "sabzi",
        "biscuit", "chips", "namkeen", "chocolate", "sweet",
        "juice", "cold drink", "soft drink", "water bottle",
        "ice cream", "dessert", "biryani", "thali", "tiffin", "dhaba",
        "breakfast", "lunch", "dinner",
        "zomato", "swiggy", "dominos", "kfc", "mcdonald",
        "subway", "starbucks", "haldiram", "bikanervala"
    ],

    "Transport": [
        "uber", "ola", "taxi", "cab", "auto", "rickshaw",
        "bike taxi", "rapido",
        "fuel", "petrol", "diesel", "cng",
        "metro", "bus", "railway", "train", "ticket",
        "travel", "trip", "ride", "fare",
        "parking", "toll", "fastag",
        "irctc", "redbus",
        "flight", "airlines", "airport",
        "boarding pass",
        "petrol pump", "indian oil", "hp", "bharat petroleum"
    ],

    "Entertainment": [
        "cinema", "movie", "film", "theatre",
        "netflix", "spotify", "hotstar", "prime", "zee5",
        "subscription", "ott", "streaming",
        "concert", "show", "event", "music", "gaming",
        "game", "arcade", "fun zone",
        "playstation", "xbox",
        "pvr", "inox", "bookmyshow",
        "ticket", "entry", "pass",
        "sports", "match", "stadium"
    ],

    "Shopping": [
        "amazon", "flipkart", "meesho", "myntra", "ajio", "nykaa",
        "mall", "store", "shop", "retail", "purchase", "buy",
        "supermarket", "mart", "dmart", "reliance", "big bazaar",
        "spencer", "vishal", "kirana", "general store",
        "grocery", "vegetable", "fruits", "onion", "potato", "tomato",
        "soap", "shampoo", "toothpaste", "toothbrush",
        "detergent", "surf", "rin", "tide",
        "cleaner", "phenyl", "harpic",
        "clothing", "fashion", "shirt", "pant", "jeans",
        "electronics", "mobile", "charger", "headphones",
        "utensils", "kitchen items",
        "bag", "shoes", "slippers",
        "stationery", "pen", "notebook", "book",
        "cash memo", "invoice", "receipt",
        "qty", "quantity", "rate", "price", "total",
        "discount", "offer", "sale"
    ],

    "Utilities": [
        "electricity", "power", "water", "internet", "wifi",
        "recharge", "mobile recharge", "bill", "bill payment",
        "postpaid", "prepaid",
        "broadband", "fiber", "connection",
        "gas", "lpg", "cylinder",
        "electric bill", "water bill",
        "dth", "tv recharge",
        "airtel", "jio", "bsnl", "vi", "vodafone",
        "service charge", "account number",
        "consumer number", "due amount"
    ],

    "Health": [
        "pharmacy", "medical", "medicine", "med", "medicl",
        "hospital", "clinic", "doctor", "dr",
        "diagnostic", "lab", "test", "scan", "xray", "mri",
        "blood test", "report",
        "apollo", "medplus", "1mg", "pharmeasy",
        "healthcare", "treatment", "consultation",
        "prescription", "tablet", "capsule", "syrup",
        "injection", "ointment", "bandage",
        "patient", "fee", "consultation fee"
    ]

}


# -------------------------------------------------------
# IMAGE PREPROCESSING
# -------------------------------------------------------

def preprocess_image(image_path):

    img = cv2.imread(image_path)

    if img is None:
        raise FileNotFoundError(f"Image '{image_path}' not found.")

    # Resize image for better OCR accuracy
    img = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Reduce noise
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    return denoised


# -------------------------------------------------------
# OCR TEXT EXTRACTION
# -------------------------------------------------------

def extract_text(image_path):

    img = preprocess_image(image_path)

    results = reader.readtext(img)

    text = " ".join([res[1] for res in results])

    return text


# -------------------------------------------------------
# CLEAN TEXT
# -------------------------------------------------------

def clean_text(text):

    # Remove long numbers like phone numbers
    text = re.sub(r'\b\d{10,}\b', '', text)

    return text


# -------------------------------------------------------
# AMOUNT EXTRACTION
# -------------------------------------------------------

def extract_amount(text):

    total_patterns = [
        r'(?:Net Amount|Total|Amount Payable)[^\d]*(\d+(?:\.\d{1,2})?)'
    ]

    for pattern in total_patterns:

        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return float(match.group(1))

    pattern = r'₹?\s?(\d{1,5}(?:\.\d{1,2})?)'

    matches = re.findall(pattern, text)

    amounts = []

    for m in matches:

        try:
            value = float(m)

            if 10 <= value <= 20000:
                amounts.append(value)

        except:
            continue

    if amounts:
        return max(amounts)

    return None


# -------------------------------------------------------
# DATE EXTRACTION
# -------------------------------------------------------

def extract_date(text):

    date_patterns = [

        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b\d{1,2}\s+\w+\s+\d{4}\b',
        r'\b\w+\s+\d{1,2},?\s+\d{4}\b'

    ]

    for pattern in date_patterns:

        match = re.search(pattern, text, re.IGNORECASE)

        if match:

            parsed = dateparser.parse(match.group())

            if parsed:
                return parsed.strftime("%Y-%m-%d")

    return None


# -------------------------------------------------------
# CATEGORY EXTRACTION
# -------------------------------------------------------

def extract_category(text):

    text_lower = text.lower()

    scores = {}

    for category, keywords in CATEGORY_KEYWORDS.items():

        count = sum(1 for kw in keywords if kw in text_lower)

        if count > 0:
            scores[category] = count

    if scores:
        return max(scores, key=scores.get)

    return "Others"


# -------------------------------------------------------
# MAIN PIPELINE
# -------------------------------------------------------

def process_receipt(image_path):

    text = extract_text(image_path)

    # Handle OCR failure
    if not text.strip():

        return {
            "category": "Others",
            "amount": None,
            "date": None,
            "raw_text": "",
            "error": "OCR failed"
        }

    text = clean_text(text)

    amount = extract_amount(text)

    date = extract_date(text)

    category = extract_category(text)

    result = {

        "category": category,
        "amount": amount,
        "date": date,
        "raw_text": text

    }

    return result


# -------------------------------------------------------
# TEST RUN
# -------------------------------------------------------

if __name__ == "__main__":

    IMAGE_PATH = "/Receipt Analysis Model/receipt 2.png"

    result = process_receipt(IMAGE_PATH)

    print("\n===== EXTRACTION RESULT =====")
    print(json.dumps(result, indent=4))
    print("=============================\n")

    save_model()