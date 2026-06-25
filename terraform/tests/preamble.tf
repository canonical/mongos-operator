resource "null_resource" "preamble" {
  provisioner "local-exec" {
    command = <<-EOT
    sudo snap install juju-wait --classic || true
    EOT
  }
}

resource "juju_application" "data-integrator" {
  charm {
    name    = "data-integrator"
    channel = "latest/stable"
  }
  model_uuid = var.model_uuid
  depends_on = [null_resource.preamble]
}
