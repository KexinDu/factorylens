from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response

from .maintenance_reports import report_download
from .work_orders import (
    Identifier,
    Status,
    WorkOrder,
    WorkOrderConflict,
    WorkOrderCreate,
    WorkOrderPage,
    WorkOrderUpdate,
)

router = APIRouter(prefix="/api/v1/work-orders", tags=["work orders"])


@router.post("", response_model=WorkOrder, status_code=201)
def create_order(payload: WorkOrderCreate, request: Request):
    try:
        return request.app.state.work_orders.create(payload)
    except KeyError as exc:
        raise HTTPException(404, exc.args[0]) from exc
    except WorkOrderConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("", response_model=WorkOrderPage)
def list_orders(
    request: Request, status: Status | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return request.app.state.work_orders.list(status, limit, offset)


@router.get("/{work_order_id}", response_model=WorkOrder)
def get_order(work_order_id: Identifier, request: Request):
    order = request.app.state.work_orders.get(work_order_id)
    if order is None:
        raise HTTPException(404, "Work order not found.")
    return order


@router.get("/{work_order_id}/report", response_class=Response,
            responses={200: {"content": {"text/markdown": {}}}})
def download_work_order_report(work_order_id: Identifier, request: Request):
    order = get_order(work_order_id, request)
    return report_download(order.diagnostic_snapshot, order)


@router.patch("/{work_order_id}", response_model=WorkOrder)
def update_order(work_order_id: Identifier, payload: WorkOrderUpdate, request: Request):
    if payload.status is None and payload.maintenance_notes is None:
        raise HTTPException(422, "Provide a status or maintenance notes to update.")
    try:
        return request.app.state.work_orders.update(work_order_id, payload)
    except KeyError as exc:
        raise HTTPException(404, exc.args[0]) from exc
    except WorkOrderConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
