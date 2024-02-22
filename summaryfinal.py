import io
import re
from fastapi import FastAPI, UploadFile, File, HTTPException
import google.generativeai as genai
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

app = FastAPI()

# Configure generative model with API key
GOOGLE_API_KEY = "AIzaSyBFmJax_4lJoUYgcMarFzEtIQBRklGVdCU"  # Replace this with your actual API key
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def convert_pdf_to_text(file):
    rsrcmgr = PDFResourceManager()
    retstr = io.StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)

    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos = set()

    initial_date = None
    expiry_date = None
    service_provider = None
    client = None

    for page in PDFPage.get_pages(file, pagenos, maxpages=maxpages, password=password, caching=caching, check_extractable=True):
        interpreter.process_page(page)
        text = retstr.getvalue()

        if not initial_date:
            initial_date = extract_date(text)

        if not expiry_date:
            expiry_date = extract_date(text)

        match_service_provider = re.search(r'Service Provider: (.+)', text)
        if match_service_provider:
            service_provider = match_service_provider.group(1)

        match_client = re.search(r'Client: (.+)', text)
        if match_client:
            client = match_client.group(1)

    device.close()
    text = retstr.getvalue()
    retstr.close()

    return {
        "text": text,
        "initial_date": initial_date,
        "expiry_date": expiry_date,
        "service_provider": service_provider,
        "client": client
    }

def extract_date(text):
    date_regex = r'\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{1,2} [a-zA-Z]{3,9} \d{4})\b'
    match = re.search(date_regex, text)
    if match:
        return match.group()
    return None

@app.post("/generate-contract-summary/")
async def generate_contract_summary(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_data = convert_pdf_to_text(io.BytesIO(await file.read()))
    pdf_text = pdf_data["text"]

    # Define input text for generating content
    input_text = """
    Summarize the key details of this contract including the following:
    - Dates: initial_date, expiry_date
    - Service Provider
    - Client
    - Payment terms
    - Term of the contract
    - Termination conditions
    - Confidentiality provisions
    - Intellectual property rights
    - Governing law

    Provide the information in the following format:
    initial_date: <initial_date>
    expiry_date: <expiry_date>
    service_provider: <service_provider>
    client: <client>
    """

    # Generate content using both PDF text and input text
    response = model.generate_content([input_text, pdf_text])
    generated_text = response.text

    # Extract initial_date, expiry_date, service_provider, and client
    initial_date = pdf_data["initial_date"]
    expiry_date = pdf_data["expiry_date"]
    service_provider = pdf_data["service_provider"]
    client = pdf_data["client"]

    # Parse generated text to get initial_date, expiry_date, service_provider, and client if not found in PDF
    if not initial_date:
        match = re.search(r'initial_date: (.+)', generated_text)
        if match:
            initial_date = match.group(1)
    if not expiry_date:
        match = re.search(r'expiry_date: (.+)', generated_text)
        if match:
            expiry_date = match.group(1)
    if not service_provider:
        match = re.search(r'service_provider: (.+)', generated_text)
        if match:
            service_provider = match.group(1)
    if not client:
        match = re.search(r'client: (.+)', generated_text)
        if match:
            client = match.group(1)

    return {
        "generated_text": generated_text,
        "initial_date": initial_date,
        "expiry_date": expiry_date,
        "service_provider": service_provider,
        "client": client
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
