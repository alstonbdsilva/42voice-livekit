"""
Billing and Payment Router.
Handles Stripe checkout session creation, Stripe webhook processing, and local checkout simulation.
"""

import logging
import stripe
import json
import uuid
import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from api import database
from config import get_settings
from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user

router = APIRouter()
logger = logging.getLogger("voice-agent.api.billing")

# --- Request Models ---

class BuyPlanRequest(BaseModel):
    planId: str

class MockSuccessRequest(BaseModel):
    planId: str
    buyerType: str
    buyerId: str
    price: float
    reference: Optional[str] = None


# Helper to generate unique invoice numbers
def generate_invoice_number():
    return f"INV-{uuid.uuid4().hex[:8].upper()}"


# Process standard invoice, payment, credit updates, and reseller commissions
async def process_successful_payment(
    plan_id: str,
    buyer_type: str,
    buyer_id: str,
    wholesale_price: float,
    client_price: float,
    reference: str
):
    settings = get_settings()

    async def trans_cb(conn):
        # 1. Fetch Plan details
        plan_rows = await conn.fetch("SELECT name, minutes FROM plans WHERE id = $1", uuid.UUID(plan_id))
        if not plan_rows:
            raise ValueError("Plan not found")
        plan = plan_rows[0]
        plan_name = plan["name"]
        minutes = plan["minutes"]

        invoice_num = generate_invoice_number()
        now = datetime.datetime.now(datetime.timezone.utc)
        due_date = now + datetime.timedelta(days=30)

        if buyer_type == "client":
            client_uuid = uuid.UUID(buyer_id)
            # Fetch client details
            client_rows = await conn.fetch("SELECT name, reseller_id FROM clients WHERE id = $1", client_uuid)
            if not client_rows:
                raise ValueError("Client profile not found")
            client = client_rows[0]
            client_name = client["name"]
            reseller_id = client["reseller_id"]

            # Line items description
            line_items = [{
                "description": f"Prepaid Minutes Recharge: {plan_name} ({minutes} mins)",
                "quantity": 1,
                "rate": float(client_price),
                "amount": float(client_price)
            }]

            # Create client invoice
            inv_rows = await conn.fetch(
                """INSERT INTO invoices (number, client_id, amount, tax, total, paid_amount, status, due_date, issue_date, line_items)
                   VALUES ($1, $2, $3, 0.00, $3, $3, 'paid', $4, $5, $6)
                   RETURNING id""",
                invoice_num, client_uuid, client_price, due_date, now, json.dumps(line_items)
            )
            invoice_id = inv_rows[0]["id"]

            # Log payment
            await conn.execute(
                """INSERT INTO payments (invoice_id, client_id, amount, status, method, reference, paid_at, created_at)
                   VALUES ($1, $2, $3, 'succeeded', 'card', $4, $5, $5)""",
                invoice_id, client_uuid, client_price, reference, now
            )

            # Update client minutes balance
            await conn.execute(
                "UPDATE clients SET minutes_balance = minutes_balance + $1 WHERE id = $2",
                minutes, client_uuid
            )

            # Process reseller commission
            if reseller_id:
                commission_amt = max(client_price - wholesale_price, 0.00)
                if commission_amt > 0:
                    # Calculate percentage
                    commission_pct = round((commission_amt / client_price) * 100, 2) if client_price > 0 else 0.00
                    await conn.execute(
                        """INSERT INTO commissions (reseller_id, client_id, invoice_id, amount, commission_pct, status, date)
                           VALUES ($1, $2, $3, $4, $5, 'payable', $6)""",
                        reseller_id, client_uuid, invoice_id, commission_amt, commission_pct, now
                    )

            logger.info(f"Client {client_name} ({buyer_id}) successfully purchased plan {plan_name}. Minutes +{minutes}.")

        elif buyer_type == "reseller":
            reseller_uuid = uuid.UUID(buyer_id)
            # Fetch reseller details
            reseller_rows = await conn.fetch("SELECT name FROM resellers WHERE id = $1", reseller_uuid)
            if not reseller_rows:
                raise ValueError("Reseller profile not found")
            reseller = reseller_rows[0]
            reseller_name = reseller["name"]

            line_items = [{
                "description": f"Wholesale Minutes Recharge: {plan_name} ({minutes} mins)",
                "quantity": 1,
                "rate": float(wholesale_price),
                "amount": float(wholesale_price)
            }]

            # Create reseller invoice
            inv_rows = await conn.fetch(
                """INSERT INTO invoices (number, reseller_id, amount, tax, total, paid_amount, status, due_date, issue_date, line_items)
                   VALUES ($1, $2, $3, 0.00, $3, $3, 'paid', $4, $5, $6)
                   RETURNING id""",
                invoice_num, reseller_uuid, wholesale_price, due_date, now, json.dumps(line_items)
            )
            invoice_id = inv_rows[0]["id"]

            # Log payment
            await conn.execute(
                """INSERT INTO payments (invoice_id, reseller_id, amount, status, method, reference, paid_at, created_at)
                   VALUES ($1, $2, $3, 'succeeded', 'card', $4, $5, $5)""",
                invoice_id, reseller_uuid, wholesale_price, reference, now
            )

            # Update reseller minutes balance
            await conn.execute(
                "UPDATE resellers SET minutes_balance = minutes_balance + $1 WHERE id = $2",
                minutes, reseller_uuid
            )

            logger.info(f"Reseller {reseller_name} ({buyer_id}) successfully purchased wholesale plan {plan_name}. Minutes +{minutes}.")

    await database.transaction(trans_cb)


# --- Endpoint Route Definitions ---

@router.post("/buy-plan")
async def buy_plan(req_body: BuyPlanRequest, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    settings = get_settings()
    origin = request.headers.get("origin") or "http://localhost:3000"
    plan_id = req_body.planId

    # Find the plan
    plan_uuid = uuid.UUID(plan_id)
    plan_rows = await database.query(
        "SELECT id, name, price, minutes, reseller_id, is_custom, status FROM plans WHERE id = $1",
        [plan_uuid]
    )
    if not plan_rows:
        return ApiResponse.error(404, "Plan not found", "PLAN_NOT_FOUND")
    
    plan = plan_rows[0]
    if plan["status"] != "active":
        return ApiResponse.error(400, "This plan is currently inactive", "PLAN_INACTIVE")

    buyer_type = ""
    buyer_id = ""
    wholesale_price = float(plan["price"])
    client_price = 0.0

    if current_user["role"] == "CLIENT":
        buyer_type = "client"
        buyer_id = current_user["client_id"]
        if not buyer_id:
            return ApiResponse.error(400, "Current user is not linked to a Client profile", "CLIENT_PROFILE_MISSING")

        # Clients must buy at reseller rates. Find reseller client rate.
        client_rows = await database.query("SELECT reseller_id FROM clients WHERE id = $1", [uuid.UUID(buyer_id)])
        if not client_rows or not client_rows[0]["reseller_id"]:
            return ApiResponse.error(400, "Client has no linked reseller partner", "RESELLER_MISSING")

        reseller_id = client_rows[0]["reseller_id"]
        
        # Check custom reseller-configured rate
        rp_rows = await database.query(
            "SELECT client_price FROM reseller_plans WHERE reseller_id = $1 AND plan_id = $2 AND status = 'active'",
            [reseller_id, plan_uuid]
        )
        if not rp_rows:
            return ApiResponse.error(400, "Reseller has not configured retail pricing for this plan", "PLAN_UNAVAILABLE")
        
        client_price = float(rp_rows[0]["client_price"])
        charge_amount = client_price

    elif current_user["role"] == "RESELLER":
        buyer_type = "reseller"
        buyer_id = current_user["reseller_id"]
        if not buyer_id:
            return ApiResponse.error(400, "Current user is not linked to a Reseller profile", "RESELLER_PROFILE_MISSING")

        # Verify plan is accessible to reseller (either standard or specifically customized for them)
        if plan["is_custom"] and plan["reseller_id"] != uuid.UUID(buyer_id):
            return ApiResponse.error(403, "Access to this custom plan is forbidden", "PLAN_FORBIDDEN")

        charge_amount = wholesale_price

    else:
        # SUPER_ADMIN or FINANCE_ADMIN buying standard plan
        buyer_type = "reseller"
        buyer_id = current_user["reseller_id"] or str(uuid.UUID(int=0)) # Fallback id
        charge_amount = wholesale_price

    # Determine if Stripe is in Mock Mode
    is_mock = settings.stripe_secret_key.startswith("sk_test_mock") or not settings.stripe_secret_key

    if is_mock:
        # Return mock checkout redirect URL
        mock_checkout_url = (
            f"{origin}/plans?mock_checkout=true"
            f"&plan_id={plan_id}"
            f"&buyer_type={buyer_type}"
            f"&buyer_id={buyer_id}"
            f"&wholesale_price={wholesale_price}"
            f"&client_price={client_price}"
            f"&price={charge_amount}"
        )
        return ApiResponse.success(
            message="Mock Stripe Checkout session generated",
            data={"checkout_url": mock_checkout_url}
        )

    # Real Stripe integration
    try:
        stripe.api_key = settings.stripe_secret_key
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': plan["name"],
                        'description': f"Purchase of {plan['minutes']} minutes recharge plan.",
                    },
                    'unit_amount': int(charge_amount * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{origin}/plans?success=true&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/plans?cancelled=true",
            metadata={
                'plan_id': plan_id,
                'buyer_type': buyer_type,
                'buyer_id': buyer_id,
                'wholesale_price': str(wholesale_price),
                'client_price': str(client_price)
            }
        )
        return ApiResponse.success(
            message="Stripe Checkout session created",
            data={"checkout_url": session.url}
        )
    except Exception as e:
        logger.error(f"Stripe Checkout creation failed: {e}")
        return ApiResponse.error(500, f"Stripe integration error: {e}", "STRIPE_ERROR")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Receives events from Stripe Webhooks.
    Validates signature and processes completed checkout sessions.
    """
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.get('metadata', {})
        
        plan_id = metadata.get('plan_id')
        buyer_type = metadata.get('buyer_type')
        buyer_id = metadata.get('buyer_id')
        wholesale_price = float(metadata.get('wholesale_price', 0))
        client_price = float(metadata.get('client_price', 0))
        reference = session.get('payment_intent') or session.get('id', 'unknown_stripe_ref')
        
        if plan_id and buyer_type and buyer_id:
            try:
                await process_successful_payment(
                    plan_id, buyer_type, buyer_id, wholesale_price, client_price, reference
                )
            except Exception as e:
                logger.error(f"Failed to process successful payment webhook: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal processing error")
                
    return {"status": "success"}


@router.post("/mock-success")
async def mock_checkout_success(req_body: MockSuccessRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Simulates Stripe webhook callback for Mock Mode checkout testing.
    Can be called by client/reseller upon clicking 'Simulate Success' in frontend.
    """
    settings = get_settings()
    is_mock = settings.stripe_secret_key.startswith("sk_test_mock") or not settings.stripe_secret_key
    if not is_mock:
        return ApiResponse.error(400, "Mock endpoints are disabled in production Stripe configuration", "MOCK_DISABLED")

    # Find the plan
    plan_uuid = uuid.UUID(req_body.planId)
    plan_rows = await database.query("SELECT price FROM plans WHERE id = $1", [plan_uuid])
    if not plan_rows:
        return ApiResponse.error(404, "Plan not found", "PLAN_NOT_FOUND")
        
    wholesale_price = float(plan_rows[0]["price"])
    client_price = 0.0

    if req_body.buyerType == "client":
        client_uuid = uuid.UUID(req_body.buyerId)
        # Fetch reseller client rate
        client_rows = await database.query("SELECT reseller_id FROM clients WHERE id = $1", [client_uuid])
        if client_rows and client_rows[0]["reseller_id"]:
            reseller_id = client_rows[0]["reseller_id"]
            rp_rows = await database.query(
                "SELECT client_price FROM reseller_plans WHERE reseller_id = $1 AND plan_id = $2 AND status = 'active'",
                [reseller_id, plan_uuid]
            )
            if rp_rows:
                client_price = float(rp_rows[0]["client_price"])

    ref = req_body.reference or f"mock_stripe_{uuid.uuid4().hex[:10]}"

    try:
        await process_successful_payment(
            req_body.planId,
            req_body.buyerType,
            req_body.buyerId,
            wholesale_price,
            client_price,
            ref
        )
        return ApiResponse.success(message="Simulation transaction completed successfully!")
    except Exception as e:
        logger.error(f"Mock checkout simulation failed: {e}")
        return ApiResponse.error(500, f"Simulation database transaction failure: {e}", "DB_TRANSACTION_FAILED")


@router.get("/check-credits")
async def check_credits(agent_name: str):
    """
    Checks if client or reseller associated with the agent has positive minute balance.
    Used by agent worker (agent.py) to validate call authorization.
    """
    # 1. Resolve agent by name
    agent_rows = await database.query(
        "SELECT client_id, user_id FROM agents WHERE LOWER(name) = LOWER($1)",
        [agent_name.strip()]
    )
    if not agent_rows:
        return {"has_credits": True, "minutes_balance": 100}
        
    agent = agent_rows[0]
    
    # 2. Check client credits
    if agent["client_id"]:
        client_uuid = uuid.UUID(str(agent["client_id"]))
        cl_rows = await database.query(
            "SELECT minutes_balance FROM clients WHERE id = $1",
            [client_uuid]
        )
        if cl_rows:
            balance = cl_rows[0]["minutes_balance"]
            return {"has_credits": balance > 0, "minutes_balance": balance}
            
    # 3. Check reseller credits (based on user)
    if agent["user_id"]:
        user_uuid = uuid.UUID(str(agent["user_id"]))
        user_rows = await database.query(
            "SELECT reseller_id FROM users WHERE id = $1",
            [user_uuid]
        )
        if user_rows and user_rows[0]["reseller_id"]:
            reseller_uuid = uuid.UUID(str(user_rows[0]["reseller_id"]))
            res_rows = await database.query(
                "SELECT minutes_balance FROM resellers WHERE id = $1",
                [reseller_uuid]
            )
            if res_rows:
                balance = res_rows[0]["minutes_balance"]
                return {"has_credits": balance > 0, "minutes_balance": balance}
                
    return {"has_credits": True, "minutes_balance": 100}

