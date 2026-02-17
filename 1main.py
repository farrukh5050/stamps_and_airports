from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from ghost_session import GhostSession
from get_invoice import send_invoice

app = FastAPI()

class SendInvoiceRequest(BaseModel):
    email: str
    invoice_id: int

class RunRequest(BaseModel):
    message: str

@app.post("/send-invoice")
def send_invoice_endpoint(req: SendInvoiceRequest):
    try:
        ghost_session = GhostSession()
        ghost_session.login()

        token = ghost_session.get_token()
        base_url = ghost_session.get_base_url()

        response = send_invoice(base_url, token, req.email, req.invoice_id)

        return {
            "status": "ok" if response.status_code == 200 else "failed",
            "status_code": response.status_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message": "Hello"}

@app.post("/run")
def run_code(req: RunRequest):
    return {
        "status": "ok",
        "received": req.message,
        "result": f"Python received: {req.message}"
    }
