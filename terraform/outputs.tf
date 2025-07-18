# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.mongos.name
}

# Required integration endpoints

output "mongos_proxy_endpoint" {
  description = "Name of the endpoint to provide the mongos_client interface."
  value       = "mongos_proxy"
}

output "cluster_endpoint" {
  description = "Name of the endpoint to provide the config-server interface."
  value       = "cluster"
}

output "certificates_endpoint" {
  description = "Name of the endpoint to provide the tls-certificates interface."
  value       = "certificates"
}
