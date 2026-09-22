from dotenv import load_dotenv

# Load local secrets before importing the application and constructing Settings.
load_dotenv()

from resume_adjuster.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
