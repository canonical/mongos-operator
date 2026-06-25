# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "mongos" {
  charm {
    name     = "mongos"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }
  config            = var.config
  constraints       = var.constraints
  endpoint_bindings = var.endpoint_bindings
  machines          = (var.machines == null || length(var.machines) == 0) ? null : var.machines
  model_uuid        = var.model_uuid
  name              = var.app_name
  units             = (var.machines == null || length(var.machines) == 0) ? var.units : null
}
