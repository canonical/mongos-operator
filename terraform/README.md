# Terraform module for mongos-operator

This is a Terraform module facilitating the deployment of the Mongos charm with [Terraform juju provider](https://github.com/juju/terraform-provider-juju/). For more information, refer to the provider [documentation](https://registry.terraform.io/providers/juju/juju/latest/docs). 

## Requirements

| Name | Version |
| ---- | ------- |
| `terraform` | >= 1.6 |
| `juju` | ~> 2.0 |

## Providers

| Name | Version |
| ---- | ------- |
| `juju` | ~> 2.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| `juju_application.mongos` | [Juju application](https://registry.terraform.io/providers/juju/juju/latest/docs/resources/application) |

## API

### Inputs
The module offers the following configurable inputs:

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| `app_name` | Application name | `string` | `"mongos"` | no |
| `base` | Charm base (old name: series) | `string` | `"ubuntu@24.04"` | no |
| `channel` | Charm channel | `string` | `"8/stable"` | no |
| `config` | Map of charm configuration options | `map(string)` | `{}` | no |
| `endpoint_bindings` | Map of endpoint bindings | `set(object)` | `[]` | no |
| `machines` | List of machines for placement | `set(string)` | `[]` | no |
| `model_uuid` | Model UUID | `string` | n/a | yes |
| `revision` | Charm revision | `number` | `null` | no |
| `units` | Charm units | `number` | `3` | no |


### Outputs
Upon applied, the module exports the following outputs:

| Name | Description |
|------|-------------|
| `application` | Object representing the deployed mongos application |
| `requires` | Map of all "requires" endpoints |
