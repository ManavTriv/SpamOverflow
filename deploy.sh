#!/bin/bash

terraform init
terraform apply -auto-approve

deployed_url="http://127.0.0.1:6400/"
echo "$deployed_url" > api.txt