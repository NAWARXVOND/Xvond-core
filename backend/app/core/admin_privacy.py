from fastapi import APIRouter


# Xvond Admin is the platform/operator control plane. Customer conversation
# content and customer-created business requests belong to the tenant portal
# (or the tenant's connected external system), not the Xvond operator UI.
ADMIN_CUSTOMER_DATA_ROUTES = {
    "/admin/agent-actions/companies/{company_id}/requests",
    "/admin/agent-actions/requests/{request_id}",
}


def enforce_admin_customer_data_boundary(router: APIRouter) -> None:
    """Remove customer-data management routes from an admin configuration router.

    The underlying customer APIs remain tenant-scoped. This keeps Xvond Admin
    focused on configuration and platform health while preventing accidental
    operator access to customer request payloads.
    """
    router.routes[:] = [
        route
        for route in router.routes
        if getattr(route, "path", None) not in ADMIN_CUSTOMER_DATA_ROUTES
    ]
