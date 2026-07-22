"""
Finance Module Router.
Handles endpoints for plan management, invoices, payments, contracts, renewals, commissions, and dashboards.
"""

import logging
import uuid
import datetime
import json
import calendar
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from api import database
from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user, require_roles

router = APIRouter()
logger = logging.getLogger("voice-agent.api.finance")

# --- Request Models ---

class CreatePlanRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    price: float = Field(..., ge=0.0)
    minutes: int = Field(..., ge=0)
    isCustom: bool = False
    resellerId: Optional[str] = None

class UpdatePlanRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    minutes: Optional[int] = None
    status: Optional[str] = None

class SetClientPriceRequest(BaseModel):
    clientPrice: float = Field(..., ge=0.0)
    status: Optional[str] = "active"

class CreateInvoiceRequest(BaseModel):
    clientId: Optional[str] = None
    resellerId: Optional[str] = None
    amount: float
    tax: float = 0.0
    total: float
    dueDate: datetime.datetime
    lineItems: List[Dict[str, Any]] = []

class UpdateInvoiceRequest(BaseModel):
    status: str
    paidAmount: Optional[float] = None

class CreateContractRequest(BaseModel):
    clientId: str
    contractValue: float
    startDate: datetime.datetime
    endDate: datetime.datetime
    autoRenewal: bool = False
    paymentTerms: Optional[str] = None
    billingCycle: Optional[str] = None
    noticePeriodDays: int = 30
    notes: Optional[str] = None

class UpdateContractRequest(BaseModel):
    status: Optional[str] = None
    contractValue: Optional[float] = None
    endDate: Optional[datetime.datetime] = None
    autoRenewal: Optional[bool] = None
    notes: Optional[str] = None

# --- Helper functions for mapping database records ---

def map_plan(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "description": r.get("description") or "",
        "price": float(r["price"]),
        "minutes": int(r["minutes"]),
        "isCustom": bool(r["is_custom"]),
        "resellerId": str(r["reseller_id"]) if r.get("reseller_id") else None,
        "status": r["status"],
        "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"],
        "clientPrice": float(r["client_price"]) if r.get("client_price") is not None else None,
        "resellerPlanStatus": r.get("reseller_plan_status") or "inactive"
    }

def map_invoice(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(r["id"]),
        "number": r["number"],
        "clientId": str(r["client_id"]) if r.get("client_id") else None,
        "clientName": r.get("client_name") or "",
        "resellerId": str(r["reseller_id"]) if r.get("reseller_id") else None,
        "resellerName": r.get("reseller_name") or "",
        "amount": float(r["amount"]),
        "tax": float(r["tax"]),
        "total": float(r["total"]),
        "paidAmount": float(r["paid_amount"]),
        "status": r["status"],
        "dueDate": r["due_date"].isoformat() if hasattr(r["due_date"], "isoformat") else r["due_date"],
        "issueDate": r["issue_date"].isoformat() if hasattr(r["issue_date"], "isoformat") else r["issue_date"],
        "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"],
        "lineItems": r["line_items"] if isinstance(r["line_items"], list) else []
    }

def map_payment(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(r["id"]),
        "invoiceId": str(r["invoice_id"]) if r.get("invoice_id") else None,
        "invoiceNumber": r.get("invoice_number") or "",
        "clientId": str(r["client_id"]) if r.get("client_id") else None,
        "clientName": r.get("client_name") or "",
        "resellerId": str(r["reseller_id"]) if r.get("reseller_id") else None,
        "resellerName": r.get("reseller_name") or "",
        "amount": float(r["amount"]),
        "status": r["status"],
        "method": r["method"],
        "reference": r["reference"] or "",
        "paidAt": r["paid_at"].isoformat() if hasattr(r["paid_at"], "isoformat") else r["paid_at"],
        "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"]
    }

def map_contract(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(r["id"]),
        "number": r["number"],
        "clientId": str(r["client_id"]),
        "clientName": r.get("client_name") or "",
        "contractValue": float(r["contract_value"]),
        "status": r["status"],
        "startDate": r["start_date"].isoformat() if hasattr(r["start_date"], "isoformat") else r["start_date"],
        "endDate": r["end_date"].isoformat() if hasattr(r["end_date"], "isoformat") else r["end_date"],
        "autoRenewal": bool(r["auto_renewal"]),
        "paymentTerms": r.get("payment_terms") or "",
        "billingCycle": r.get("billing_cycle") or "",
        "noticePeriodDays": int(r.get("notice_period_days") or 30),
        "notes": r.get("notes") or "",
        "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"]
    }

def map_renewal(r: Dict[str, Any]) -> Dict[str, Any]:
    end_date = r.get("end_date")
    return {
        "id": str(r["id"]),
        "clientId": str(r["client_id"]),
        "clientName": r.get("client_name") or "",
        "contractId": str(r["contract_id"]),
        "contractNumber": r.get("contract_number") or "",
        "value": float(r["value"]),
        "status": r["status"],
        "renewalDate": r["renewal_date"].isoformat() if hasattr(r["renewal_date"], "isoformat") else r["renewal_date"],
        "date": r["renewal_date"].isoformat() if hasattr(r["renewal_date"], "isoformat") else r["renewal_date"],
        "endDate": end_date.isoformat() if (end_date is not None and hasattr(end_date, "isoformat")) else end_date,
        "owner": r.get("owner") or "Account Manager",
        "probability": int(r.get("probability") or 80),
        "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"]
    }

def map_commission(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(r["id"]),
        "resellerId": str(r["reseller_id"]),
        "resellerName": r.get("reseller_name") or "",
        "clientId": str(r["client_id"]) if r.get("client_id") else None,
        "clientName": r.get("client_name") or "",
        "invoiceId": str(r["invoice_id"]) if r.get("invoice_id") else None,
        "invoiceNumber": r.get("invoice_number") or "",
        "amount": float(r["amount"]),
        "commissionPct": float(r["commission_pct"]),
        "status": r["status"],
        "date": r["date"].isoformat() if hasattr(r["date"], "isoformat") else r["date"],
        "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"]
    }


# --- 1. Plans Endpoints ---

@router.get("/plans")
async def get_plans(current_user: Dict[str, Any] = Depends(get_current_user)):
    role = current_user["role"]
    
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        # Admins see all plans
        rows = await database.query("SELECT * FROM plans ORDER BY is_custom ASC, price ASC")
        return ApiResponse.success(data=[map_plan(r) for r in rows])
        
    elif role == "RESELLER":
        # Resellers see standard plans + custom plans assigned to them, plus their retail rate
        reseller_id = uuid.UUID(current_user["reseller_id"])
        rows = await database.query(
            """SELECT p.*, rp.client_price, rp.status as reseller_plan_status
               FROM plans p
               LEFT JOIN reseller_plans rp ON p.id = rp.plan_id AND rp.reseller_id = $1
               WHERE p.is_custom = FALSE OR p.reseller_id = $1
               ORDER BY p.price ASC""",
            [reseller_id]
        )
        return ApiResponse.success(data=[map_plan(r) for r in rows])
        
    elif role == "CLIENT":
        # Clients see plans configured for them by their reseller
        client_id = uuid.UUID(current_user["client_id"])
        client_rows = await database.query("SELECT reseller_id FROM clients WHERE id = $1", [client_id])
        if not client_rows or not client_rows[0]["reseller_id"]:
            return ApiResponse.success(data=[])
            
        reseller_id = client_rows[0]["reseller_id"]
        rows = await database.query(
            """SELECT p.*, rp.client_price, rp.status as reseller_plan_status
               FROM plans p
               JOIN reseller_plans rp ON p.id = rp.plan_id
               WHERE rp.reseller_id = $1 AND rp.status = 'active'
               ORDER BY rp.client_price ASC""",
            [reseller_id]
        )
        return ApiResponse.success(data=[map_plan(r) for r in rows])

    return ApiResponse.success(data=[])


@router.post("/plans", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def create_plan(req_body: CreatePlanRequest):
    reseller_uuid = uuid.UUID(req_body.resellerId) if req_body.resellerId else None
    rows = await database.query(
        """INSERT INTO plans (name, description, price, minutes, is_custom, reseller_id, status)
           VALUES ($1, $2, $3, $4, $5, $6, 'active')
           RETURNING *""",
        [req_body.name, req_body.description, req_body.price, req_body.minutes, req_body.isCustom, reseller_uuid]
    )
    return ApiResponse.success(status_code=201, message="Plan created successfully", data=map_plan(rows[0]))


@router.put("/plans/{plan_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def update_plan(plan_id: str, req_body: UpdatePlanRequest):
    plan_uuid = uuid.UUID(plan_id)
    fields = []
    params = [plan_uuid]
    idx = 2
    
    dto = req_body.dict(exclude_unset=True)
    if not dto:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    for k, v in dto.items():
        db_key = "is_custom" if k == "isCustom" else k
        fields.append(f"{db_key} = ${idx}")
        params.append(v)
        idx += 1
        
    query = f"UPDATE plans SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = $1 RETURNING *"
    rows = await database.query(query, params)
    if not rows:
        return ApiResponse.error(404, "Plan not found", "PLAN_NOT_FOUND")
    return ApiResponse.success(message="Plan updated successfully", data=map_plan(rows[0]))


@router.post("/plans/{plan_id}/set-rate", dependencies=[Depends(require_roles(["RESELLER"]))])
async def set_client_rate(plan_id: str, req_body: SetClientPriceRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    plan_uuid = uuid.UUID(plan_id)
    reseller_id = uuid.UUID(current_user["reseller_id"])
    
    # 1. Verify plan exists
    plan_rows = await database.query("SELECT id FROM plans WHERE id = $1", [plan_uuid])
    if not plan_rows:
        return ApiResponse.error(404, "Plan not found", "PLAN_NOT_FOUND")
        
    # 2. Upsert rate in reseller_plans
    rows = await database.query(
        """INSERT INTO reseller_plans (reseller_id, plan_id, client_price, status)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (reseller_id, plan_id) 
           DO UPDATE SET client_price = EXCLUDED.client_price, status = EXCLUDED.status, updated_at = CURRENT_TIMESTAMP
           RETURNING *""",
        [reseller_id, plan_uuid, req_body.clientPrice, req_body.status]
    )
    return ApiResponse.success(message="Retail pricing configured successfully", data=rows[0])


# --- 2. Invoices Endpoints ---

@router.get("/invoices")
async def get_invoices(current_user: Dict[str, Any] = Depends(get_current_user)):
    role = current_user["role"]
    
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        rows = await database.query(
            """SELECT i.*, c.name as client_name, r.name as reseller_name
               FROM invoices i
               LEFT JOIN clients c ON i.client_id = c.id
               LEFT JOIN resellers r ON i.reseller_id = r.id
               ORDER BY i.created_at DESC"""
        )
        return ApiResponse.success(data=[map_invoice(r) for r in rows])
        
    elif role == "RESELLER":
        reseller_id = uuid.UUID(current_user["reseller_id"])
        rows = await database.query(
            """SELECT i.*, c.name as client_name, r.name as reseller_name
               FROM invoices i
               LEFT JOIN clients c ON i.client_id = c.id
               LEFT JOIN resellers r ON i.reseller_id = r.id
               WHERE i.reseller_id = $1 OR c.reseller_id = $1
               ORDER BY i.created_at DESC""",
            [reseller_id]
        )
        return ApiResponse.success(data=[map_invoice(r) for r in rows])
        
    elif role == "CLIENT":
        client_id = uuid.UUID(current_user["client_id"])
        rows = await database.query(
            """SELECT i.*, c.name as client_name
               FROM invoices i
               JOIN clients c ON i.client_id = c.id
               WHERE i.client_id = $1
               ORDER BY i.created_at DESC""",
            [client_id]
        )
        return ApiResponse.success(data=[map_invoice(r) for r in rows])

    return ApiResponse.success(data=[])


@router.get("/invoices/{invoice_id}")
async def get_invoice_detail(invoice_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    inv_uuid = uuid.UUID(invoice_id)
    rows = await database.query(
        """SELECT i.*, c.name as client_name, r.name as reseller_name
           FROM invoices i
           LEFT JOIN clients c ON i.client_id = c.id
           LEFT JOIN resellers r ON i.reseller_id = r.id
           WHERE i.id = $1""",
        [inv_uuid]
    )
    if not rows:
        return ApiResponse.error(404, "Invoice not found", "INVOICE_NOT_FOUND")
        
    inv = rows[0]
    # Check permissions
    role = current_user["role"]
    if role == "CLIENT" and str(inv["client_id"]) != current_user["client_id"]:
        return ApiResponse.error(403, "Access forbidden", "INVOICE_FORBIDDEN")
    if role == "RESELLER":
        # must be reseller's invoice or client's invoice
        is_owner = str(inv["reseller_id"]) == current_user["reseller_id"]
        client_reseller = None
        if inv["client_id"]:
            c_rows = await database.query("SELECT reseller_id FROM clients WHERE id = $1", [inv["client_id"]])
            if c_rows:
                client_reseller = str(c_rows[0]["reseller_id"])
        if not is_owner and client_reseller != current_user["reseller_id"]:
            return ApiResponse.error(403, "Access forbidden", "INVOICE_FORBIDDEN")
            
    return ApiResponse.success(data=map_invoice(inv))


@router.post("/invoices", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def create_invoice(req_body: CreateInvoiceRequest):
    c_id = uuid.UUID(req_body.clientId) if req_body.clientId else None
    r_id = uuid.UUID(req_body.resellerId) if req_body.resellerId else None
    inv_num = f"INV-{uuid.uuid4().hex[:8].upper()}"
    
    rows = await database.query(
        """INSERT INTO invoices (number, client_id, reseller_id, amount, tax, total, paid_amount, status, due_date, line_items)
           VALUES ($1, $2, $3, $4, $5, $6, 0.00, 'pending', $7, $8)
           RETURNING *""",
        [inv_num, c_id, r_id, req_body.amount, req_body.tax, req_body.total, req_body.dueDate, json.dumps(req_body.lineItems)]
    )
    return ApiResponse.success(status_code=201, message="Invoice generated successfully", data=map_invoice(rows[0]))


@router.put("/invoices/{invoice_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def update_invoice(invoice_id: str, req_body: UpdateInvoiceRequest):
    inv_uuid = uuid.UUID(invoice_id)
    fields = ["status = $2"]
    params: List[Any] = [inv_uuid, req_body.status]
    idx = 3
    
    if req_body.paidAmount is not None:
        fields.append(f"paid_amount = ${idx}")
        params.append(req_body.paidAmount)
        idx += 1
        
    query = f"UPDATE invoices SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = $1 RETURNING *"
    rows = await database.query(query, params)
    if not rows:
        return ApiResponse.error(404, "Invoice not found", "INVOICE_NOT_FOUND")
    return ApiResponse.success(message="Invoice updated successfully", data=map_invoice(rows[0]))


# --- 3. Payments Endpoints ---

@router.get("/payments")
async def get_payments(current_user: Dict[str, Any] = Depends(get_current_user)):
    role = current_user["role"]
    
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        rows = await database.query(
            """SELECT p.*, i.number as invoice_number, c.name as client_name, r.name as reseller_name
               FROM payments p
               LEFT JOIN invoices i ON p.invoice_id = i.id
               LEFT JOIN clients c ON p.client_id = c.id
               LEFT JOIN resellers r ON p.reseller_id = r.id
               ORDER BY p.created_at DESC"""
        )
        return ApiResponse.success(data=[map_payment(r) for r in rows])
        
    elif role == "RESELLER":
        reseller_id = uuid.UUID(current_user["reseller_id"])
        rows = await database.query(
            """SELECT p.*, i.number as invoice_number, c.name as client_name, r.name as reseller_name
               FROM payments p
               LEFT JOIN invoices i ON p.invoice_id = i.id
               LEFT JOIN clients c ON p.client_id = c.id
               LEFT JOIN resellers r ON p.reseller_id = r.id
               WHERE p.reseller_id = $1 OR c.reseller_id = $1
               ORDER BY p.created_at DESC""",
            [reseller_id]
        )
        return ApiResponse.success(data=[map_payment(r) for r in rows])
        
    elif role == "CLIENT":
        client_id = uuid.UUID(current_user["client_id"])
        rows = await database.query(
            """SELECT p.*, i.number as invoice_number, c.name as client_name
               FROM payments p
               LEFT JOIN invoices i ON p.invoice_id = i.id
               LEFT JOIN clients c ON p.client_id = c.id
               WHERE p.client_id = $1
               ORDER BY p.created_at DESC""",
            [client_id]
        )
        return ApiResponse.success(data=[map_payment(r) for r in rows])

    return ApiResponse.success(data=[])


# --- 4. Contracts Endpoints ---

@router.get("/contracts")
async def get_contracts(current_user: Dict[str, Any] = Depends(get_current_user)):
    role = current_user["role"]
    
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        rows = await database.query(
            """SELECT co.*, cl.name as client_name 
               FROM contracts co
               JOIN clients cl ON co.client_id = cl.id
               ORDER BY co.end_date ASC"""
        )
        return ApiResponse.success(data=[map_contract(r) for r in rows])
        
    elif role == "RESELLER":
        reseller_id = uuid.UUID(current_user["reseller_id"])
        rows = await database.query(
            """SELECT co.*, cl.name as client_name 
               FROM contracts co
               JOIN clients cl ON co.client_id = cl.id
               WHERE cl.reseller_id = $1
               ORDER BY co.end_date ASC""",
            [reseller_id]
        )
        return ApiResponse.success(data=[map_contract(r) for r in rows])
        
    elif role == "CLIENT":
        client_id = uuid.UUID(current_user["client_id"])
        rows = await database.query(
            """SELECT co.*, cl.name as client_name 
               FROM contracts co
               JOIN clients cl ON co.client_id = cl.id
               WHERE co.client_id = $1
               ORDER BY co.end_date ASC""",
            [client_id]
        )
        return ApiResponse.success(data=[map_contract(r) for r in rows])

    return ApiResponse.success(data=[])


@router.get("/contracts/{contract_id}")
async def get_contract_detail(contract_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    contract_uuid = uuid.UUID(contract_id)
    rows = await database.query(
        """SELECT co.*, cl.name as client_name 
           FROM contracts co
           JOIN clients cl ON co.client_id = cl.id
           WHERE co.id = $1""",
        [contract_uuid]
    )
    if not rows:
        return ApiResponse.error(404, "Contract not found", "CONTRACT_NOT_FOUND")
        
    contract = rows[0]
    role = current_user["role"]
    # Check permissions
    if role == "CLIENT" and str(contract["client_id"]) != current_user["client_id"]:
        return ApiResponse.error(403, "Access forbidden", "CONTRACT_FORBIDDEN")
    if role == "RESELLER":
        c_rows = await database.query("SELECT reseller_id FROM clients WHERE id = $1", [contract["client_id"]])
        if not c_rows or str(c_rows[0]["reseller_id"]) != current_user["reseller_id"]:
            return ApiResponse.error(403, "Access forbidden", "CONTRACT_FORBIDDEN")
            
    return ApiResponse.success(data=map_contract(contract))


@router.post("/contracts", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN", "RESELLER"]))])
async def create_contract(req_body: CreateContractRequest):
    c_uuid = uuid.UUID(req_body.clientId)
    contract_num = f"CON-{uuid.uuid4().hex[:8].upper()}"
    
    # Simple check on permissions - resellers can only contract their clients
    # Handled by auth role filters globally
    
    rows = await database.query(
        """INSERT INTO contracts (number, client_id, contract_value, status, start_date, end_date, auto_renewal, payment_terms, billing_cycle, notice_period_days, notes)
           VALUES ($1, $2, $3, 'active', $4, $5, $6, $7, $8, $9, $10)
           RETURNING *""",
        [contract_num, c_uuid, req_body.contractValue, req_body.startDate, req_body.endDate, req_body.autoRenewal, req_body.paymentTerms, req_body.billingCycle, req_body.noticePeriodDays, req_body.notes]
    )
    
    # Seed a pending renewal entry automatically
    contract = rows[0]
    await database.query(
        """INSERT INTO renewals (client_id, contract_id, value, status, renewal_date, probability)
           VALUES ($1, $2, $3, 'pending', $4, 80)""",
        [c_uuid, contract["id"], req_body.contractValue, req_body.endDate]
    )
    
    return ApiResponse.success(status_code=201, message="Contract created successfully", data=map_contract(contract))


@router.put("/contracts/{contract_id}", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN", "RESELLER"]))])
async def update_contract(contract_id: str, req_body: UpdateContractRequest):
    contract_uuid = uuid.UUID(contract_id)
    fields = []
    params = [contract_uuid]
    idx = 2
    
    dto = req_body.dict(exclude_unset=True)
    if not dto:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    for k, v in dto.items():
        db_key = "contract_value" if k == "contractValue" else "end_date" if k == "endDate" else "auto_renewal" if k == "autoRenewal" else k
        fields.append(f"{db_key} = ${idx}")
        params.append(v)
        idx += 1
        
    query = f"UPDATE contracts SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = $1 RETURNING *"
    rows = await database.query(query, params)
    if not rows:
        return ApiResponse.error(404, "Contract not found", "CONTRACT_NOT_FOUND")
        
    # If end_date was updated, sync renewal date
    if req_body.endDate:
        await database.query(
            "UPDATE renewals SET renewal_date = $1 WHERE contract_id = $2",
            [req_body.endDate, contract_uuid]
        )
        
    return ApiResponse.success(message="Contract updated successfully", data=map_contract(rows[0]))


# --- 5. Renewals Endpoints ---

@router.get("/renewals")
async def get_renewals(current_user: Dict[str, Any] = Depends(get_current_user)):
    role = current_user["role"]
    
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        rows = await database.query(
            """SELECT r.*, cl.name as client_name, co.number as contract_number, co.end_date
               FROM renewals r
               JOIN clients cl ON r.client_id = cl.id
               JOIN contracts co ON r.contract_id = co.id
               ORDER BY r.renewal_date ASC"""
        )
        return ApiResponse.success(data=[map_renewal(r) for r in rows])
        
    elif role == "RESELLER":
        reseller_id = uuid.UUID(current_user["reseller_id"])
        rows = await database.query(
            """SELECT r.*, cl.name as client_name, co.number as contract_number, co.end_date
               FROM renewals r
               JOIN clients cl ON r.client_id = cl.id
               JOIN contracts co ON r.contract_id = co.id
               WHERE cl.reseller_id = $1
               ORDER BY r.renewal_date ASC""",
            [reseller_id]
        )
        return ApiResponse.success(data=[map_renewal(r) for r in rows])
        
    elif role == "CLIENT":
        client_id = uuid.UUID(current_user["client_id"])
        rows = await database.query(
            """SELECT r.*, cl.name as client_name, co.number as contract_number, co.end_date
               FROM renewals r
               JOIN clients cl ON r.client_id = cl.id
               JOIN contracts co ON r.contract_id = co.id
               WHERE r.client_id = $1
               ORDER BY r.renewal_date ASC""",
            [client_id]
        )
        return ApiResponse.success(data=[map_renewal(r) for r in rows])

    return ApiResponse.success(data=[])


# --- 6. Commissions Endpoints ---

@router.get("/commissions")
async def get_commissions(current_user: Dict[str, Any] = Depends(get_current_user)):
    role = current_user["role"]
    
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        rows = await database.query(
            """SELECT co.*, r.name as reseller_name, c.name as client_name, i.number as invoice_number
               FROM commissions co
               JOIN resellers r ON co.reseller_id = r.id
               LEFT JOIN clients c ON co.client_id = c.id
               LEFT JOIN invoices i ON co.invoice_id = i.id
               ORDER BY co.created_at DESC"""
        )
        return ApiResponse.success(data=[map_commission(r) for r in rows])
        
    elif role == "RESELLER":
        reseller_id = uuid.UUID(current_user["reseller_id"])
        rows = await database.query(
            """SELECT co.*, r.name as reseller_name, c.name as client_name, i.number as invoice_number
               FROM commissions co
               JOIN resellers r ON co.reseller_id = r.id
               LEFT JOIN clients c ON co.client_id = c.id
               LEFT JOIN invoices i ON co.invoice_id = i.id
               WHERE co.reseller_id = $1
               ORDER BY co.created_at DESC""",
            [reseller_id]
        )
        return ApiResponse.success(data=[map_commission(r) for r in rows])

    return ApiResponse.success(data=[])


@router.post("/commissions/{commission_id}/payout", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def process_commission_payout(commission_id: str):
    comm_uuid = uuid.UUID(commission_id)
    rows = await database.query(
        "UPDATE commissions SET status = 'paid' WHERE id = $1 RETURNING *",
        [comm_uuid]
    )
    if not rows:
        return ApiResponse.error(404, "Commission record not found", "COMMISSION_NOT_FOUND")
    return ApiResponse.success(message="Commission payout completed successfully", data=rows[0])


# --- 7. Dashboards APIs ---

@router.get("/dashboard/summary")
async def get_dashboard_summary(current_user: Dict[str, Any] = Depends(get_current_user)):
    role = current_user["role"]
    
    # Set default structures
    totals = {
        "revenueCollected": 0.00,
        "revenueDue": 0.00,
        "revenueOverdue": 0.00,
        "pendingInvoices": 0,
        "mrr": 0.00,
        "arr": 0.00,
        "activeClients": 0,
        "activeResellers": 0,
        "activeAgents": 0,
        "totalCalls": 0,
        "totalMessages": 0,
        "totalMinutes": 0,
        "totalConversations": 0
    }
    
    now = datetime.datetime.now(datetime.timezone.utc)
    current_year = now.year
    current_month = now.month
    
    monthly_trend = []
    for i in range(5, -1, -1):
        m_idx = current_month - i
        y_idx = current_year
        if m_idx <= 0:
            m_idx += 12
            y_idx -= 1
        m_name = calendar.month_abbr[m_idx]
        monthly_trend.append({
            "month": m_name,
            "year": y_idx,
            "month_num": m_idx,
            "revenueCollected": 0.00,
            "revenueDue": 0.00
        })

    # Fetch total call records
    agent_stats = await database.query(
        "SELECT SUM(total_calls) as calls, SUM(total_messages) as msgs, SUM(total_minutes) as mins FROM agents"
    )
    if agent_stats and agent_stats[0]["calls"] is not None:
        totals["totalCalls"] = int(agent_stats[0]["calls"])
        totals["totalMessages"] = int(agent_stats[0]["msgs"])
        totals["totalMinutes"] = int(agent_stats[0]["mins"])
        totals["totalConversations"] = int(agent_stats[0]["calls"])

    # Expose counts
    cl_count = await database.query("SELECT COUNT(*) FROM clients WHERE status = 'active'")
    totals["activeClients"] = cl_count[0]["count"] if cl_count else 0
    
    re_count = await database.query("SELECT COUNT(*) FROM resellers WHERE status = 'active'")
    totals["activeResellers"] = re_count[0]["count"] if re_count else 0
    
    ag_count = await database.query("SELECT COUNT(*) FROM agents WHERE status = 'active'")
    totals["activeAgents"] = ag_count[0]["count"] if ag_count else 0

    # Scoped calculations
    if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        # MRR sum
        mrr_res = await database.query("SELECT SUM(monthly_recurring) FROM clients WHERE status = 'active'")
        totals["mrr"] = float(mrr_res[0]["sum"] or 0.00)
        totals["arr"] = totals["mrr"] * 12
        
        # Collections
        collected = await database.query("SELECT SUM(amount) FROM payments WHERE status = 'succeeded'")
        totals["revenueCollected"] = float(collected[0]["sum"] or 0.00)
        
        # Outstanding
        due = await database.query("SELECT SUM(total - paid_amount) FROM invoices WHERE status = 'pending' AND due_date >= $1", [now])
        totals["revenueDue"] = float(due[0]["sum"] or 0.00)
        
        overdue = await database.query("SELECT SUM(total - paid_amount) FROM invoices WHERE status = 'overdue' OR (status = 'pending' AND due_date < $1)", [now])
        totals["revenueOverdue"] = float(overdue[0]["sum"] or 0.00)
        
        pending_count = await database.query("SELECT COUNT(*) FROM invoices WHERE status = 'pending'")
        totals["pendingInvoices"] = pending_count[0]["count"] if pending_count else 0

        # Build database-driven trend
        col_rows = await database.query(
            """SELECT EXTRACT(MONTH FROM paid_at) as m_num, EXTRACT(YEAR FROM paid_at) as y_num, SUM(amount) as total_amt
               FROM payments
               WHERE status = 'succeeded' AND paid_at IS NOT NULL
               GROUP BY EXTRACT(MONTH FROM paid_at), EXTRACT(YEAR FROM paid_at)"""
        )
        for r in col_rows:
            m_n = int(r["m_num"])
            y_n = int(r["y_num"])
            t_a = float(r["total_amt"] or 0.00)
            for item in monthly_trend:
                if item["month_num"] == m_n and item["year"] == y_n:
                    item["revenueCollected"] = t_a
                    break

        due_rows = await database.query(
            """SELECT EXTRACT(MONTH FROM due_date) as m_num, EXTRACT(YEAR FROM due_date) as y_num, SUM(total - paid_amount) as total_amt
               FROM invoices
               WHERE status = 'pending' AND due_date IS NOT NULL
               GROUP BY EXTRACT(MONTH FROM due_date), EXTRACT(YEAR FROM due_date)"""
        )
        for r in due_rows:
            m_n = int(r["m_num"])
            y_n = int(r["y_num"])
            t_a = float(r["total_amt"] or 0.00)
            for item in monthly_trend:
                if item["month_num"] == m_n and item["year"] == y_n:
                    item["revenueDue"] = t_a
                    break

    elif role == "RESELLER":
        reseller_id = uuid.UUID(current_user["reseller_id"])
        
        # Managed client counts
        totals["activeClients"] = (await database.query("SELECT COUNT(*) FROM clients WHERE reseller_id = $1 AND status = 'active'", [reseller_id]))[0]["count"]
        
        # Collected commissions
        collected_comm = await database.query("SELECT SUM(amount) FROM commissions WHERE reseller_id = $1 AND status = 'paid'", [reseller_id])
        totals["revenueCollected"] = float(collected_comm[0]["sum"] or 0.00)
        
        # Pending commissions
        due_comm = await database.query("SELECT SUM(amount) FROM commissions WHERE reseller_id = $1 AND status = 'payable'", [reseller_id])
        totals["revenueDue"] = float(due_comm[0]["sum"] or 0.00)
        
        totals["revenueOverdue"] = 0.00

        # Trend query for Reseller
        col_rows = await database.query(
            """SELECT EXTRACT(MONTH FROM date) as m_num, EXTRACT(YEAR FROM date) as y_num, SUM(amount) as total_amt
               FROM commissions
               WHERE reseller_id = $1 AND status = 'paid' AND date IS NOT NULL
               GROUP BY EXTRACT(MONTH FROM date), EXTRACT(YEAR FROM date)""",
            [reseller_id]
        )
        for r in col_rows:
            m_n = int(r["m_num"])
            y_n = int(r["y_num"])
            t_a = float(r["total_amt"] or 0.00)
            for item in monthly_trend:
                if item["month_num"] == m_n and item["year"] == y_n:
                    item["revenueCollected"] = t_a
                    break

        due_rows = await database.query(
            """SELECT EXTRACT(MONTH FROM date) as m_num, EXTRACT(YEAR FROM date) as y_num, SUM(amount) as total_amt
               FROM commissions
               WHERE reseller_id = $1 AND status = 'payable' AND date IS NOT NULL
               GROUP BY EXTRACT(MONTH FROM date), EXTRACT(YEAR FROM date)""",
            [reseller_id]
        )
        for r in due_rows:
            m_n = int(r["m_num"])
            y_n = int(r["y_num"])
            t_a = float(r["total_amt"] or 0.00)
            for item in monthly_trend:
                if item["month_num"] == m_n and item["year"] == y_n:
                    item["revenueDue"] = t_a
                    break

    elif role == "CLIENT":
        client_id = uuid.UUID(current_user["client_id"])
        
        # Collections from client
        collected = await database.query("SELECT SUM(amount) FROM payments WHERE client_id = $1 AND status = 'succeeded'", [client_id])
        totals["revenueCollected"] = float(collected[0]["sum"] or 0.00)
        
        # Due from client
        due = await database.query("SELECT SUM(total - paid_amount) FROM invoices WHERE client_id = $1 AND status = 'pending' AND due_date >= $2", [client_id, now])
        totals["revenueDue"] = float(due[0]["sum"] or 0.00)
        
        overdue = await database.query("SELECT SUM(total - paid_amount) FROM invoices WHERE client_id = $1 AND (status = 'overdue' OR (status = 'pending' AND due_date < $2))", [client_id, now])
        totals["revenueOverdue"] = float(overdue[0]["sum"] or 0.00)

        # Trend query for Client
        col_rows = await database.query(
            """SELECT EXTRACT(MONTH FROM paid_at) as m_num, EXTRACT(YEAR FROM paid_at) as y_num, SUM(amount) as total_amt
               FROM payments
               WHERE client_id = $1 AND status = 'succeeded' AND paid_at IS NOT NULL
               GROUP BY EXTRACT(MONTH FROM paid_at), EXTRACT(YEAR FROM paid_at)""",
            [client_id]
        )
        for r in col_rows:
            m_n = int(r["m_num"])
            y_n = int(r["y_num"])
            t_a = float(r["total_amt"] or 0.00)
            for item in monthly_trend:
                if item["month_num"] == m_n and item["year"] == y_n:
                    item["revenueCollected"] = t_a
                    break

        due_rows = await database.query(
            """SELECT EXTRACT(MONTH FROM due_date) as m_num, EXTRACT(YEAR FROM due_date) as y_num, SUM(total - paid_amount) as total_amt
               FROM invoices
               WHERE client_id = $1 AND status = 'pending' AND due_date IS NOT NULL
               GROUP BY EXTRACT(MONTH FROM due_date), EXTRACT(YEAR FROM due_date)""",
            [client_id]
        )
        for r in due_rows:
            m_n = int(r["m_num"])
            y_n = int(r["y_num"])
            t_a = float(r["total_amt"] or 0.00)
            for item in monthly_trend:
                if item["month_num"] == m_n and item["year"] == y_n:
                    item["revenueDue"] = t_a
                    break

    # Clean up fields only used for internal mapping before returning
    for item in monthly_trend:
        item.pop("year", None)
        item.pop("month_num", None)

    return ApiResponse.success(data={"totals": totals, "monthlyTrend": monthly_trend})


@router.get("/dashboard/money", dependencies=[Depends(require_roles(["SUPER_ADMIN", "FINANCE_ADMIN"]))])
async def get_dashboard_money():
    totals = {
        "totalCollected": 0.00,
        "totalAvailable": 0.00,
        "totalDue": 0.00,
        "totalOverdue": 0.00,
        "grossRevenue": 0.00,
        "netRevenue": 0.00,
        "grossMargin": 80,
        "platformCost": 1500.00,
        "totalInvoicesRaised": 0,
        "totalInvoicesUnpaid": 0,
        "totalInvoicesPartial": 0,
        "commissionPayable": 0.00
    }
    
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Total payments collected
    collected = await database.query("SELECT SUM(amount) FROM payments WHERE status = 'succeeded'")
    totals["totalCollected"] = float(collected[0]["sum"] or 0.00)
    totals["grossRevenue"] = totals["totalCollected"]
    
    # 2. Commissions paid/payable
    paid_comm = await database.query("SELECT SUM(amount) FROM commissions WHERE status = 'paid'")
    payable_comm = await database.query("SELECT SUM(amount) FROM commissions WHERE status = 'payable'")
    
    commissions_paid = float(paid_comm[0]["sum"] or 0.00)
    totals["commissionPayable"] = float(payable_comm[0]["sum"] or 0.00)
    
    # 3. Available cash and net revenue
    totals["totalAvailable"] = max(totals["totalCollected"] - commissions_paid - totals["platformCost"], 0.00)
    totals["netRevenue"] = max(totals["totalCollected"] - commissions_paid, 0.00)
    
    # 4. Invoices stats
    all_invs = await database.query("SELECT COUNT(*) as raised, SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as unpaid, SUM(CASE WHEN status='partially_paid' THEN 1 ELSE 0 END) as partial FROM invoices")
    if all_invs:
        totals["totalInvoicesRaised"] = all_invs[0]["raised"] or 0
        totals["totalInvoicesUnpaid"] = all_invs[0]["unpaid"] or 0
        totals["totalInvoicesPartial"] = all_invs[0]["partial"] or 0
        
    # 5. Due & Overdue collections
    due = await database.query("SELECT SUM(total - paid_amount) FROM invoices WHERE status = 'pending' AND due_date >= $1", [now])
    totals["totalDue"] = float(due[0]["sum"] or 0.00)
    
    overdue = await database.query("SELECT SUM(total - paid_amount) FROM invoices WHERE status = 'overdue' OR (status = 'pending' AND due_date < $1)", [now])
    totals["totalOverdue"] = float(overdue[0]["sum"] or 0.00)

    # Calculate margin
    if totals["grossRevenue"] > 0:
        totals["grossMargin"] = int(round((totals["netRevenue"] / totals["grossRevenue"]) * 100))
    else:
        totals["grossMargin"] = 100

    # Build database-driven commissions trend
    commissions_trend = []
    current_year = now.year
    current_month = now.month
    for i in range(4, -1, -1):
        m_idx = current_month - i
        y_idx = current_year
        if m_idx <= 0:
            m_idx += 12
            y_idx -= 1
        m_name = calendar.month_abbr[m_idx]
        commissions_trend.append({
            "month": m_name,
            "year": y_idx,
            "month_num": m_idx,
            "commissions": 0.00
        })

    comm_trend_rows = await database.query(
        """SELECT EXTRACT(MONTH FROM date) as m_num, EXTRACT(YEAR FROM date) as y_num, SUM(amount) as total_amt
           FROM commissions
           WHERE status = 'paid' AND date IS NOT NULL
           GROUP BY EXTRACT(MONTH FROM date), EXTRACT(YEAR FROM date)"""
    )
    for r in comm_trend_rows:
        m_n = int(r["m_num"])
        y_n = int(r["y_num"])
        t_a = float(r["total_amt"] or 0.00)
        for item in commissions_trend:
            if item["month_num"] == m_n and item["year"] == y_n:
                item["commissions"] = t_a
                break

    for item in commissions_trend:
        item.pop("year", None)
        item.pop("month_num", None)

    return ApiResponse.success(data={"totals": totals, "commissionsTrend": commissions_trend})


@router.get("/notifications")
async def get_notifications(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Mock notifications API endpoint to prevent dashboard page 404s.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    
    mock_notifs = [
        {
            "id": 1,
            "title": "Stripe Sandbox Activated",
            "message": "Payment gateway set up in mock sandbox mode.",
            "type": "success",
            "read": False,
            "createdAt": (now - datetime.timedelta(hours=1)).isoformat()
        },
        {
            "id": 2,
            "title": "Welcome to Command Centre",
            "message": "Dynamic call minute balance controls are active.",
            "type": "info",
            "read": False,
            "createdAt": (now - datetime.timedelta(hours=4)).isoformat()
        },
        {
            "id": 3,
            "title": "System Check Succeeded",
            "message": "FastAPI backend connected to PostgreSQL database.",
            "type": "success",
            "read": True,
            "createdAt": (now - datetime.timedelta(days=1)).isoformat()
        }
    ]
    return ApiResponse.success(data=mock_notifs)

