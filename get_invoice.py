import requests
from ghost_session import GhostSession

def send_invoice(base_url, auth_token, email, InvoiceId):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "authentication-token": auth_token,
    }
    url = f"{base_url}/api/ghost/v1/accounts/invoiceretrieve/emailinvoice"
    data = {
        "emailAddress": email,
        "emailBody": "Please find your invoice attached. This is email was sent by n8n.",
        "emailSubject": "Your Invoice",
        "invoiceId": InvoiceId,
        "invoiceNumber": InvoiceId
        }
    response = requests.post(url, headers=headers, json=data)
    return response

if __name__ == "__main__":
    ghost_session = GhostSession()
    ghost_session.login()  # Ensure we're logged in
    token = ghost_session.get_token()
    url = ghost_session.get_base_url()

    response = send_invoice(url, token, "farakh@streetcars.co.uk", 71579)
    print(response.status_code) 
