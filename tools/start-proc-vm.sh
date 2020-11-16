#!/bin/bash
set -e

# Example script for starting processing VM on Azure
# Make sure to set AZ_GROUP and AZ_VM_NAME
az vm start --resource-group $AZ_GROUP --name $AZ_VM_NAME
