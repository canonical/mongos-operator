# Charmed MongoDB Operator
[![Charmhub](https://charmhub.io/mongos/badge.svg)](https://charmhub.io/mongos)
[![Release to 6/edge](https://github.com/canonical/mongos-operator/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/mongos-operator/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/mongos-operator/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/mongos-operator/actions/workflows/ci.yaml)

## Overview

[mongos](https://www.mongodb.com/docs/v6.0/reference/program/mongos/) is a popular NoSQL database application. It stores its data with JSON-like documents creating a flexible user experience with easy-to-use data aggregation for data analytics. In addition, it is a distributed database, so vertical and horizontal scaling come naturally.

Applications like mongos must be managed and operated in the production environment. This means that mongos proxy administrators and analysts who run workloads in various infrastructures should be able to automate tasks for repeatable operational work. Technologies such as software operators encapsulate the knowledge, wisdom and expertise of a real-world operations team and codify it into a computer program that helps to operate complex server applications like MongoDB and other databases.

Canonical has developed an open-source operator called Charmed Mongos, which make it easier to operate mongos. The Charmed mongos Virtual Machine (VM) operator deploys and operates mongos on physical, Virtual Machines (VM) and other wide range of cloud and cloud-like environments, including AWS, Azure, OpenStack and VMWare.

Charmed monogs(VM Operator) is an enhanced, open source and fully-compatible drop-in replacement for the MongoDB Community Edition of mongos with advanced mongos enterprise features. It simplifies the deployment, scaling, design and management of mongos in production in a reliable way.

It acts as a [subordinate Charmed Operator](https://discourse.charmhub.io/t/subordinate-applications/1053) and is meant to act as a proxy to a sharded MongoDB cluster. To deploy a sharded MongoDB cluster please see our [Charmed solution for MongoDB](https://charmhub.io/mongodb)


