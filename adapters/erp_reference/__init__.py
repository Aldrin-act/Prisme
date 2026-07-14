"""erp_reference — L'unique adaptateur ERP réel, pour la preuve de concept (§5.4)."""

from .schema_erp import OperationERP, PayloadERP, PosteERP
from .translator import traduire

__all__ = ["OperationERP", "PayloadERP", "PosteERP", "traduire"]
