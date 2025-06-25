
Quick start
-----------

create the virtual enviorment

```bash
python3 -m venv venv
```

activate this enviorment

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run FastAPI server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
### 🔹 Generate Bulk Data

**POST** `/generate-data`

**Description:**  
This endpoint generates data in bulk and inserts it into the database.

### 🔹 Get Test Performance 

**GET** `/test-performance`

**Description:**  
This endpoint shows the performance difference between the old function and the optimized function.




