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
  endpoint_bindings = var.endpoint_bindings
  model_uuid        = var.model_uuid
  name              = var.app_name
}
