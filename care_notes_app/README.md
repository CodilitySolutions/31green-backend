python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
 in this root directory care_notes_app 
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
