from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from api.database import get_db
from api.models import User, PaymentMethod
from api.schemas import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
    PaymentMethodResponse
)
from api.routers.auth import get_current_active_user, require_role

router = APIRouter(prefix="/payment-methods", tags=["Payment Methods"])


@router.get("", response_model=List[PaymentMethodResponse])
async def list_payment_methods(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all payment methods"""
    stmt = select(PaymentMethod).order_by(PaymentMethod.name)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{method_id}", response_model=PaymentMethodResponse)
async def get_payment_method(
    method_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific payment method"""
    stmt = select(PaymentMethod).where(PaymentMethod.id == method_id)
    result = await db.execute(stmt)
    method = result.scalar_one_or_none()
    
    if not method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    return method


@router.post("", response_model=PaymentMethodResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_method(
    method_data: PaymentMethodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Create a new payment method (Admin only)"""
    method = PaymentMethod(**method_data.model_dump())
    db.add(method)
    await db.commit()
    await db.refresh(method)
    return method


@router.patch("/{method_id}", response_model=PaymentMethodResponse)
async def update_payment_method(
    method_id: int,
    method_data: PaymentMethodUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Update a payment method (Admin only)"""
    stmt = select(PaymentMethod).where(PaymentMethod.id == method_id)
    result = await db.execute(stmt)
    method = result.scalar_one_or_none()
    
    if not method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    for field, value in method_data.model_dump(exclude_unset=True).items():
        setattr(method, field, value)
    
    await db.commit()
    await db.refresh(method)
    return method


@router.delete("/{method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_method(
    method_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Deactivate a payment method (Admin only) - soft delete"""
    stmt = select(PaymentMethod).where(PaymentMethod.id == method_id)
    result = await db.execute(stmt)
    method = result.scalar_one_or_none()
    
    if not method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # Soft delete - just set is_active to False
    method.is_active = False
    await db.commit()
    
    return None
