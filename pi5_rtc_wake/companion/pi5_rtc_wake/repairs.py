"""A native Settings reminder when a loaded companion needs a Core restart."""

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


@callback
def async_sync_restart_issue(hass, entry_id, required):
    issue_id = "homeassistant_restart_required_" + entry_id
    if required:
        ir.async_create_issue(hass, DOMAIN, issue_id, is_fixable=False,
                              severity=ir.IssueSeverity.WARNING,
                              translation_key="homeassistant_restart_required")
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
